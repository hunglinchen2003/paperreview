"""Run one PubMed → Ollama → GitHub digest cycle (for Windows Task Scheduler)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.pipeline import runner

if __name__ == "__main__":
    result = runner.run_once()
    print(result)
    raise SystemExit(0 if result.get("success") else 1)
