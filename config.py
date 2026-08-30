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
    ollama_model: str = "gpt-oss:20b"
    report_language: str = "bilingual"
    timezone: str = "Asia/Taipei"
    system_prompt: str = (
        "You are a senior biomedical researcher specializing in molecular biology and galectin biology. "
        "Analyze the provided full text or abstract carefully. Write both Traditional Chinese and English. "
        "Never invent PubMed IDs, journals, or publication dates."
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
