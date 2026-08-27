import re
from pathlib import Path
from typing import Optional

class PDFExtractor:
    def __init__(self, text_output_dir: str = "data/texts"):
        self.text_output_dir = Path(text_output_dir)
        self.text_output_dir.mkdir(parents=True, exist_ok=True)

    def extract_text_from_pdf(self, pdf_path: str, pmid: Optional[str] = None) -> Optional[str]:
        """
        Extract text from PDF file using PyMuPDF (fitz) or pypdf as fallback.
        Saves clean text file and returns the extracted string.
        """
        path = Path(pdf_path)
        if not path.exists() or path.stat().st_size == 0:
            return None

        text = ""
        # Try PyMuPDF (fitz) first
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(str(path))
            pages_text = []
            for page_num in range(len(doc)):
                page = doc[page_num]
                page_text = page.get_text("text")
                if page_text:
                    pages_text.append(page_text)
            text = "\n\n".join(pages_text)
            doc.close()
        except ImportError:
            # Fallback to pypdf
            try:
                from pypdf import PdfReader
                reader = PdfReader(str(path))
                pages_text = []
                for page in reader.pages:
                    extracted = page.extract_text()
                    if extracted:
                        pages_text.append(extracted)
                text = "\n\n".join(pages_text)
            except Exception as e:
                print(f"[PDF Extractor] Error using pypdf fallback for {pdf_path}: {e}")
                return None
        except Exception as e:
            print(f"[PDF Extractor] Error using PyMuPDF for {pdf_path}: {e}")
            return None

        if not text.strip():
            return None

        cleaned_text = self._clean_academic_text(text)

        # Save to text_output_dir if pmid is given or filename
        save_name = f"{pmid}.txt" if pmid else f"{path.stem}.txt"
        saved_file = self.text_output_dir / save_name
        try:
            with open(saved_file, "w", encoding="utf-8") as f:
                f.write(cleaned_text)
        except Exception as e:
            print(f"[PDF Extractor] Error saving extracted text to {saved_file}: {e}")

        return cleaned_text

    def _clean_academic_text(self, text: str) -> str:
        """
        Clean academic PDF extraction artifacts:
        - Remove duplicate blank lines
        - Rejoin broken hyphenated words
        - Trim overly long reference lists if needed
        """
        # Fix line breaks within words (e.g., "galec-\ntin" -> "galectin")
        text = re.sub(r'(\w+)-\n(\w+)', r'\1\2', text)
        
        # Replace multiple spaces with single space
        text = re.sub(r'[ \t]+', ' ', text)
        
        # Replace 3 or more newlines with 2 newlines
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        return text.strip()

    def get_text_excerpt_for_llm(self, text: str, max_chars: int = 15000) -> str:
        """
        Limit text length for LLM context window while preserving Introduction,
        Results, Discussion, and Conclusion sections.
        """
        if len(text) <= max_chars:
            return text

        # Find if References section exists and truncate after it
        ref_match = re.search(r'\n\s*(?:REFERENCES|References|Bibliography|LITERATURE CITED)\s*\n', text)
        if ref_match:
            main_text = text[:ref_match.start()]
            if len(main_text) <= max_chars:
                return main_text
            # Take the beginning (Intro/Methods) and the end of main_text (Results/Discussion)
            half = max_chars // 2
            return main_text[:half] + "\n\n[...中間內文節略...]\n\n" + main_text[-half:]

        half = max_chars // 2
        return text[:half] + "\n\n[...內文節略...]\n\n" + text[-half:]
