import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.api.endpoints import router as api_router
from app.db.sqlite import init_db
from app.config import settings
from app.core.summarizer import summarizer
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import uvicorn
from contextlib import asynccontextmanager

# Initialize Scheduler
scheduler = BackgroundScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    init_db()
    
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
