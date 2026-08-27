import json
import requests
from typing import List, Dict, Any, Optional
from datetime import datetime

class OllamaClient:
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama3", language: str = "zh-TW"):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.language = language

    def check_connection(self) -> Dict[str, Any]:
        """
        Check if Ollama is accessible and list installed models.
        """
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                models = [m.get("name") for m in data.get("models", [])]
                return {
                    "connected": True,
                    "models": models,
                    "current_model": self.model,
                    "model_available": any(self.model in m or m.startswith(self.model) for m in models)
                }
            return {"connected": False, "error": f"Status code {resp.status_code}", "models": []}
        except Exception as e:
            return {"connected": False, "error": str(e), "models": []}

    def generate(self, prompt: str, system: Optional[str] = None, timeout: int = 300) -> str:
        """
        Call Ollama generate API.
        """
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.3,
                "top_p": 0.9,
                "num_ctx": 8192
            }
        }
        if system:
            payload["system"] = system

        try:
            resp = requests.post(url, json=payload, timeout=timeout)
            resp.raise_for_status()
            data = resp.json()
            return data.get("response", "").strip()
        except requests.exceptions.ConnectionError:
            raise RuntimeError(f"無法連線至 Ollama ({self.base_url})，請確認 Ollama 服務是否已啟動 (ollama serve)。")
        except Exception as e:
            raise RuntimeError(f"Ollama 生成失敗: {e}")

    def analyze_single_paper(self, paper: Dict[str, Any], full_text: Optional[str] = None, system_prompt: Optional[str] = None) -> str:
        """
        Generate deep analysis for a single paper.
        """
        title = paper.get("title", "Untitled")
        authors = paper.get("authors", "Unknown")
        journal = paper.get("journal", "Unknown")
        pub_date = paper.get("pub_date", "Unknown")
        pmid = paper.get("pmid", "")
        doi = paper.get("doi", "")
        abstract = paper.get("abstract", "")

        content_source = "PDF 全文 (節錄)" if full_text else "PubMed 論文摘要 (Abstract)"
        content_body = full_text if full_text else abstract

        lang_instruction = "請使用繁體中文（台灣學術用語習慣）進行專業分析與撰寫。" if self.language == "zh-TW" else "請使用中文進行分析。"

        prompt = f"""
你是一位分子醫學與腫瘤生物學的專業文獻評析專家。
{lang_instruction}

以下是一篇關於 Galectin（半乳糖凝集素）的最新研究文獻資料：

- **標題 (Title)**: {title}
- **期刊 (Journal)**: {journal} ({pub_date})
- **作者 (Authors)**: {authors}
- **PMID**: {pmid} | **DOI**: {doi or 'N/A'}
- **內容來源**: {content_source}

【文獻內容】：
{content_body}

---
請針對本篇論文進行結構化深度剖析，包含以下面向：
1. **研究核心問題與背景**：作者試圖解決什麼科學問題？
2. **涉及之 Galectin 亞型與標靶**：例如 Galectin-1, Galectin-3, Galectin-9 等，及其在細胞或組織中的表現/角色。
3. **實驗設計與主要方法**：採用了哪些關鍵實驗（如細胞實驗、動物模型、臨床檢體、分子機制探討等）？
4. **關鍵發現與分子機轉 (Mechanism)**：發現了哪些重要訊息路徑（Signaling pathways）或交互作用？
5. **臨床轉化潛力與重要性**：此研究對診斷、標靶治療、免疫治療或抗藥性等帶來哪些啟示？
6. **研究亮點與局限性**：此論文最重要的貢獻與未來待釐清之處。

請直接以清晰的 Markdown 格式輸出該篇文獻的詳細分析報告。
"""
        return self.generate(prompt, system=system_prompt)

    def generate_comprehensive_report(self, papers: List[Dict[str, Any]], paper_analyses: List[str], 
                                      query_keyword: str = "galectin", system_prompt: Optional[str] = None) -> str:
        """
        Generate cross-paper literature review synthesis report.
        """
        today_str = datetime.now().strftime("%Y-%m-%d")
        lang_instruction = "請使用繁體中文（台灣學術用語習慣）進行完整撰寫。" if self.language == "zh-TW" else "請使用中文撰寫。"

        papers_summary_text = ""
        for i, (p, analysis) in enumerate(zip(papers, paper_analyses), 1):
            papers_summary_text += f"\n\n### 篇章 {i}: {p.get('title')}\n- **PMID**: {p.get('pmid')} | **期刊**: {p.get('journal')}\n{analysis}\n"

        prompt = f"""
你是一位生醫領域的頂尖首席科學家與綜述報告撰寫專家。
{lang_instruction}

今天是 {today_str}，我們追蹤了 PubMed 上關於【{query_keyword}】的最新 {len(papers)} 篇研究論文，並已完成各篇的初階分析：

{papers_summary_text}

---
請整合以上所有文獻，撰寫一份**高水準、結構嚴謹且具前瞻性的【每日 Galectin 研究動態與文獻綜述日報 (Daily Galectin Literature Digest)】**。

報告架構需包含：
# 📊 【Galectin 前沿研究動態每日綜述】 - {today_str}

## 🎯 執行摘要 (Executive Summary)
- 快速精煉今日文獻的核心焦點與重大突破（約 150-200 字）。

## 🔬 本期追蹤文獻概覽
- 條列今日納入分析的 {len(papers)} 篇文獻（附 PMID 與期刊）。

## 🧬 跨文獻深度剖析與分子機轉總結 (Cross-Study Synthesis & Molecular Mechanisms)
- 歸納今日文獻中探討之 Galectin 家族亞型（如 Gal-1/3/9 等）在不同疾病（如癌症、發炎、纖維化、免疫調節等）中的共性與特性。
- 梳理關鍵上下游分子訊號路徑與生化機制（包含與 Glycan 配體、細胞受體或免疫檢查點之交互作用）。

## 💡 臨床轉化、診斷與治療啟示 (Translational & Therapeutic Implications)
- 評估在藥物開發（如抑制劑、單株抗體、PROTAC）、生物標記（Biomarkers）及合併免疫療法上的潛力與挑戰。

## 🔭 未來研究展望與關鍵未解問題 (Future Perspectives & Open Questions)
- 綜合今日文獻提出後續值得深入探討的研究方向與實驗建議。

## 📑 逐篇文獻深度解讀 (Individual Paper Breakdown)
（此處請納入並潤飾前述各篇文獻的詳細分析）

---
請以高品質 Markdown 格式輸出，排版美觀、層次分明、專業嚴謹。
"""
        return self.generate(prompt, system=system_prompt)
