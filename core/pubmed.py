import re
import time
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional
import requests

NCBI_ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
NCBI_EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
EUROPE_PMC_SEARCH_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"

class PubMedSearcher:
    def __init__(self, email: str = "researcher@example.com", tool_name: str = "galectin_reviewer"):
        self.email = email
        self.tool_name = tool_name
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": f"PubMedReviewerBot/1.0 ({email})"
        })

    def search_pmids(self, query: str, max_results: int = 20) -> List[str]:
        """
        Search PubMed for recent articles matching the query.
        Returns list of PMIDs sorted by publication date (most recent first).
        """
        term = query.strip()
        # Keep user keywords, but prefer title/abstract matches for a topical digest.
        if "[" not in term:
            term = f"{term}[Title/Abstract]"
        params = {
            "db": "pubmed",
            "term": term,
            "sort": "pub_date",
            "retmax": max_results,
            "retmode": "json",
            "email": self.email,
            "tool": self.tool_name,
        }
        try:
            resp = self.session.get(NCBI_ESEARCH_URL, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            id_list = data.get("esearchresult", {}).get("idlist", [])
            return id_list
        except Exception as e:
            print(f"[PubMed] Search error for query '{query}': {e}")
            return []

    def fetch_paper_details(self, pmids: List[str]) -> List[Dict[str, Any]]:
        """
        Fetch full metadata and abstract for a list of PMIDs using efetch XML.
        """
        if not pmids:
            return []

        params = {
            "db": "pubmed",
            "id": ",".join(pmids),
            "retmode": "xml",
            "email": self.email,
            "tool": self.tool_name
        }

        try:
            resp = self.session.get(NCBI_EFETCH_URL, params=params, timeout=25)
            resp.raise_for_status()
            return self._parse_pubmed_xml(resp.text)
        except Exception as e:
            print(f"[PubMed] Fetch details error: {e}")
            return []

    def _parse_pubmed_xml(self, xml_content: str) -> List[Dict[str, Any]]:
        papers = []
        try:
            root = ET.fromstring(xml_content)
            for article in root.findall(".//PubmedArticle"):
                try:
                    pmid = article.findtext(".//MedlineCitation/PMID")
                    if not pmid:
                        continue
                    
                    title = article.findtext(".//ArticleTitle") or "Untitled"
                    # Clean title brackets often seen in translated titles
                    title = title.strip().strip("[]")
                    
                    # Journal
                    journal = article.findtext(".//Journal/Title") or article.findtext(".//Journal/ISOAbbreviation") or "Unknown Journal"
                    
                    # Publication date
                    pub_date = "Unknown Date"
                    pub_date_el = article.find(".//JournalIssue/PubDate")
                    if pub_date_el is not None:
                        year = pub_date_el.findtext("Year") or ""
                        month = pub_date_el.findtext("Month") or ""
                        day = pub_date_el.findtext("Day") or ""
                        pub_date = f"{year} {month} {day}".strip()
                    if not pub_date or pub_date == "Unknown Date":
                        pub_date_elem = article.find(".//ArticleDate")
                        if pub_date_elem is not None:
                            year = pub_date_elem.findtext("Year") or ""
                            month = pub_date_elem.findtext("Month") or ""
                            day = pub_date_elem.findtext("Day") or ""
                            pub_date = f"{year}-{month}-{day}".strip()

                    # Authors
                    authors_list = []
                    for author in article.findall(".//AuthorList/Author"):
                        last_name = author.findtext("LastName") or ""
                        fore_name = author.findtext("ForeName") or author.findtext("Initials") or ""
                        if last_name or fore_name:
                            authors_list.append(f"{fore_name} {last_name}".strip())
                    authors = ", ".join(authors_list) if authors_list else "Unknown Authors"

                    # Abstract
                    abstract_texts = []
                    for abstract_el in article.findall(".//Abstract/AbstractText"):
                        label = abstract_el.get("Label")
                        text = "".join(abstract_el.itertext()).strip()
                        if label:
                            abstract_texts.append(f"**{label}**: {text}")
                        else:
                            abstract_texts.append(text)
                    abstract = "\n\n".join(abstract_texts) if abstract_texts else ""

                    # IDs (DOI, PMCID)
                    doi = None
                    pmcid = None
                    for article_id in article.findall(".//ArticleIdList/ArticleId"):
                        id_type = article_id.get("IdType")
                        val = (article_id.text or "").strip()
                        if id_type == "doi" and not doi:
                            doi = val
                        elif id_type == "pmc" and not pmcid:
                            pmcid = val if val.startswith("PMC") else f"PMC{val}"

                    papers.append({
                        "pmid": pmid,
                        "title": title,
                        "authors": authors,
                        "journal": journal,
                        "pub_date": pub_date,
                        "abstract": abstract,
                        "doi": doi,
                        "pmcid": pmcid,
                        "is_oa": pmcid is not None,
                        "pdf_url": None
                    })
                except Exception as parse_err:
                    print(f"[PubMed] Error parsing single article: {parse_err}")
                    continue
        except Exception as e:
            print(f"[PubMed] XML root parsing error: {e}")
        return papers

    def collect_pdf_candidates(
        self, pmid: str, pmcid: Optional[str] = None, doi: Optional[str] = None
    ) -> List[str]:
        """Collect candidate Open Access PDF URLs (Europe PMC, Unpaywall, Semantic Scholar)."""
        urls: List[str] = []
        seen = set()

        def add(url: Optional[str]):
            if not url:
                return
            url = url.strip()
            if url and url not in seen:
                seen.add(url)
                urls.append(url)

        try:
            params = {
                "query": f"EXT_ID:{pmid} src:med",
                "format": "json",
                "resultType": "core",
            }
            resp = self.session.get(EUROPE_PMC_SEARCH_URL, params=params, timeout=12)
            if resp.status_code == 200:
                results = resp.json().get("resultList", {}).get("result", [])
                if results:
                    res = results[0]
                    found_pmcid = res.get("pmcid")
                    if found_pmcid and not pmcid:
                        pmcid = found_pmcid
                    for u in res.get("fullTextUrlList", {}).get("fullTextUrl", []) or []:
                        style = (u.get("documentStyle") or "").lower()
                        href = u.get("url") or ""
                        if style == "pdf" or href.lower().endswith(".pdf"):
                            add(href)
        except Exception as e:
            print(f"[PubMed] Europe PMC resolution error for PMID {pmid}: {e}")

        if pmcid:
            clean_pmc = pmcid if str(pmcid).upper().startswith("PMC") else f"PMC{pmcid}"
            add(f"https://europepmc.org/backend/ptpmcrender.fcgi?accid={clean_pmc}&blobtype=pdf")
            add(f"https://europepmc.org/articles/{clean_pmc}?pdf=render")

        if doi:
            try:
                resp = self.session.get(
                    f"https://api.unpaywall.org/v2/{doi}",
                    params={"email": self.email},
                    timeout=10,
                )
                if resp.status_code == 200:
                    best_oa = resp.json().get("best_oa_location") or {}
                    add(best_oa.get("url_for_pdf"))
            except Exception as e:
                print(f"[PubMed] Unpaywall resolution error for DOI {doi}: {e}")

        try:
            resp = self.session.get(
                f"https://api.semanticscholar.org/graph/v1/paper/PMID:{pmid}",
                params={"fields": "openAccessPdf"},
                timeout=10,
            )
            if resp.status_code == 200:
                oa_pdf = resp.json().get("openAccessPdf") or {}
                add(oa_pdf.get("url"))
        except Exception:
            pass

        return urls

    def resolve_open_access_pdf_url(
        self, pmid: str, pmcid: Optional[str] = None, doi: Optional[str] = None
    ) -> Optional[str]:
        urls = self.collect_pdf_candidates(pmid=pmid, pmcid=pmcid, doi=doi)
        return urls[0] if urls else None

    def fetch_pmc_fulltext(self, pmcid: str) -> Optional[str]:
        """Fetch OA full text via Europe PMC JATS XML and flatten to plain text."""
        if not pmcid:
            return None
        clean = pmcid if str(pmcid).upper().startswith("PMC") else f"PMC{pmcid}"
        url = f"https://www.ebi.ac.uk/europepmc/webservices/rest/{clean}/fullTextXML"
        try:
            resp = self.session.get(url, timeout=20)
            if resp.status_code != 200 or not resp.text.strip().startswith("<"):
                return None
            return self._jats_to_text(resp.text)
        except Exception as e:
            print(f"[PubMed] PMC full-text XML error for {pmcid}: {e}")
            return None

    def _jats_to_text(self, xml_content: str) -> Optional[str]:
        try:
            root = ET.fromstring(xml_content)
        except ET.ParseError:
            return None

        parts: List[str] = []
        title = root.findtext(".//article-title")
        if title:
            parts.append(title.strip())

        for abstract in root.findall(".//abstract"):
            text = " ".join("".join(abstract.itertext()).split())
            if text:
                parts.append("Abstract\n" + text)

        for sec in root.findall(".//body//sec"):
            heading = sec.findtext("title") or ""
            paragraphs = []
            for p in sec.findall("p"):
                t = " ".join("".join(p.itertext()).split())
                if t:
                    paragraphs.append(t)
            body = "\n".join(paragraphs).strip()
            if heading or body:
                parts.append(f"{heading.strip()}\n{body}".strip())

        if len(parts) < 2:
            # Fallback: dump all body paragraphs
            for p in root.findall(".//body//p"):
                t = " ".join("".join(p.itertext()).split())
                if t:
                    parts.append(t)

        text = "\n\n".join(parts).strip()
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text if len(text) > 200 else None
