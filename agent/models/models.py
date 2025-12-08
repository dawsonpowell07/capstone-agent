from typing import Literal, Optional
from pydantic import BaseModel


class ChatRequest(BaseModel):
    """Simple chat request from frontend with just role and content"""
    role: Literal["user"]
    content: str
    userId: Optional[str] = None
    itineraryId: Optional[str] = None
