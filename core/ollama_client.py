import re
import requests
from typing import List, Dict, Any, Optional
from datetime import datetime


THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


class OllamaClient:
    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "gpt-oss:20b",
        language: str = "bilingual",
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.language = language

    def check_connection(self) -> Dict[str, Any]:
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                models = [m.get("name") for m in data.get("models", [])]
                return {
                    "connected": True,
                    "models": models,
                    "current_model": self.model,
                    "model_available": any(
                        self.model == m or m.startswith(self.model) or self.model.startswith(m.split(":")[0])
                        for m in models
                    ),
                }
            return {"connected": False, "error": f"Status code {resp.status_code}", "models": []}
        except Exception as e:
            return {"connected": False, "error": str(e), "models": []}

    def _num_ctx(self) -> int:
        name = (self.model or "").lower()
        if "gpt-oss" in name or "20b" in name:
            return 16384
        return 8192

    def _clean_output(self, text: str) -> str:
        if not text:
            return ""
        text = THINK_RE.sub("", text)
        text = re.sub(r"<think>.*", "", text, flags=re.DOTALL | re.IGNORECASE)
        return text.strip()

    def generate(self, prompt: str, system: Optional[str] = None, timeout: int = 720) -> str:
        """
        Call Ollama. Prefer /api/chat (required for gpt-oss thinking models),
        then fall back to /api/generate.
        """
        options = {
            "temperature": 0.3,
            "top_p": 0.9,
            "num_ctx": self._num_ctx(),
        }
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        try:
            resp = requests.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": False,
                    "keep_alive": "30m",
                    "options": options,
                },
                timeout=timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            message = data.get("message") or {}
            content = message.get("content") or data.get("response") or ""
            cleaned = self._clean_output(content)
            if cleaned:
                return cleaned
            # Some gpt-oss builds put the answer only in thinking
            thinking = self._clean_output(message.get("thinking") or "")
            if thinking:
                return thinking
        except requests.exceptions.ConnectionError:
            raise RuntimeError(
                f"無法連線至 Ollama ({self.base_url})，請確認 Ollama 服務是否已啟動 (ollama serve)。"
            )
        except Exception as chat_err:
            print(f"[Ollama] /api/chat failed, trying /api/generate: {chat_err}")

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "keep_alive": "30m",
            "options": options,
        }
        if system:
            payload["system"] = system
        try:
            resp = requests.post(f"{self.base_url}/api/generate", json=payload, timeout=timeout)
            resp.raise_for_status()
            data = resp.json()
            return self._clean_output(data.get("response") or "")
        except requests.exceptions.ConnectionError:
            raise RuntimeError(
                f"無法連線至 Ollama ({self.base_url})，請確認 Ollama 服務是否已啟動 (ollama serve)。"
            )
        except Exception as e:
            raise RuntimeError(f"Ollama 生成失敗: {e}")

    def analyze_single_paper(
        self,
        paper: Dict[str, Any],
        full_text: Optional[str] = None,
        system_prompt: Optional[str] = None,
        query_keyword: str = "galectin",
    ) -> str:
        title = paper.get("title", "Untitled")
        authors = paper.get("authors", "Unknown")
        journal = paper.get("journal", "Unknown")
        pub_date = paper.get("pub_date", "Unknown")
        pmid = paper.get("pmid", "")
        doi = paper.get("doi") or "N/A"
        abstract = paper.get("abstract", "")
        source = paper.get("full_text_source") or ("pdf" if full_text else "abstract")
        content_source = {
            "pdf": "PDF full text (excerpt)",
            "pmc_xml": "PMC / Europe PMC full text XML",
            "jats": "PMC / Europe PMC full text XML",
        }.get(source, "PubMed abstract")
        content_body = full_text if full_text else abstract

        prompt = f"""You are a biomedical literature analyst specializing in {query_keyword}.

Paper metadata (cite these exactly; do not invent identifiers):
- Title: {title}
- Journal: {journal}
- Publication date: {pub_date}
- Authors: {authors}
- PMID: {pmid} (https://pubmed.ncbi.nlm.nih.gov/{pmid}/)
- DOI: {doi}
- Content source: {content_source}

DOCUMENT:
{content_body}

Write TWO sections, in this exact order:

## 中文分析
Use Traditional Chinese (Taiwan academic style). Cover:
1. 研究問題與背景
2. 與 {query_keyword} 的關聯（亞型／分子角色）
3. 實驗設計與方法
4. 關鍵發現與機轉
5. 臨床或轉化意義
6. 限制與亮點

## English analysis
The same six points in English (research question, relation to {query_keyword}, methods, key findings, translational relevance, limitations).

Do not invent PMIDs, journals, or dates. Output Markdown only.
"""
        return self.generate(prompt, system=system_prompt)

    def generate_zh_digest(
        self,
        papers: List[Dict[str, Any]],
        paper_analyses: List[str],
        query_keyword: str,
        system_prompt: Optional[str] = None,
    ) -> str:
        today_str = datetime.now().strftime("%Y-%m-%d")
        body = self._analysis_bundle(papers, paper_analyses)
        prompt = f"""你是生醫綜述撰寫者。今天是 {today_str}，主題是「{query_keyword}」。

以下是今日納入的文獻書目與各篇分析：
{body}

請用**繁體中文**撰寫今日綜述，結構如下（不要重複貼上書目表格，來源索引已另外附上）：

# 中文綜述 — {today_str}

## 執行摘要
約 150–200 字。

## 跨文獻重點與分子機轉
## 臨床／轉化啟示
## 未解問題與展望
## 逐篇重點（每篇 5–8 行，標題用原文）

語氣專業、客觀。不要杜撰 PMID、期刊或日期。
"""
        return self.generate(prompt, system=system_prompt)

    def generate_en_digest(
        self,
        papers: List[Dict[str, Any]],
        paper_analyses: List[str],
        query_keyword: str,
        system_prompt: Optional[str] = None,
    ) -> str:
        today_str = datetime.now().strftime("%Y-%m-%d")
        body = self._analysis_bundle(papers, paper_analyses)
        prompt = f"""You are a biomedical review writer. Today is {today_str}. Topic: {query_keyword}.

Papers and analyses:
{body}

Write an English daily digest with this structure (do NOT repeat the source table; it is provided separately):

# English Digest — {today_str}

## Executive summary
About 150–200 words.

## Cross-paper synthesis and mechanisms
## Translational and clinical implications
## Open questions
## Per-paper highlights (5–8 lines each, keep original titles)

Be precise. Do not invent PMIDs, journals, or dates.
"""
        return self.generate(prompt, system=system_prompt)

    def generate_comprehensive_report(
        self,
        papers: List[Dict[str, Any]],
        paper_analyses: List[str],
        query_keyword: str = "galectin",
        system_prompt: Optional[str] = None,
    ) -> str:
        """Backward-compatible wrapper: bilingual digest concatenated."""
        zh = self.generate_zh_digest(papers, paper_analyses, query_keyword, system_prompt)
        en = self.generate_en_digest(papers, paper_analyses, query_keyword, system_prompt)
        return zh + "\n\n---\n\n" + en

    def _analysis_bundle(self, papers: List[Dict[str, Any]], paper_analyses: List[str]) -> str:
        chunks = []
        for i, (p, analysis) in enumerate(zip(papers, paper_analyses), 1):
            pmid = p.get("pmid")
            chunks.append(
                f"### Paper {i}\n"
                f"- Title: {p.get('title')}\n"
                f"- Journal: {p.get('journal')} | Date: {p.get('pub_date')}\n"
                f"- PMID: {pmid} | https://pubmed.ncbi.nlm.nih.gov/{pmid}/\n"
                f"- DOI: {p.get('doi') or 'N/A'}\n"
                f"{analysis}\n"
            )
        return "\n".join(chunks)
