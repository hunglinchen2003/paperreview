import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

class Database:
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            base_dir = Path(__file__).resolve().parent.parent
            data_dir = base_dir / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            self.db_path = str(data_dir / "papers.db")
        else:
            self.db_path = db_path
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
            
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Papers Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS papers (
                    pmid TEXT PRIMARY KEY,
                    pmcid TEXT,
                    doi TEXT,
                    title TEXT NOT NULL,
                    authors TEXT,
                    journal TEXT,
                    pub_date TEXT,
                    abstract TEXT,
                    pdf_url TEXT,
                    pdf_path TEXT,
                    text_path TEXT,
                    is_oa INTEGER DEFAULT 0,
                    has_pdf INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Reports Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date_str TEXT NOT NULL,
                    title TEXT NOT NULL,
                    markdown_content TEXT NOT NULL,
                    html_content TEXT,
                    paper_pmids TEXT,
                    github_url TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Pipeline execution logs Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    level TEXT NOT NULL,
                    message TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def log(self, level: str, message: str):
        try:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [{level}] {message}")
        except Exception:
            try:
                # Handle Windows cp950 console encoding fallback
                safe_msg = message.encode("cp950", errors="replace").decode("cp950")
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [{level}] {safe_msg}")
            except Exception:
                pass
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO logs (level, message, created_at) VALUES (?, ?, ?)",
                (level, message, datetime.now().isoformat())
            )
            conn.commit()

    def get_logs(self, limit: int = 100) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM logs ORDER BY id DESC LIMIT ?", (limit,)
            )
            return [dict(row) for row in cursor.fetchall()]

    def is_pmid_exists(self, pmid: str) -> bool:
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT 1 FROM papers WHERE pmid = ?", (str(pmid),))
            return cursor.fetchone() is not None

    def get_existing_pmids(self) -> set:
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT pmid FROM papers")
            return {row["pmid"] for row in cursor.fetchall()}

    def save_paper(self, paper: Dict[str, Any]):
        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO papers (
                    pmid, pmcid, doi, title, authors, journal, pub_date,
                    abstract, pdf_url, pdf_path, text_path, is_oa, has_pdf, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                str(paper.get("pmid")),
                paper.get("pmcid"),
                paper.get("doi"),
                paper.get("title", ""),
                paper.get("authors", ""),
                paper.get("journal", ""),
                paper.get("pub_date", ""),
                paper.get("abstract", ""),
                paper.get("pdf_url"),
                paper.get("pdf_path"),
                paper.get("text_path"),
                1 if paper.get("is_oa") else 0,
                1 if paper.get("has_pdf") else 0,
                datetime.now().isoformat()
            ))
            conn.commit()

    def get_papers(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM papers ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset)
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_paper_by_pmid(self, pmid: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM papers WHERE pmid = ?", (str(pmid),))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_total_paper_count(self) -> int:
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) as cnt FROM papers")
            return cursor.fetchone()["cnt"]

    def save_report(self, date_str: str, title: str, markdown_content: str, 
                    html_content: str = "", paper_pmids: List[str] = None, 
                    github_url: str = "") -> int:
        pmids_json = json.dumps(paper_pmids or [])
        with self._get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO reports (date_str, title, markdown_content, html_content, paper_pmids, github_url, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                date_str,
                title,
                markdown_content,
                html_content,
                pmids_json,
                github_url,
                datetime.now().isoformat()
            ))
            conn.commit()
            return cursor.lastrowid

    def update_report_github_url(self, report_id: int, github_url: str):
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE reports SET github_url = ? WHERE id = ?",
                (github_url, report_id)
            )
            conn.commit()

    def get_reports(self, limit: int = 30) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM reports ORDER BY id DESC LIMIT ?", (limit,)
            )
            rows = cursor.fetchall()
            results = []
            for row in rows:
                item = dict(row)
                try:
                    item["paper_pmids"] = json.loads(item["paper_pmids"]) if item["paper_pmids"] else []
                except Exception:
                    item["paper_pmids"] = []
                results.append(item)
            return results

    def get_report_by_id(self, report_id: int) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM reports WHERE id = ?", (report_id,))
            row = cursor.fetchone()
            if not row:
                return None
            item = dict(row)
            try:
                item["paper_pmids"] = json.loads(item["paper_pmids"]) if item["paper_pmids"] else []
            except Exception:
                item["paper_pmids"] = []
            return item
