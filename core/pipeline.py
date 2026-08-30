import os
import threading
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from config import load_config, BASE_DIR
from .database import Database
from .pubmed import PubMedSearcher
from .downloader import PDFDownloader
from .pdf_extractor import PDFExtractor
from .ollama_client import OllamaClient
from .github_publisher import GitHubPublisher
from .git_local_publisher import LocalGitPublisher
from .report_builder import build_bilingual_report

LOCK_FILE = BASE_DIR / "data" / "pipeline.lock"
LOCK_STALE_SECONDS = 3 * 60 * 60


class PipelineRunner:
    def __init__(self):
        self.lock = threading.Lock()
        self.is_running = False
        self.current_step = "待命中 (Idle)"
        self.progress = 0
        self.last_run_time = None
        self.last_result = None
        self.db = Database()

    def get_status(self) -> Dict[str, Any]:
        return {
            "is_running": self.is_running,
            "current_step": self.current_step,
            "progress": self.progress,
            "last_run_time": self.last_run_time,
            "last_result": self.last_result,
        }

    def _acquire_file_lock(self) -> bool:
        LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
        if LOCK_FILE.exists():
            age = time.time() - LOCK_FILE.stat().st_mtime
            if age < LOCK_STALE_SECONDS:
                return False
        LOCK_FILE.write_text(str(os.getpid()), encoding="utf-8")
        return True

    def _release_file_lock(self):
        try:
            if LOCK_FILE.exists():
                LOCK_FILE.unlink()
        except OSError:
            pass

    def start_pipeline_async(self, custom_query: Optional[str] = None, max_papers: Optional[int] = None) -> bool:
        if self.is_running:
            return False
        thread = threading.Thread(
            target=self._run_pipeline_worker,
            args=(custom_query, max_papers),
            daemon=True,
        )
        thread.start()
        return True

    def run_once(self, custom_query: Optional[str] = None, max_papers: Optional[int] = None) -> Dict[str, Any]:
        self._run_pipeline_worker(custom_query, max_papers)
        return self.last_result or {}

    def _select_papers(
        self,
        searcher: PubMedSearcher,
        candidates: List[str],
        target_count: int,
    ) -> List[Dict[str, Any]]:
        """Prefer open-access full text among newest unseen PMIDs."""
        details = searcher.fetch_paper_details(candidates)
        scored = []
        for paper in details:
            urls = searcher.collect_pdf_candidates(
                pmid=paper["pmid"],
                pmcid=paper.get("pmcid"),
                doi=paper.get("doi"),
            )
            paper["pdf_url"] = urls[0] if urls else None
            paper["oa_candidate"] = bool(urls or paper.get("pmcid"))
            scored.append(paper)
            time.sleep(0.12)

        with_oa = [p for p in scored if p.get("oa_candidate")]
        without_oa = [p for p in scored if not p.get("oa_candidate")]
        ordered = with_oa + without_oa
        return ordered[:target_count]

    def _run_pipeline_worker(self, custom_query: Optional[str] = None, max_papers_override: Optional[int] = None):
        with self.lock:
            if self.is_running:
                return
            if not self._acquire_file_lock():
                self.current_step = "另一個流程正在執行（檔案鎖）"
                self.last_result = {"success": False, "error": "pipeline already running"}
                return
            self.is_running = True
            self.progress = 0
            self.current_step = "啟動任務..."
            self.last_run_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cfg = load_config()
        query = custom_query or cfg.pubmed_query
        target_count = max_papers_override or cfg.max_papers_per_run
        today_str = datetime.now().strftime("%Y-%m-%d")

        self.db.log("INFO", f"啟動文獻檢索與綜述流程 | 關鍵字: '{query}', 目標篇數: {target_count}")

        try:
            self.current_step = f"正在搜尋 PubMed 文獻 ({query})..."
            self.progress = 8

            searcher = PubMedSearcher(email=cfg.email_for_ncbi)
            downloader = PDFDownloader(output_dir=f"{cfg.data_dir}/pdfs", email=cfg.email_for_ncbi)
            extractor = PDFExtractor(text_output_dir=f"{cfg.data_dir}/texts")
            ollama = OllamaClient(
                base_url=cfg.ollama_base_url,
                model=cfg.ollama_model,
                language=cfg.report_language,
            )
            publisher = GitHubPublisher(
                token=cfg.github_token,
                repo=cfg.github_repo,
                branch=cfg.github_branch,
                folder=cfg.github_folder,
            )

            existing_pmids = self.db.get_existing_pmids()
            self.db.log("INFO", f"資料庫中已有 {len(existing_pmids)} 篇歷史文獻，準備比對去重。")

            candidate_pmids = searcher.search_pmids(query=query, max_results=max(80, target_count * 12))
            new_pmids = [pmid for pmid in candidate_pmids if pmid not in existing_pmids]
            self.db.log(
                "INFO",
                f"檢索到 {len(candidate_pmids)} 篇候選文獻，篩選出 {len(new_pmids)} 篇未曾處理過的新文獻。",
            )

            if not new_pmids:
                msg = f"未找到關於 '{query}' 的新文獻（所有檢索結果皆已在資料庫中）。"
                self.db.log("WARNING", msg)
                self.current_step = "完成（無新文獻）"
                self.progress = 100
                self.last_result = {"success": True, "message": msg, "papers_count": 0}
                return

            self.current_step = "正在篩選具有開放全文的最新文獻..."
            self.progress = 20
            scan_pmids = new_pmids[: max(target_count * 6, 15)]
            papers = self._select_papers(searcher, scan_pmids, target_count)
            if not papers:
                raise RuntimeError("獲取 PubMed 文獻資訊失敗或返回為空。")
            self.db.log("INFO", f"選定即將處理的 {len(papers)} 篇文獻: {', '.join(p['pmid'] for p in papers)}")

            self.current_step = "正在下載 Open Access PDF / 擷取 PMC 全文..."
            self.progress = 35

            for i, paper in enumerate(papers, 1):
                pmid = paper["pmid"]
                self.db.log("INFO", f"[{i}/{len(papers)}] 下載與解析: PMID {pmid} - {paper['title'][:50]}...")

                pdf_path = downloader.download_paper_pdf(paper)
                paper["pdf_path"] = pdf_path
                paper["has_pdf"] = bool(pdf_path)
                paper["text_path"] = None
                paper["full_text_source"] = "abstract"

                if pdf_path:
                    full_text = extractor.extract_text_from_pdf(pdf_path, pmid=pmid)
                    if full_text:
                        paper["text_path"] = f"{cfg.data_dir}/texts/{pmid}.txt"
                        paper["full_text_source"] = "pdf"

                if not paper.get("text_path") and paper.get("pmcid"):
                    xml_text = searcher.fetch_pmc_fulltext(paper["pmcid"])
                    if xml_text:
                        text_file = Path(cfg.data_dir) / "texts" / f"{pmid}.txt"
                        text_file.parent.mkdir(parents=True, exist_ok=True)
                        text_file.write_text(xml_text, encoding="utf-8")
                        paper["text_path"] = str(text_file)
                        paper["full_text_source"] = "pmc_xml"
                        self.db.log("INFO", f"PMID {pmid} 改用 Europe PMC 全文 XML。")

                self.db.save_paper(paper)

            self.current_step = f"正在呼叫 Ollama ({cfg.ollama_model}) 進行各篇雙語剖析..."
            self.progress = 55

            paper_analyses: List[str] = []
            for i, paper in enumerate(papers, 1):
                pmid = paper["pmid"]
                self.db.log("INFO", f"[{i}/{len(papers)}] LLM 剖析中: PMID {pmid}...")
                full_text = None
                text_file = paper.get("text_path") or f"{cfg.data_dir}/texts/{pmid}.txt"
                try:
                    raw = Path(text_file).read_text(encoding="utf-8")
                    full_text = extractor.get_text_excerpt_for_llm(raw, max_chars=14000)
                except Exception:
                    full_text = None

                analysis = ollama.analyze_single_paper(
                    paper,
                    full_text=full_text,
                    system_prompt=cfg.system_prompt,
                    query_keyword=query,
                )
                paper_analyses.append(analysis)

            self.current_step = "正在撰寫中文與英文綜述日報..."
            self.progress = 75
            self.db.log("INFO", "分別生成中文與英文綜述…")

            zh_digest = ollama.generate_zh_digest(papers, paper_analyses, query, cfg.system_prompt)
            self.progress = 85
            en_digest = ollama.generate_en_digest(papers, paper_analyses, query, cfg.system_prompt)

            report_title = f"{query} 文獻綜述 / Literature Digest ({today_str})"
            master_report_md = build_bilingual_report(
                papers=papers,
                paper_analyses=paper_analyses,
                zh_digest=zh_digest,
                en_digest=en_digest,
                query_keyword=query,
                model_name=cfg.ollama_model,
                date_str=today_str,
            )

            report_id = self.db.save_report(
                date_str=today_str,
                title=report_title,
                markdown_content=master_report_md,
                paper_pmids=[p["pmid"] for p in papers],
            )
            self.db.log("INFO", f"綜述報告已儲存至資料庫 (Report ID: {report_id})")

            self.current_step = "正在生成靜態頁面與發布至 GitHub Pages..."
            self.progress = 90

            all_reports = self.db.get_reports(limit=50)
            pub_res = publisher.publish_to_github(
                date_str=today_str,
                title=report_title,
                markdown_content=master_report_md,
                all_reports=all_reports,
                query_keyword=query,
            )

            github_url = pub_res.get("github_pages_url", "")
            if github_url:
                self.db.update_report_github_url(report_id, github_url)

            if pub_res.get("success"):
                self.db.log("INFO", f"GitHub Pages API 發布成功！網址: {github_url}")
            else:
                self.db.log("INFO", "靜態網頁已產生於 docs/，嘗試本地 Git 同步...")
                local_git = LocalGitPublisher()
                git_res = local_git.sync_and_push(commit_msg=f"Update {query} digest: {today_str}")
                self.db.log("INFO", f"本地 Git 狀態: {git_res.get('message')}")
                if git_res.get("success") and cfg.github_repo:
                    owner, repo_name = cfg.github_repo.split("/", 1)
                    github_url = f"https://{owner}.github.io/{repo_name}/reports/{today_str}.html"
                    self.db.update_report_github_url(report_id, github_url)

            self.current_step = "流程執行完畢"
            self.progress = 100
            self.last_result = {
                "success": True,
                "report_id": report_id,
                "report_title": report_title,
                "papers_count": len(papers),
                "github_url": github_url,
                "local_path": pub_res.get("local_path"),
                "date": today_str,
            }
            self.db.log("INFO", f"每日流程順利完成！共處理 {len(papers)} 篇文獻。")

        except Exception as e:
            err_trace = traceback.format_exc()
            self.db.log("ERROR", f"流程執行失敗: {e}\n{err_trace}")
            self.current_step = f"發生錯誤: {e}"
            self.progress = 100
            self.last_result = {"success": False, "error": str(e)}
        finally:
            self.is_running = False
            self._release_file_lock()


runner = PipelineRunner()
