import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional
import requests
import time

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
        params = {
            "db": "pubmed",
            "term": query,
            "sort": "pub_date",
            "retmax": max_results,
            "retmode": "json",
            "email": self.email,
            "tool": self.tool_name
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

    def resolve_open_access_pdf_url(self, pmid: str, pmcid: Optional[str] = None, doi: Optional[str] = None) -> Optional[str]:
        """
        Attempt to resolve direct Open Access PDF download URL from Europe PMC, NCBI PMC, or Unpaywall.
        """
        # 1. Check Europe PMC API
        try:
            query = f"EXT_ID:{pmid} src:med"
            params = {
                "query": query,
                "format": "json",
                "resultType": "core"
            }
            resp = self.session.get(EUROPE_PMC_SEARCH_URL, params=params, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                results = data.get("resultList", {}).get("result", [])
                if results:
                    res = results[0]
                    # Check for direct PDF links in fullTextUrlList
                    url_list = res.get("fullTextUrlList", {}).get("fullTextUrl", [])
                    for u in url_list:
                        if u.get("documentStyle") == "pdf" or u.get("url", "").lower().endswith(".pdf"):
                            return u.get("url")
                    
                    # If PMC ID is discovered
                    found_pmcid = res.get("pmcid")
                    if found_pmcid and not pmcid:
                        pmcid = found_pmcid
        except Exception as e:
            print(f"[PubMed] Europe PMC resolution error for PMID {pmid}: {e}")

        # 2. Check PMC direct link if PMCID exists
        if pmcid:
            clean_pmc = pmcid if pmcid.startswith("PMC") else f"PMC{pmcid}"
            # Europe PMC direct PDF download URL format
            europe_pmc_pdf = f"https://europepmc.org/backend/ptpmcrender.fcgi?accid={clean_pmc}&blobtype=pdf"
            return europe_pmc_pdf

        # 3. Check Unpaywall if DOI exists
        if doi:
            try:
                unpaywall_url = f"https://api.unpaywall.org/v2/{doi}?email={self.email}"
                resp = self.session.get(unpaywall_url, timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    best_oa = data.get("best_oa_location") or {}
                    pdf_url = best_oa.get("url_for_pdf")
                    if pdf_url:
                        return pdf_url
            except Exception as e:
                print(f"[PubMed] Unpaywall resolution error for DOI {doi}: {e}")

        # 4. Check Semantic Scholar
        try:
            ss_url = f"https://api.semanticscholar.org/graph/v1/paper/PMID:{pmid}?fields=openAccessPdf"
            resp = self.session.get(ss_url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                oa_pdf = data.get("openAccessPdf")
                if oa_pdf and oa_pdf.get("url"):
                    return oa_pdf.get("url")
        except Exception:
            pass

        return None
