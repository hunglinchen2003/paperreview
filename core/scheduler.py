from datetime import datetime
from typing import Optional, Dict, Any
from zoneinfo import ZoneInfo
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from config import load_config
from .pipeline import runner

scheduler = BackgroundScheduler()
JOB_ID = "daily_pubmed_review_job"
TZ = ZoneInfo("Asia/Taipei")


def scheduled_task_wrapper():
    print(f"[{datetime.now()}] [Scheduler] Triggering daily PubMed review pipeline...")
    runner.start_pipeline_async()


def init_scheduler():
    cfg = load_config()
    if not scheduler.running:
        scheduler.start()
    update_job_schedule(cfg.schedule_enabled, cfg.schedule_hour, cfg.schedule_minute)


def update_job_schedule(enabled: bool, hour: int, minute: int):
    if scheduler.get_job(JOB_ID):
        scheduler.remove_job(JOB_ID)

    if enabled:
        trigger = CronTrigger(hour=hour, minute=minute, timezone=TZ)
        scheduler.add_job(
            scheduled_task_wrapper,
            trigger=trigger,
            id=JOB_ID,
            name="Daily PubMed Review",
            replace_existing=True,
        )
        print(f"[Scheduler] Daily job scheduled at {hour:02d}:{minute:02d} Asia/Taipei.")
    else:
        print("[Scheduler] Scheduled job is currently disabled.")


def get_scheduler_status() -> Dict[str, Any]:
    cfg = load_config()
    job = scheduler.get_job(JOB_ID)
    next_run = None
    if job and job.next_run_time:
        next_run = job.next_run_time.astimezone(TZ).strftime("%Y-%m-%d %H:%M:%S %Z")

    return {
        "is_running": scheduler.running,
        "enabled": cfg.schedule_enabled,
        "schedule_time": f"{cfg.schedule_hour:02d}:{cfg.schedule_minute:02d}",
        "timezone": "Asia/Taipei",
        "next_run_time": next_run,
    }
