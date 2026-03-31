# Template source: seleniumbase/seleniumbase | Difficulty: hard | Niche: web
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from config import SCHEDULE_CRON
from automation import run_automation

scheduler = AsyncIOScheduler()

def start():
    cron_parts = SCHEDULE_CRON.split()
    scheduler.add_job(
        run_automation,
        "cron",
        minute=cron_parts[0], hour=cron_parts[1],
        day=cron_parts[2], month=cron_parts[3], day_of_week=cron_parts[4]
    )
    scheduler.start()
    print(f"Scheduler started | cron: {SCHEDULE_CRON}")
