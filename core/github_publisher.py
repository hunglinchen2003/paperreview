import os
import json
import base64
import requests
import markdown
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

class GitHubPublisher:
    def __init__(self, token: str = "", repo: str = "", branch: str = "main", folder: str = "docs"):
        """
        token: GitHub Personal Access Token (PAT) with `repo` permission
        repo: 'owner/repo-name' e.g. 'username/username.github.io' or 'username/galectin-digest'
        branch: Target branch e.g. 'main' or 'gh-pages'
        folder: Subfolder in repo e.g. 'docs'
        """
        self.token = token.strip()
        self.repo = repo.strip()
        self.branch = branch.strip() or "main"
        self.folder = folder.strip().rstrip("/")
        self.base_api = "https://api.github.com"
        
        # Local docs directory for static hosting or preview
        base_dir = Path(__file__).resolve().parent.parent
        self.local_docs_dir = base_dir / "docs"
        self.local_docs_dir.mkdir(parents=True, exist_ok=True)
        (self.local_docs_dir / "reports").mkdir(parents=True, exist_ok=True)

    @property
    def is_configured(self) -> bool:
        return bool(self.token and self.repo and "/" in self.repo)

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "PubMed-Galectin-Reviewer-Bot"
        }

    def test_connection(self) -> Dict[str, Any]:
        """
        Test GitHub authentication and repository access.
        """
        if not self.is_configured:
            return {"success": False, "error": "GitHub Token 或 Repository 未設定完整 (格式須為 owner/repo)。"}

        url = f"{self.base_api}/repos/{self.repo}"
        try:
            resp = requests.get(url, headers=self._get_headers(), timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "success": True,
                    "repo_name": data.get("full_name"),
                    "private": data.get("private"),
                    "default_branch": data.get("default_branch"),
                    "html_url": data.get("html_url")
                }
            elif resp.status_code == 404:
                return {"success": False, "error": f"找不到倉庫 {self.repo}，請確認倉庫名稱或 Token 權限。"}
            elif resp.status_code == 401:
                return {"success": False, "error": "GitHub Token 驗證失敗 (401 Unauthorized)。"}
            else:
                return {"success": False, "error": f"GitHub API 錯誤碼 {resp.status_code}: {resp.text}"}
        except Exception as e:
            return {"success": False, "error": f"連線異常: {e}"}

    def convert_markdown_to_html(self, markdown_content: str, title: str, date_str: str) -> str:
        """
        Convert markdown report to a beautifully styled standalone HTML document.
        """
        # Convert MD to HTML with tables, code blocks, fenced_code, etc.
        body_html = markdown.markdown(
            markdown_content,
            extensions=["extra", "codehilite", "toc", "tables", "nl2br"]
        )

        html_template = f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} | Galectin 文獻綜述</title>
    <!-- Tailwind CSS -->
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <style>
        .prose h1 {{ font-size: 1.875rem; font-weight: 800; color: #1e293b; margin-top: 1.5rem; margin-bottom: 1rem; border-bottom: 2px solid #e2e8f0; padding-bottom: 0.5rem; }}
        .prose h2 {{ font-size: 1.5rem; font-weight: 700; color: #0f766e; margin-top: 1.75rem; margin-bottom: 0.75rem; }}
        .prose h3 {{ font-size: 1.25rem; font-weight: 600; color: #1e293b; margin-top: 1.25rem; margin-bottom: 0.5rem; }}
        .prose p {{ margin-bottom: 1rem; line-height: 1.75; color: #334155; }}
        .prose ul {{ list-style-type: disc; padding-left: 1.5rem; margin-bottom: 1rem; color: #334155; }}
        .prose ol {{ list-style-type: decimal; padding-left: 1.5rem; margin-bottom: 1rem; color: #334155; }}
        .prose li {{ margin-bottom: 0.5rem; }}
        .prose blockquote {{ border-left: 4px solid #0d9488; padding-left: 1rem; color: #475569; font-style: italic; margin: 1rem 0; }}
        .prose hr {{ margin: 2rem 0; border-color: #cbd5e1; }}
        .prose strong {{ color: #0f172a; font-weight: 600; }}
        .prose code {{ background-color: #f1f5f9; padding: 0.2rem 0.4rem; border-radius: 0.25rem; font-size: 0.875em; color: #0f766e; }}
    </style>
</head>
<body class="bg-slate-50 min-h-screen text-slate-800 font-sans">
    <nav class="bg-teal-800 text-white shadow-md sticky top-0 z-50">
        <div class="max-w-5xl mx-auto px-4 py-3 flex items-center justify-between">
            <a href="../index.html" class="flex items-center space-x-2 text-teal-100 hover:text-white font-medium transition">
                <i class="fa-solid fa-arrow-left"></i>
                <span>返回總覽清單</span>
            </a>
            <div class="flex items-center space-x-2">
                <span class="bg-teal-900/80 px-3 py-1 rounded-full text-xs font-mono text-teal-200">
                    <i class="fa-regular fa-calendar-days mr-1"></i> {date_str}
                </span>
            </div>
        </div>
    </nav>

    <main class="max-w-5xl mx-auto px-4 py-8">
        <div class="bg-white rounded-2xl shadow-sm border border-slate-200/80 p-6 md:p-10 mb-8">
            <div class="prose max-w-none">
                {body_html}
            </div>
        </div>
        
        <footer class="text-center text-slate-400 text-sm py-6">
            <p>🤖 由 PubMed 智能追蹤機器人與 Ollama 本地模型自動生成</p>
            <p class="mt-1 text-xs">報告產生時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </footer>
    </main>
</body>
</html>
"""
        return html_template

    def generate_index_html(self, reports: List[Dict[str, Any]]) -> str:
        """
        Generate the master index.html for GitHub Pages listing all past reports.
        """
        cards_html = ""
        for rep in reports:
            rep_id = rep.get("id")
            date_str = rep.get("date_str", "Unknown Date")
            title = rep.get("title", f"Galectin 文獻日報 - {date_str}")
            created_at = rep.get("created_at", "")[:19].replace("T", " ")
            pmids = rep.get("paper_pmids", [])
            paper_count = len(pmids) if isinstance(pmids, list) else 0
            
            # Link to single report HTML
            file_link = f"reports/{date_str}.html"

            cards_html += f"""
            <div class="report-card bg-white rounded-xl border border-slate-200 hover:border-teal-500/50 hover:shadow-lg transition-all duration-200 p-6 flex flex-col justify-between" data-title="{title.lower()}" data-date="{date_str}">
                <div>
                    <div class="flex items-center justify-between text-xs font-medium text-slate-400 mb-3">
                        <span class="bg-teal-50 text-teal-700 px-2.5 py-1 rounded-md border border-teal-200/60 font-mono">
                            <i class="fa-regular fa-calendar mr-1"></i>{date_str}
                        </span>
                        <span><i class="fa-solid fa-file-pdf mr-1 text-teal-600"></i>{paper_count} 篇論文</span>
                    </div>
                    <h3 class="text-lg font-bold text-slate-800 hover:text-teal-700 transition mb-3 line-clamp-2">
                        <a href="{file_link}">{title}</a>
                    </h3>
                </div>
                <div class="pt-4 border-t border-slate-100 flex items-center justify-between mt-4">
                    <span class="text-xs text-slate-400 font-mono">
                        <i class="fa-regular fa-clock mr-1"></i>{created_at}
                    </span>
                    <a href="{file_link}" class="inline-flex items-center text-sm font-semibold text-teal-600 hover:text-teal-800 transition">
                        閱讀報告 <i class="fa-solid fa-arrow-right ml-1 text-xs"></i>
                    </a>
                </div>
            </div>
            """

        index_template = f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Galectin 前沿研究日報 | GitHub Pages</title>
    <!-- Tailwind CSS -->
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
</head>
<body class="bg-slate-50 min-h-screen text-slate-800 font-sans">
    <!-- Header -->
    <header class="bg-gradient-to-r from-teal-800 via-teal-700 to-cyan-800 text-white shadow-lg">
        <div class="max-w-6xl mx-auto px-4 py-12">
            <div class="flex flex-col md:flex-row md:items-center md:justify-between gap-6">
                <div>
                    <div class="inline-flex items-center gap-2 bg-teal-900/60 px-3 py-1 rounded-full text-xs font-semibold tracking-wide text-teal-200 mb-3 border border-teal-500/30">
                        <i class="fa-solid fa-dna animate-spin text-teal-300" style="animation-duration: 8s;"></i> 生醫文獻自動化追蹤系統
                    </div>
                    <h1 class="text-3xl md:text-4xl font-extrabold tracking-tight">Galectin 研究動態綜述日報</h1>
                    <p class="mt-2 text-teal-100 text-sm md:text-base max-w-2xl">
                        每日定時自 PubMed 檢索最新 Galectin（半乳糖凝集素）相關文獻，自動下載全文與解析，並由本地 Ollama 深度模型撰寫之專業前沿研究綜述。
                    </p>
                </div>
                <div class="flex items-center gap-3 bg-white/10 backdrop-blur-md p-4 rounded-xl border border-white/20">
                    <div class="text-center px-4">
                        <div class="text-2xl font-bold text-white">{len(reports)}</div>
                        <div class="text-xs text-teal-200 mt-0.5">累計綜述</div>
                    </div>
                </div>
            </div>
        </div>
    </header>

    <!-- Content & Search -->
    <main class="max-w-6xl mx-auto px-4 py-8">
        <div class="mb-8 flex flex-col sm:flex-row gap-4 items-center justify-between">
            <div class="relative w-full sm:w-80">
                <i class="fa-solid fa-magnifying-glass absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"></i>
                <input type="text" id="searchInput" placeholder="搜尋歷史報告標題或日期..." 
                       class="w-full pl-9 pr-4 py-2 text-sm bg-white border border-slate-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-teal-500" />
            </div>
            <div class="text-sm text-slate-500 self-end sm:self-auto font-medium">
                顯示共 <span id="reportCount" class="font-bold text-teal-700">{len(reports)}</span> 份報告
            </div>
        </div>

        <div id="reportsGrid" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {cards_html or '<div class="col-span-full py-16 text-center text-slate-400 bg-white rounded-xl border border-dashed border-slate-300"><i class="fa-regular fa-folder-open text-4xl mb-3 text-slate-300"></i><p>目前尚無已發布的綜述報告</p></div>'}
        </div>
        
        <footer class="text-center text-slate-400 text-sm py-12 mt-8 border-t border-slate-200">
            <p>🤖 自動化維護於 GitHub Pages • 由 PubMed & Ollama LLM 驅動</p>
        </footer>
    </main>

    <script>
        const searchInput = document.getElementById('searchInput');
        const cards = document.querySelectorAll('.report-card');
        const countSpan = document.getElementById('reportCount');

        if (searchInput) {{
            searchInput.addEventListener('input', (e) => {{
                const val = e.target.value.toLowerCase().trim();
                let visibleCount = 0;
                cards.forEach(card => {{
                    const title = card.getAttribute('data-title') || '';
                    const date = card.getAttribute('data-date') || '';
                    if (title.includes(val) || date.includes(val)) {{
                        card.style.display = 'flex';
                        visibleCount++;
                    }} else {{
                        card.style.display = 'none';
                    }}
                }});
                countSpan.innerText = visibleCount;
            }});
        }}
    </script>
</body>
</html>
"""
        return index_template

    def save_local_report_files(self, date_str: str, title: str, markdown_content: str, all_reports: List[Dict[str, Any]]) -> str:
        """
        Save static HTML, MD, and master index.html into local docs/ directory.
        Returns local path of the generated HTML report.
        """
        # Save markdown
        md_file = self.local_docs_dir / "reports" / f"{date_str}.md"
        with open(md_file, "w", encoding="utf-8") as f:
            f.write(markdown_content)

        # Save single report HTML
        html_content = self.convert_markdown_to_html(markdown_content, title, date_str)
        html_file = self.local_docs_dir / "reports" / f"{date_str}.html"
        with open(html_file, "w", encoding="utf-8") as f:
            f.write(html_content)

        # Save index.html
        index_html = self.generate_index_html(all_reports)
        index_file = self.local_docs_dir / "index.html"
        with open(index_file, "w", encoding="utf-8") as f:
            f.write(index_html)

        return str(html_file)

    def publish_to_github(self, date_str: str, title: str, markdown_content: str, all_reports: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Upload the report markdown, report HTML, and updated index.html to GitHub repository.
        """
        # 1. Save locally first
        local_html = self.save_local_report_files(date_str, title, markdown_content, all_reports)

        if not self.is_configured:
            return {
                "success": False,
                "message": "GitHub Token 或 Repo 未配置，報告已儲存於本地 docs/ 資料夾。",
                "local_path": local_html
            }

        headers = self._get_headers()
        base_path = f"{self.folder}/" if self.folder else ""

        # Prepare files to commit
        html_content = self.convert_markdown_to_html(markdown_content, title, date_str)
        index_html = self.generate_index_html(all_reports)

        files_to_push = {
            f"{base_path}reports/{date_str}.md": markdown_content,
            f"{base_path}reports/{date_str}.html": html_content,
            f"{base_path}index.html": index_html
        }

        pushed_files = []
        errors = []

        for file_path, content_str in files_to_push.items():
            try:
                # 1. Check if file already exists to get its SHA (needed for update)
                url = f"{self.base_api}/repos/{self.repo}/contents/{file_path}?ref={self.branch}"
                get_resp = requests.get(url, headers=headers, timeout=15)
                sha = None
                if get_resp.status_code == 200:
                    sha = get_resp.json().get("sha")

                # 2. PUT file content
                put_url = f"{self.base_api}/repos/{self.repo}/contents/{file_path}"
                content_bytes = content_str.encode("utf-8")
                b64_content = base64.b64encode(content_bytes).decode("utf-8")

                payload = {
                    "message": f"🤖 Auto-publish Galectin daily digest: {date_str}",
                    "content": b64_content,
                    "branch": self.branch
                }
                if sha:
                    payload["sha"] = sha

                put_resp = requests.put(put_url, headers=headers, json=payload, timeout=20)
                if put_resp.status_code in (200, 201):
                    pushed_files.append(file_path)
                else:
                    errors.append(f"Failed to push {file_path}: {put_resp.status_code} {put_resp.text}")
            except Exception as e:
                errors.append(f"Exception pushing {file_path}: {e}")

        owner = self.repo.split("/")[0]
        repo_name = self.repo.split("/")[1]
        pages_url = f"https://{owner}.github.io/{repo_name}/" if not repo_name.endswith(".github.io") else f"https://{owner}.github.io/"
        report_url = f"{pages_url}reports/{date_str}.html"

        if errors and not pushed_files:
            return {
                "success": False,
                "message": "GitHub 發布失敗: " + " | ".join(errors),
                "errors": errors,
                "local_path": local_html
            }

        return {
            "success": True,
            "message": f"成功發布 {len(pushed_files)} 個檔案至 GitHub ({self.repo} @ {self.branch})！",
            "pushed_files": pushed_files,
            "github_pages_url": report_url,
            "index_url": pages_url,
            "local_path": local_html
        }
