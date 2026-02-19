from pydantic import BaseModel
from typing import List, Optional

class ChatRequest(BaseModel):
    user_id: str
    message: str
    context_flags: Optional[dict] = None  # New field for passing client-side context flags

class ChatResponse(BaseModel):
    response: str
    
class MemoryExtractRequest(BaseModel):
    user_id: str

class HistoryResponse(BaseModel):
    role: str
    content: str
    timestamp: str
