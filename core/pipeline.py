import threading
import traceback
from datetime import datetime
from typing import Dict, Any, List, Optional

from config import load_config
from .database import Database
from .pubmed import PubMedSearcher
from .downloader import PDFDownloader
from .pdf_extractor import PDFExtractor
from .ollama_client import OllamaClient
from .github_publisher import GitHubPublisher
from .git_local_publisher import LocalGitPublisher

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
            "last_result": self.last_result
        }

    def start_pipeline_async(self, custom_query: Optional[str] = None, max_papers: Optional[int] = None) -> bool:
        """
        Start the pipeline in a background thread.
        Returns True if started, False if already running.
        """
        if self.is_running:
            return False

        thread = threading.Thread(
            target=self._run_pipeline_worker,
            args=(custom_query, max_papers),
            daemon=True
        )
        thread.start()
        return True

    def _run_pipeline_worker(self, custom_query: Optional[str] = None, max_papers_override: Optional[int] = None):
        with self.lock:
            self.is_running = True
            self.progress = 0
            self.current_step = "啟動任務..."
            self.last_run_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cfg = load_config()
        query = custom_query or cfg.pubmed_query
        target_count = max_papers_override or cfg.max_papers_per_run
        today_str = datetime.now().strftime("%Y-%m-%d")

        self.db.log("INFO", f"🚀 啟動文獻檢索與綜述流程 | 關鍵字: '{query}', 目標篇數: {target_count}")

        try:
            # Step 1: Initialize components
            self.current_step = f"正在搜尋 PubMed 文獻 ({query})..."
            self.progress = 10
            
            searcher = PubMedSearcher(email=cfg.email_for_ncbi)
            downloader = PDFDownloader(output_dir=f"{cfg.data_dir}/pdfs", email=cfg.email_for_ncbi)
            extractor = PDFExtractor(text_output_dir=f"{cfg.data_dir}/texts")
            ollama = OllamaClient(base_url=cfg.ollama_base_url, model=cfg.ollama_model, language=cfg.report_language)
            publisher = GitHubPublisher(
                token=cfg.github_token,
                repo=cfg.github_repo,
                branch=cfg.github_branch,
                folder=cfg.github_folder
            )

            # Step 2: Search PubMed and deduplicate
            existing_pmids = self.db.get_existing_pmids()
            self.db.log("INFO", f"資料庫中已有 {len(existing_pmids)} 篇歷史文獻，準備比對去重。")

            # Fetch a larger batch of candidates (e.g. 50) to find uncollected ones
            candidate_pmids = searcher.search_pmids(query=query, max_results=max(50, target_count * 5))
            
            new_pmids = [pmid for pmid in candidate_pmids if pmid not in existing_pmids]
            self.db.log("INFO", f"檢索到 {len(candidate_pmids)} 篇候選文獻，篩選出 {len(new_pmids)} 篇未曾處理過的新文獻。")

            if not new_pmids:
                msg = f"未找到關於 '{query}' 的新文獻（所有檢索結果皆已在資料庫中）。"
                self.db.log("WARNING", msg)
                self.current_step = "完成（無新文獻）"
                self.progress = 100
                self.last_result = {"success": True, "message": msg, "papers_count": 0}
                return

            # Take up to target_count
            selected_pmids = new_pmids[:target_count]
            self.db.log("INFO", f"選定即將處理的 {len(selected_pmids)} 篇文獻: {', '.join(selected_pmids)}")

            # Step 3: Fetch full metadata
            self.current_step = f"正在獲取 {len(selected_pmids)} 篇文獻詳細資訊與摘要..."
            self.progress = 25
            papers = searcher.fetch_paper_details(selected_pmids)
            if not papers:
                raise RuntimeError("獲取 PubMed 文獻資訊失敗或返回為空。")

            # Step 4: Download PDFs & Extract Text
            self.current_step = "正在嘗試下載 Open Access PDF 全文與轉換文字..."
            self.progress = 40
            
            for i, paper in enumerate(papers, 1):
                pmid = paper["pmid"]
                self.db.log("INFO", f"[{i}/{len(papers)}] 下載與解析: PMID {pmid} - {paper['title'][:40]}...")
                
                pdf_path = downloader.download_paper_pdf(paper)
                paper["has_pdf"] = bool(pdf_path)
                paper["pdf_path"] = pdf_path
                
                full_text = None
                if pdf_path:
                    full_text = extractor.extract_text_from_pdf(pdf_path, pmid=pmid)
                    paper["text_path"] = f"{cfg.data_dir}/texts/{pmid}.txt" if full_text else None

                # Save paper metadata to database
                self.db.save_paper(paper)

            # Step 5: Ollama Analysis
            self.current_step = f"正在呼叫 Ollama ({cfg.ollama_model}) 進行各篇論文深入剖析..."
            self.progress = 60
            
            paper_analyses = []
            for i, paper in enumerate(papers, 1):
                pmid = paper["pmid"]
                self.db.log("INFO", f"[{i}/{len(papers)}] LLM 剖析中: PMID {pmid}...")
                
                full_text = None
                if paper.get("pdf_path"):
                    text_file = f"{cfg.data_dir}/texts/{pmid}.txt"
                    try:
                        with open(text_file, "r", encoding="utf-8") as tf:
                            full_text = extractor.get_text_excerpt_for_llm(tf.read(), max_chars=12000)
                    except Exception:
                        full_text = None

                analysis = ollama.analyze_single_paper(paper, full_text=full_text, system_prompt=cfg.system_prompt)
                paper_analyses.append(analysis)

            # Step 6: Generate Master Review Digest
            self.current_step = "正在呼叫 Ollama 整合撰寫跨文獻前沿研究綜述日報..."
            self.progress = 80
            self.db.log("INFO", "整合跨文獻資料，生成今日前沿綜述總結報告...")
            
            report_title = f"Galectin 前沿研究動態與文獻綜述日報 ({today_str})"
            master_report_md = ollama.generate_comprehensive_report(
                papers=papers,
                paper_analyses=paper_analyses,
                query_keyword=query,
                system_prompt=cfg.system_prompt
            )

            # Save report locally & in DB
            report_id = self.db.save_report(
                date_str=today_str,
                title=report_title,
                markdown_content=master_report_md,
                paper_pmids=[p["pmid"] for p in papers]
            )
            self.db.log("INFO", f"綜述報告已儲存至資料庫 (Report ID: {report_id})")

            # Step 7: GitHub Pages publishing
            self.current_step = "正在生成靜態頁面與發布至 GitHub Pages..."
            self.progress = 90
            
            all_reports = self.db.get_reports(limit=50)
            pub_res = publisher.publish_to_github(
                date_str=today_str,
                title=report_title,
                markdown_content=master_report_md,
                all_reports=all_reports
            )

            github_url = pub_res.get("github_pages_url", "")
            if github_url:
                self.db.update_report_github_url(report_id, github_url)

            if pub_res.get("success"):
                self.db.log("INFO", f"🎉 GitHub Pages API 發布成功！網址: {github_url}")
            else:
                self.db.log("INFO", f"靜態網頁已產生於 docs/，嘗試本地 Git 同步...")
                local_git = LocalGitPublisher()
                git_res = local_git.sync_and_push(commit_msg=f"🤖 Update Galectin digest: {today_str}")
                self.db.log("INFO", f"本地 Git 狀態: {git_res.get('message')}")

            self.current_step = "流程執行完畢"
            self.progress = 100
            self.last_result = {
                "success": True,
                "report_id": report_id,
                "report_title": report_title,
                "papers_count": len(papers),
                "github_url": github_url,
                "local_path": pub_res.get("local_path"),
                "date": today_str
            }
            self.db.log("INFO", f"✅ 每日流程順利完成！共處理 {len(papers)} 篇文獻。")

        except Exception as e:
            err_trace = traceback.format_exc()
            self.db.log("ERROR", f"❌ 流程執行失敗: {e}\n{err_trace}")
            self.current_step = f"發生錯誤: {e}"
            self.progress = 100
            self.last_result = {"success": False, "error": str(e)}
        finally:
            self.is_running = False

# Global Singleton
runner = PipelineRunner()
