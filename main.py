import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.api.endpoints import router as api_router
from app.db.sqlite import init_db, get_db_connection
from app.config import settings
from app.core.summarizer import summarizer
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from contextlib import asynccontextmanager
from datetime import datetime

# Initialize Scheduler
scheduler = BackgroundScheduler()

def record_system_event(event_key: str):
    """Record startup/shutdown timestamp to DB."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        cursor.execute(
            "INSERT OR REPLACE INTO system_state (key, value, updated_at) VALUES (?, ?, ?)",
            (event_key, now, now)
        )
        conn.commit()
        conn.close()
        return datetime.fromisoformat(now)
    except Exception as e:
        print(f"Error recording system event {event_key}: {e}")
        return None

def get_last_system_event(event_key: str):
    """Get last recorded timestamp for an event."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM system_state WHERE key = ?", (event_key,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return datetime.fromisoformat(row["value"])
        return None
    except Exception as e:
        print(f"Error getting system event {event_key}: {e}")
        return None

def check_missed_summaries():
    """Check if we missed any summary schedules during downtime."""
    print("Checking for missed summaries...")
    last_shutdown = get_last_system_event("last_shutdown")
    if not last_shutdown:
        print("No last shutdown record found. Skipping missed summary check.")
        return

    now = datetime.now()
    
    # Check if a Sunday 3AM passed between shutdown and now
    # Simple heuristic: If shutdown was before last Sunday 3AM and now is after, 
    # AND we haven't run it yet (which we can't easily track without job history, 
    # but running it again is idempotent-ish for weekly summary if date range is fixed).
    # Better approach: Just run the summary logic. The summarizer logic usually checks data.
    # Our summarizer generates summary for "last week".
    # If we missed Sunday, we should run it now.
    
    # Check if "Sunday" occurred in [last_shutdown, now]
    # This is a bit complex to calculate perfectly for all edge cases.
    # Simplified logic: If (now - last_shutdown) > 7 days, definitely run.
    # Or if today is e.g. Monday and last_shutdown was Saturday.
    
    # Let's use a robust way:
    # If the scheduled job time (Sunday 3AM) falls within the downtime window.
    # CronTrigger doesn't give us "next run time" from a past reference easily.
    
    # We will simply trigger a check. The summarizer generates summary for the *previous full week*.
    # If we run it multiple times for the same week, it might duplicate or overwrite.
    # Our `add_weekly_summary` inserts a new row. We should probably check if one exists first?
    # For MVP Phase 2, let's just run it if downtime > 1 day or cross-weekend.
    
    # 1. Weekly Check
    time_diff = now - last_shutdown
    if time_diff.total_seconds() > 86400: # Down for more than a day
        print("System was down for > 1 day. Triggering summary checks...")
        summarizer.run_all_weekly_summaries()
    elif last_shutdown.weekday() != 6 and now.weekday() == 0: # Shutdown before Sun, Up on Mon
         print("System crossed Sunday during downtime. Triggering weekly summary...")
         summarizer.run_all_weekly_summaries()

    # 2. Monthly Check (If crossed the 1st of month)
    # Check if month changed or year changed
    if (now.year > last_shutdown.year) or (now.month > last_shutdown.month):
        print("System crossed month boundary. Triggering monthly summary...")
        summarizer.run_all_monthly_summaries()

    # 3. Yearly Check (If crossed Jan 1st)
    if now.year > last_shutdown.year:
        print("System crossed year boundary. Triggering yearly summary...")
        summarizer.run_all_yearly_summaries()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    init_db()
    
    # Record Startup
    startup_time = record_system_event("last_startup")
    
    # Check for missed summaries
    check_missed_summaries()
    
    # Schedule Weekly Summary (Every Sunday at 3 AM)
    scheduler.add_job(
        summarizer.run_all_weekly_summaries,
        CronTrigger(day_of_week='sun', hour=3, minute=0),
        id='weekly_summary_job',
        replace_existing=True
    )
    
    # Schedule Monthly Summary (1st day of month at 3 AM)
    scheduler.add_job(
        summarizer.run_all_monthly_summaries,
        CronTrigger(day=1, hour=3, minute=0),
        id='monthly_summary_job',
        replace_existing=True
    )

    # Schedule Yearly Summary (Jan 1st at 3 AM)
    scheduler.add_job(
        summarizer.run_all_yearly_summaries,
        CronTrigger(month=1, day=1, hour=3, minute=0),
        id='yearly_summary_job',
        replace_existing=True
    )
    
    scheduler.start()
    
    yield
    
    # Shutdown logic
    record_system_event("last_shutdown")
    scheduler.shutdown()

app = FastAPI(title=f"Personal Agent {settings.bot_name} - Phase 2", lifespan=lifespan)

# Include API Router
app.include_router(api_router, prefix="/api")

# Mount Static Files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Serve Index
@app.get("/")
async def read_root():
    return FileResponse("app/static/index.html")

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
