import os
import json
from pathlib import Path
from typing import Optional
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent
CONFIG_FILE = BASE_DIR / "config.json"
DATA_DIR = BASE_DIR / "data"

class AppConfig(BaseModel):
    # PubMed Settings
    pubmed_query: str = "galectin"
    max_papers_per_run: int = 5
    email_for_ncbi: str = "user@example.com"  # Recommended by NCBI
    
    # Scheduler Settings
    schedule_enabled: bool = True
    schedule_hour: int = 2
    schedule_minute: int = 0
    
    # Ollama Settings
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3"
    report_language: str = "zh-TW"  # zh-TW, zh-CN, en
    system_prompt: str = (
        "你是一位專精於生醫分子生物學與腫瘤免疫學的資深研究員。"
        "請根據提供的最新文獻全文/摘要，深入分析研究動態，總結關鍵機轉、實驗設計、重要發現與臨床應用潛力，"
        "並撰寫一份結構完整、客觀且具深度專業性的綜述報告。"
    )
    
    # GitHub Pages Settings
    github_enabled: bool = True
    github_token: str = ""
    github_repo: str = "hunglinchen2003/paperreview"  # e.g., "username/galectin-daily-digest" or "username/username.github.io"
    github_branch: str = "main"
    github_folder: str = "docs"  # docs/ for GitHub Pages
    
    # Storage Paths
    data_dir: str = str(DATA_DIR)

def load_config() -> AppConfig:
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return AppConfig(**data)
        except Exception as e:
            print(f"[Config] Error loading config.json: {e}, using defaults.")
    
    # Create default config if not exists
    config = AppConfig()
    save_config(config)
    return config

def save_config(config: AppConfig):
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config.model_dump(), f, indent=4, ensure_ascii=False)
