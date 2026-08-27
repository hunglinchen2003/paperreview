import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any

# Ensure standard UTF-8 output on Windows console
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from fastapi import FastAPI, Request, Form, BackgroundTasks, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from config import load_config, save_config, AppConfig, BASE_DIR
from core.database import Database
from core.pipeline import runner
from core.scheduler import init_scheduler, get_scheduler_status, update_job_schedule
from core.ollama_client import OllamaClient
from core.github_publisher import GitHubPublisher

app = FastAPI(title="Galectin Literature Review WebUI", version="1.0.0")

# Setup directories
STATIC_DIR = BASE_DIR / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
TEMPLATES_DIR = BASE_DIR / "templates"
TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
DOCS_DIR = BASE_DIR / "docs"
DOCS_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/docs-site", StaticFiles(directory=str(DOCS_DIR), html=True), name="docs_site")

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
db = Database()

@app.on_event("startup")
async def startup_event():
    # Initialize background scheduler
    init_scheduler()
    db.log("INFO", "🌟 WebUI 伺服器與每日自動排程已啟動。")

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

@app.get("/api/status")
async def get_system_status():
    runner_status = runner.get_status()
    scheduler_status = get_scheduler_status()
    total_papers = db.get_total_paper_count()
    reports = db.get_reports(limit=5)
    
    cfg = load_config()
    ollama = OllamaClient(base_url=cfg.ollama_base_url, model=cfg.ollama_model)
    ollama_status = ollama.check_connection()

    return JSONResponse({
        "runner": runner_status,
        "scheduler": scheduler_status,
        "total_papers": total_papers,
        "recent_reports_count": len(reports),
        "ollama": ollama_status,
        "config": cfg.model_dump()
    })

@app.post("/api/run")
async def trigger_run(custom_query: Optional[str] = None, max_papers: Optional[int] = None):
    started = runner.start_pipeline_async(custom_query=custom_query, max_papers=max_papers)
    if not started:
        return JSONResponse({"success": False, "message": "任務已在執行中，請稍候！"}, status_code=400)
    return JSONResponse({"success": True, "message": "已成功啟動文獻搜尋與分析流程！"})

@app.get("/api/config")
async def get_configuration():
    return JSONResponse(load_config().model_dump())

@app.post("/api/config")
async def update_configuration(new_config: AppConfig):
    save_config(new_config)
    # Update scheduler trigger
    update_job_schedule(new_config.schedule_enabled, new_config.schedule_hour, new_config.schedule_minute)
    db.log("INFO", "⚙️ 系統設定已更新並同步套用。")
    return JSONResponse({"success": True, "message": "設定已成功儲存！"})

@app.get("/api/papers")
async def list_papers(limit: int = 50, offset: int = 0):
    papers = db.get_papers(limit=limit, offset=offset)
    total = db.get_total_paper_count()
    return JSONResponse({"total": total, "papers": papers})

@app.get("/api/papers/{pmid}")
async def get_paper(pmid: str):
    paper = db.get_paper_by_pmid(pmid)
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    return JSONResponse(paper)

@app.get("/api/papers/{pmid}/pdf")
async def get_paper_pdf(pmid: str):
    paper = db.get_paper_by_pmid(pmid)
    if not paper or not paper.get("pdf_path"):
        raise HTTPException(status_code=404, detail="PDF file not found")
    
    path = Path(paper["pdf_path"])
    if not path.exists():
        raise HTTPException(status_code=404, detail="PDF file does not exist on disk")
    
    return FileResponse(
        path=str(path),
        media_type="application/pdf",
        filename=f"PubMed_{pmid}.pdf"
    )

@app.get("/api/papers/{pmid}/text")
async def get_paper_text(pmid: str):
    paper = db.get_paper_by_pmid(pmid)
    if not paper or not paper.get("text_path"):
        raise HTTPException(status_code=404, detail="Extracted text not found")
    
    path = Path(paper["text_path"])
    if not path.exists():
        raise HTTPException(status_code=404, detail="Text file does not exist on disk")
    
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    return JSONResponse({"pmid": pmid, "content": content})

@app.get("/api/reports")
async def list_reports(limit: int = 50):
    reports = db.get_reports(limit=limit)
    return JSONResponse(reports)

@app.get("/api/reports/{report_id}")
async def get_report_detail(report_id: int):
    report = db.get_report_by_id(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return JSONResponse(report)

@app.get("/api/logs")
async def get_logs(limit: int = 100):
    logs = db.get_logs(limit=limit)
    return JSONResponse(logs)

@app.get("/api/ollama/test")
async def test_ollama(base_url: Optional[str] = None, model: Optional[str] = None):
    cfg = load_config()
    client = OllamaClient(
        base_url=base_url or cfg.ollama_base_url,
        model=model or cfg.ollama_model
    )
    result = client.check_connection()
    return JSONResponse(result)

@app.post("/api/github/test")
async def test_github(token: Optional[str] = None, repo: Optional[str] = None, branch: Optional[str] = None):
    cfg = load_config()
    pub = GitHubPublisher(
        token=token if token is not None else cfg.github_token,
        repo=repo if repo is not None else cfg.github_repo,
        branch=branch if branch is not None else cfg.github_branch
    )
    res = pub.test_connection()
    return JSONResponse(res)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
