import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.api.endpoints import router as api_router
from app.db.sqlite import init_db
from app.config import settings

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    init_db()
    yield
    # Shutdown logic (if any)

app = FastAPI(title=f"Personal Agent {settings.bot_name} - MVP", lifespan=lifespan)

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
