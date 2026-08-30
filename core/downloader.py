import os
import requests
from pathlib import Path
from typing import Optional, Dict, Any, List


class PDFDownloader:
    def __init__(self, output_dir: str = "data/pdfs", email: str = "researcher@example.com"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        from .pubmed import PubMedSearcher
        self.pubmed = PubMedSearcher(email=email)
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/pdf,application/octet-stream;q=0.9,*/*;q=0.8",
        })

    def download_paper_pdf(self, paper: Dict[str, Any]) -> Optional[str]:
        pmid = str(paper.get("pmid"))
        pdf_path = self.output_dir / f"{pmid}.pdf"

        if pdf_path.exists() and pdf_path.stat().st_size > 5000:
            paper["has_pdf"] = True
            paper["full_text_source"] = paper.get("full_text_source") or "pdf"
            return str(pdf_path)

        candidates: List[str] = []
        if paper.get("pdf_url"):
            candidates.append(paper["pdf_url"])
        candidates.extend(
            self.pubmed.collect_pdf_candidates(
                pmid=pmid,
                pmcid=paper.get("pmcid"),
                doi=paper.get("doi"),
            )
        )

        # Deduplicate while preserving order
        seen = set()
        urls = []
        for u in candidates:
            if u and u not in seen:
                seen.add(u)
                urls.append(u)

        for pdf_url in urls:
            try:
                print(f"[Downloader] Downloading PDF for PMID {pmid} from {pdf_url} ...")
                resp = self.session.get(pdf_url, stream=True, timeout=45, allow_redirects=True)
                if resp.status_code != 200:
                    print(f"[Downloader] HTTP {resp.status_code} for {pdf_url}")
                    continue
                content = resp.content
                if content.startswith(b"%PDF") or b"%PDF-" in content[:2048]:
                    with open(pdf_path, "wb") as f:
                        f.write(content)
                    paper["pdf_url"] = pdf_url
                    paper["has_pdf"] = True
                    paper["full_text_source"] = "pdf"
                    print(f"[Downloader] Saved PDF: {pdf_path} ({len(content)} bytes)")
                    return str(pdf_path)
                print(f"[Downloader] Not a PDF for PMID {pmid} (HTML/paywall).")
            except Exception as e:
                print(f"[Downloader] Error downloading PMID {pmid}: {e}")

        print(f"[Downloader] No open-access PDF for PMID {pmid}")
        return None
