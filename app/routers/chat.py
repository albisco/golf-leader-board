from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.tables import ChatMessage, Event, EventStatus
from app.services.ws_manager import ws_manager

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatMessageRequest(BaseModel):
    event_id: int
    sender_name: str
    content: str


class ChatMessageResponse(BaseModel):
    id: int
    event_id: int
    sender_name: str
    content: str


@router.post("", response_model=ChatMessageResponse)
async def send_chat_message(
    request: ChatMessageRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Event).where(Event.id == request.event_id)
    )
    event = result.scalar_one_or_none()
    
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    
    if event.status not in [EventStatus.active, EventStatus.closed]:
        raise HTTPException(status_code=400, detail="Event must be active or closed to post messages")
    
    message = ChatMessage(
        event_id=request.event_id,
        sender_name=request.sender_name,
        content=request.content,
    )
    db.add(message)
    await db.commit()
    await db.refresh(message)
    
    await ws_manager.broadcast(request.event_id, {
        "type": "chat",
        "message": {
            "id": message.id,
            "sender_name": message.sender_name,
            "content": message.content,
            "created_at": message.created_at.isoformat(),
        },
    })
    
    return ChatMessageResponse(
        id=message.id,
        event_id=message.event_id,
        sender_name=message.sender_name,
        content=message.content,
    )