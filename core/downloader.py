import os
import requests
from pathlib import Path
from typing import Optional, Dict, Any
from .pubmed import PubMedSearcher

class PDFDownloader:
    def __init__(self, output_dir: str = "data/pdfs", email: str = "researcher@example.com"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.pubmed = PubMedSearcher(email=email)
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/pdf,text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        })

    def download_paper_pdf(self, paper: Dict[str, Any]) -> Optional[str]:
        """
        Attempt to download PDF for a given paper dict.
        Returns local file path if successful, None otherwise.
        """
        pmid = str(paper.get("pmid"))
        pdf_path = self.output_dir / f"{pmid}.pdf"
        
        # If PDF already exists locally and valid
        if pdf_path.exists() and pdf_path.stat().st_size > 5000:
            return str(pdf_path)

        # Resolve PDF URL
        pdf_url = paper.get("pdf_url")
        if not pdf_url:
            pdf_url = self.pubmed.resolve_open_access_pdf_url(
                pmid=pmid,
                pmcid=paper.get("pmcid"),
                doi=paper.get("doi")
            )
            paper["pdf_url"] = pdf_url

        if not pdf_url:
            print(f"[Downloader] No open access PDF URL found for PMID {pmid}")
            return None

        # Try downloading
        try:
            print(f"[Downloader] Downloading PDF for PMID {pmid} from {pdf_url} ...")
            resp = self.session.get(pdf_url, stream=True, timeout=30, allow_redirects=True)
            
            if resp.status_code == 200:
                content = resp.content
                # Verify that it is actually a PDF file
                if content.startswith(b"%PDF") or b"%PDF-" in content[:1024]:
                    with open(pdf_path, "wb") as f:
                        f.write(content)
                    print(f"[Downloader] Successfully saved PDF: {pdf_path} ({len(content)} bytes)")
                    return str(pdf_path)
                else:
                    print(f"[Downloader] Downloaded file for PMID {pmid} is not a valid PDF (HTML/Blocked).")
            else:
                print(f"[Downloader] Failed with status code {resp.status_code} for URL: {pdf_url}")
        except Exception as e:
            print(f"[Downloader] Error downloading PMID {pmid}: {e}")

        return None
