# 🧬 Galectin 文獻自動追蹤與 Ollama 綜述系統 (WebUI)

專為生物醫學研究人員打造的全自動化文獻追蹤與綜述生成系統。系統每天清晨 **02:00 AM** 自動檢索 PubMed 最新發表的 Galectin（半乳糖凝集素）相關文獻，自動過濾歷史重複文章、下載 Open Access PDF 全文、轉換純文字，並調用本地 **Ollama LLM** 進行專業學術剖析與整合綜述，最終自動發布至 **GitHub Pages** 個人專屬學術網站。

---

## 🌟 核心功能特色

1. **⏰ 每日定時自動執行 (02:00 AM)**：
   - 內建背景排程器（APScheduler），每日清晨自動運行，無需人工介入。
   - 支援在 WebUI 隨時手動自訂排程時間或一鍵手動觸發執行。

2. **🔍 PubMed 智能檢索與去重機制**：
   - 即時檢索 NCBI PubMed 最新發表的文獻。
   - 內建 SQLite 資料庫自動記錄所有處理過的 PMID 與 DOI，**保證每日 5 篇文獻絕不重複**。

3. **📥 Open Access PDF 全文下載與解析**：
   - 整合 Europe PMC、PubMed Central (PMC) 與 Unpaywall 多重開放存取解析器，自動下載 OA PDF 全文至本地 `data/pdfs/`。
   - 若文獻為付費牆論文，自動降級解析結構化 PubMed Abstract 摘要。

4. **📄 高精度 PDF to Text 轉換**：
   - 採用高效能 `PyMuPDF (fitz)` 與 `pypdf` 進行學術論文文字抽取與格式清理（自動修復換行破折號、去除過長參考文獻噪音）。

5. **🤖 調用本地 Ollama 深度學術分析**：
   - 支援呼叫本機 Ollama 模型（如 `llama3`、`qwen2.5`、`deepseek-r1`、`mistral` 等）。
   - **單篇深度剖析**：分析研究背景、涉及之 Galectin 亞型（Gal-1, Gal-3, Gal-9 等）、實驗設計、訊號傳遞路徑（Signaling pathways）、臨床轉化與治療潛力。
   - **跨文獻綜合綜述**：整合當日所有文獻，撰寫結構嚴謹的每日綜述日報（Daily Literature Digest）。

6. **🌐 GitHub Pages 自動發布**：
   - 自動生成美觀響應式 Markdown 與獨立 HTML 網頁。
   - 自動維護總覽首頁 `index.html`（具備即時搜尋與文章過濾功能）。
   - 透過 GitHub API 自動推送至您的 GitHub 倉庫，實現 GitHub Pages 線上即時瀏覽。

7. **💻 現代化 Web UI 管理面板**：
   - 採用 FastAPI + Tailwind CSS + Alpine.js 開發。
   - 具備總覽儀表板、文獻庫搜尋與 PDF 下載閱讀器、歷史日報閱讀器、即時系統日誌與可視化設定面板。

---

## 🏗️ 系統架構

```
[ PubMed NCBI API ] ───> [ PMID 搜尋與 SQLite 去重 ] ───> [ 取出 5 篇新文獻 ]
                                                                 │
                                                                 ▼
[ 提取純文字 data/texts/ ] <─── [ PDF to Text (PyMuPDF) ] <─── [ OA PDF 下載 (PMC / Europe PMC) ]
         │
         ▼
[ Ollama 本地模型 (LLM) ] ───> [ 逐篇深度解析 & 跨文獻綜述日報 ]
                                              │
                                              ▼
[ 儲存資料庫 & 產生 HTML ] ───> [ GitHub API 推送至 GitHub Pages ]
                                              │
                                              ▼
                                   [ WebUI 即時檢視與管理 ]
```

---

## 🚀 快速開始

### 1. 環境需求
- **作業系統**：Windows 10/11, macOS 或 Linux
- **Python**：3.9 以上
- **Ollama**：本機已安裝並啟動 Ollama（[官網下載](https://ollama.com/)）
  ```bash
  # 拉取推薦模型（可任選一款）
  ollama pull llama3
  # 或
  ollama pull qwen2.5
  ```

### 2. 安裝依賴
在專案目錄下打開終端機執行：
```bash
pip install -r requirements.txt
```

### 3. 啟動 WebUI
- **Windows 用戶**：直接雙擊執行 `run.bat`
- **命令列啟動**：
  ```bash
  python app.py
  ```

開啟瀏覽器前往：**`http://127.0.0.1:8000`**

---

## ⚙️ 系統設定指南 (在 WebUI 中配置)

開啟 WebUI 後進入 **「系統設定」** 分頁：

### 1. PubMed 與排程設定
- **檢索關鍵字**：預設為 `galectin`（可自訂如 `galectin-3 inhibitor` 等）。
- **目標篇數**：預設為 `5` 篇。
- **每日排程時間**：預設為 `02:00`（可自行調整時與分）。
- **啟用排程**：勾選後將在每天指定時間自動運作。

### 2. Ollama 模型設定
- **Ollama API 位址**：預設 `http://localhost:11434`。
- **選擇模型**：點擊「測試連線與載入可用模型」即可自動抓取本機已安裝的 Ollama 模型（如 `llama3`, `qwen2.5:14b`, `deepseek-r1`）。
- **語言**：預設為繁體中文學術用語。

### 3. GitHub Pages 自動發布設定 (選填)
若想讓報告自動發布至公開或私人 GitHub 網頁：
1. **GitHub Token (PAT)**：
   - 前往 GitHub ➔ Settings ➔ Developer Settings ➔ Personal Access Tokens (Classic)。
   - 勾選 `repo` 權限並複製 Token。
2. **倉庫名稱**：填入 `你的帳號/倉庫名`（例如 `yourname/galectin-digest` 或 `yourname/yourname.github.io`）。
3. **分支與路徑**：分支填 `main` 或 `gh-pages`，資料夾填 `docs`。
4. **開啟 GitHub Pages**：
   - 在該 GitHub 倉庫的 Settings ➔ Pages 中，將 Source 設定為 `Deploy from a branch`，Branch 選擇 `main` / `docs` 資料夾即可！
5. 點擊 **「測試 GitHub 連線」** 驗證權限。

> 💡 **提示**：即使未配置 GitHub Token，所有生成的報告與首頁仍會完整保存在本地 `docs/` 資料夾中，您也可以在 WebUI 內直接點擊「預覽本地 Pages」閱讀！

---

## 📂 專案檔案結構

```
文獻回顧/
├── app.py                      # FastAPI 主程式與 Web 路由
├── config.py                   # 設定檔管理
├── config.json                 # 系統設定檔（儲存關鍵字、排程、金鑰等）
├── requirements.txt            # Python 套件依賴
├── run.bat                     # Windows 一鍵啟動腳本
├── core/
│   ├── pubmed.py               # PubMed 檢索與 Europe PMC/Unpaywall OA 解析
│   ├── downloader.py           # PDF 全文下載與格式驗證
│   ├── pdf_extractor.py        # PDF 轉文字 (PyMuPDF / pypdf) 與文字清理
│   ├── ollama_client.py        # Ollama LLM 串接與學術綜述 Prompt
│   ├── github_publisher.py     # GitHub Pages 自動發布與 HTML 生成
│   ├── scheduler.py            # APScheduler 每日定時排程 (02:00)
│   ├── database.py             # SQLite 資料庫（文獻去重、歷史日報、日誌）
│   └── pipeline.py             # 自動化流水線排程協調器
├── templates/
│   └── index.html              # 現代化 WebUI 儀表板前端
├── data/                       # 本地資料存放目錄
│   ├── papers.db               # SQLite 資料庫檔案
│   ├── pdfs/                   # 下載之 PDF 全文
│   └── texts/                  # 抽取之純文字檔案
└── docs/                       # 靜態網站目錄（供 GitHub Pages 發布與本地預覽）
    ├── index.html              # 歷史報告總覽首頁
    └── reports/                # 每日生成的 Markdown 與 HTML 報告
```

---

## ❓ 常見問題 (FAQ)

**Q1：如何確認每天早上 2 點有沒有自動執行？**  
A：請保持 `app.py`（或 `run.bat`）在背景持續執行。您可以在 WebUI 的「總覽」分頁查看下次執行時間，或在「運行日誌」分頁查閱每日執行的詳細記錄。

**Q2：如果某一篇文章沒有 Open Access PDF 下載連結怎麼辦？**  
A：系統具備彈性容錯機制，若該論文受到出版社付費牆限制，系統會自動抓取 PubMed 官方提供的結構化 Abstract 摘要，並傳遞給 Ollama 進行分析，確保綜述報告不中斷。

**Q3：我想手動測試執行，不想等到凌晨 2 點？**  
A：在 WebUI 首頁點擊 **「立即手動執行 (Run Now)」** 按鈕，系統就會立刻在背景執行檢索、下載、解析、LLM 撰寫與發布流程，並可即時在畫面上看到進度條。
