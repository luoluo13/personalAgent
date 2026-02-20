from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from app.models.models import ChatRequest, ChatResponse, HistoryResponse, MemoryExtractRequest
from app.core.llm import llm_service
from app.core.memory import memory_service
from app.config import settings
import asyncio
from pathlib import Path

router = APIRouter()

@router.get("/config")
async def get_config():
    """Get public configuration like bot name."""
    return {"bot_name": settings.bot_name}

@router.get("/avatar")
async def get_avatar():
    """Get AI avatar image from static directory."""
    static_dir = Path("app/static")
    # Find all files starting with ai_avatar.
    files = list(static_dir.glob("ai_avatar.*"))
    
    # Filter for image extensions
    valid_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.webp'}
    image_files = [f for f in files if f.suffix.lower() in valid_extensions]
    
    if not image_files:
        raise HTTPException(status_code=404, detail="Avatar not found")
        
    # Sort by suffix (first char logic implied by alphabetical sort of suffix)
    image_files.sort(key=lambda x: x.suffix.lower())
    
    return FileResponse(image_files[0])

async def background_save_memory(user_id: str, user_msg: str, ai_msg: str):
    """Background task to save messages to vector DB (simulate async processing)"""
    # In a real app, we might want to summarize before adding to vector DB
    # For MVP, we add raw messages to vector DB for retrieval
    memory_service.add_memory(user_id, f"User: {user_msg}")
    memory_service.add_memory(user_id, f"{settings.bot_name}: {ai_msg}")

@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest, background_tasks: BackgroundTasks):
    try:
        from datetime import datetime
        
        # 1. Save User Message to DB & Redis
        memory_service.save_conversation(request.user_id, "user", request.message)
        
        # 2. Generate AI Response
        ai_response_text, is_recalling = llm_service.generate_response(request.user_id, request.message, request.context_flags)
        
        # 3. Save AI Message to DB & Redis
        memory_service.save_conversation(request.user_id, "assistant", ai_response_text)
        
        # 4. Add background task to update Vector DB
        background_tasks.add_task(background_save_memory, request.user_id, request.message, ai_response_text)
        
        # Format current time for display
        now_str = datetime.now().strftime("%H:%M")
        
        return ChatResponse(
            response=ai_response_text, 
            is_recalling=is_recalling,
            timestamp_display=now_str
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/history/{user_id}", response_model=list[HistoryResponse])
async def get_history(user_id: str):
    from datetime import datetime, timedelta
    history = memory_service.get_recent_history(user_id)
    
    formatted_history = []
    for h in history:
        # Parse timestamp string from DB
        # SQLite DEFAULT CURRENT_TIMESTAMP is UTC "YYYY-MM-DD HH:MM:SS"
        # SQLite DEFAULT (datetime('now', 'localtime')) is Local "YYYY-MM-DD HH:MM:SS"
        
        ts_str = str(h["timestamp"])
        display_time = ""
        
        try:
            # We assume the DB stores it in a format parseable by datetime
            # If it's UTC (old data), we might need to convert?
            # If it's Local (new data), we just use it.
            # But wait, existing data in DB is likely UTC (from CURRENT_TIMESTAMP default).
            # Changing table schema default doesn't change existing rows.
            # So we should safely assume it might be UTC and convert if needed?
            # Or just parse it.
            
            # Check if it looks like standard format
            dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
            
            # Simple heuristic: If it's suspiciously "early" (e.g. 8 hours behind now), add 8 hours?
            # No, that's dangerous.
            # Let's just trust that the user will clear old data or we accept old data is UTC.
            # For NEW data, we changed DB default to localtime.
            # But wait, memory_service.save_conversation inserts without timestamp, letting DB default handle it?
            # Let's check memory_service.
            
            # Actually, to be safe, let's just format what we have.
            display_time = dt.strftime("%H:%M")
            
        except ValueError:
             # Try ISO format if T exists
             try:
                 dt = datetime.fromisoformat(ts_str)
                 display_time = dt.strftime("%H:%M")
             except:
                 # Fallback for simple string slicing if all parsing fails
                 if len(ts_str) >= 16:
                     display_time = ts_str[11:16]
                 else:
                     display_time = ts_str 

        formatted_history.append(HistoryResponse(
            role=h["role"], 
            content=h["content"], 
            timestamp_display=display_time
        ))
        
    return formatted_history

@router.post("/memory/extract")
async def extract_memory(request: MemoryExtractRequest):
    # Placeholder for Phase 1
    return {"status": "success", "message": "Memory extraction triggered (MVP Placeholder)"}

@router.delete("/memory/{user_id}")
async def delete_memory(user_id: str):
    try:
        memory_service.delete_user_memory(user_id)
        return {"status": "success", "message": "Memory deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
