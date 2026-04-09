from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import AsyncSessionLocal, get_db
from app.tables import Score, Event, Group, EventStatus
from app.services.leaderboard import get_leaderboard
from app.services.ws_manager import ws_manager

router = APIRouter(tags=["scores"])


class ScoreRequest(BaseModel):
    group_id: int
    hole_id: int
    gross_score: int


class ScoreResponse(BaseModel):
    id: int
    group_id: int
    hole_id: int
    gross_score: int
    edit_count: int


@router.post("/scores", response_model=ScoreResponse)
async def submit_score(
    request: ScoreRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Group).where(Group.id == request.group_id)
    )
    group = result.scalar_one_or_none()
    
    if group is None:
        raise HTTPException(status_code=404, detail="Group not found")
    
    result = await db.execute(
        select(Event).where(Event.id == group.event_id)
    )
    event = result.scalar_one_or_none()
    
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    
    if event.status != EventStatus.active:
        raise HTTPException(status_code=403, detail=f"Cannot submit scores for event in {event.status.value} status")
    
    if request.gross_score < 1:
        raise HTTPException(status_code=422, detail="gross_score must be positive")
    
    result = await db.execute(
        select(Score).where(
            Score.group_id == request.group_id,
            Score.hole_id == request.hole_id,
        )
    )
    existing_score = result.scalar_one_or_none()
    
    if existing_score:
        existing_score.gross_score = request.gross_score
        existing_score.edit_count += 1
        await db.commit()
        await db.refresh(existing_score)
        return ScoreResponse(
            id=existing_score.id,
            group_id=existing_score.group_id,
            hole_id=existing_score.hole_id,
            gross_score=existing_score.gross_score,
            edit_count=existing_score.edit_count,
        )
    
    score = Score(
        group_id=request.group_id,
        hole_id=request.hole_id,
        gross_score=request.gross_score,
    )
    db.add(score)
    await db.commit()
    await db.refresh(score)
    
    leaderboard_data = await get_leaderboard(db, event.id)
    await ws_manager.broadcast(event.id, leaderboard_data)
    
    return ScoreResponse(
        id=score.id,
        group_id=score.group_id,
        hole_id=score.hole_id,
        gross_score=score.gross_score,
        edit_count=score.edit_count,
    )


@router.get("/api/leaderboard/{event_id}")
async def get_leaderboard_api(
    event_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return await get_leaderboard(db, event_id)



@router.websocket("/ws/{event_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    event_id: int,
):
    await ws_manager.connect(event_id, websocket)
    try:
        async with AsyncSessionLocal() as db:
            leaderboard_data = await get_leaderboard(db, event_id)
        await websocket.send_json(leaderboard_data)

        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(event_id, websocket)