import secrets
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.tables import Event, Group, Hole, Player, EventStatus, EventFormat

router = APIRouter(prefix="/events", tags=["events"])


class CreateEventRequest(BaseModel):
    name: str
    date: date
    hole_count: int = 18
    format: str = "ambrose_4ball"


class CreateGroupRequest(BaseModel):
    name: str
    group_handicap: int = 0
    players: list[dict] = Field(default_factory=list)

    @field_validator("players", mode="before")
    @classmethod
    def validate_players(cls, v: Any) -> list[dict]:
        if not isinstance(v, list):
            return []
        return v

class UpdateHolesRequest(BaseModel):
    holes: list[dict]  # [{id: int, par: int}]


class UpdateGroupRequest(BaseModel):
    group_handicap: int = 0
    players: list[dict] = Field(default_factory=list)

    @field_validator("players", mode="before")
    @classmethod
    def validate_players(cls, v: Any) -> list[dict]:
        if not isinstance(v, list):
            return []
        return v

    def model_post_init(self, ctx: Any) -> None:
        scorers = sum(1 for p in self.players if isinstance(p, dict) and p.get("is_scorer", False))
        if len(self.players) < 2:
            raise ValueError("Group must have at least 2 players")
        if scorers != 1:
            raise ValueError("Group must have exactly 1 scorer")


class GroupResponse(BaseModel):
    id: int
    name: str
    group_handicap: int
    qr_token: str


class EventResponse(BaseModel):
    id: int
    name: str
    date: str
    hole_count: int
    format: str
    status: str
    join_code: str


@router.post("", response_model=EventResponse)
async def create_event(
    request: CreateEventRequest,
    db: AsyncSession = Depends(get_db),
):
    join_code = secrets.token_urlsafe(8)
    
    event = Event(
        name=request.name,
        date=request.date,
        hole_count=request.hole_count,
        format=EventFormat(request.format),
        join_code=join_code,
        status=EventStatus.draft,
    )
    db.add(event)
    await db.flush()
    
    for hole_num in range(1, request.hole_count + 1):
        hole = Hole(
            event_id=event.id,
            hole_number=hole_num,
            par=4,
        )
        db.add(hole)
    
    await db.commit()
    await db.refresh(event)
    
    return EventResponse(
        id=event.id,
        name=event.name,
        date=event.date.isoformat(),
        hole_count=event.hole_count,
        format=event.format.value,
        status=event.status.value,
        join_code=event.join_code,
    )


@router.post("/{event_id}/start")
async def start_event(
    event_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Event).where(Event.id == event_id)
    )
    event = result.scalar_one_or_none()
    
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    
    if event.status != EventStatus.draft:
        raise HTTPException(status_code=400, detail=f"Cannot start event in {event.status.value} status")
    
    event.status = EventStatus.active
    await db.commit()
    
    return {"message": "Event started", "status": "active"}


@router.post("/{event_id}/close")
async def close_event(
    event_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Event).where(Event.id == event_id)
    )
    event = result.scalar_one_or_none()
    
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    
    if event.status != EventStatus.active:
        raise HTTPException(status_code=400, detail=f"Cannot close event in {event.status.value} status")
    
    event.status = EventStatus.closed
    await db.commit()
    
    return {"message": "Event closed", "status": "closed"}


@router.post("/{event_id}/groups", response_model=GroupResponse)
async def create_group(
    event_id: int,
    request: CreateGroupRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Event).where(Event.id == event_id)
    )
    event = result.scalar_one_or_none()
    
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    
    qr_token = secrets.token_urlsafe(32)
    
    group = Group(
        event_id=event_id,
        name=request.name,
        group_handicap=request.group_handicap,
        qr_token=qr_token,
    )
    db.add(group)
    await db.flush()
    
    for idx, player_data in enumerate(request.players):
        player = Player(
            group_id=group.id,
            name=player_data.get("name", ""),
            handicap=player_data.get("handicap", 0),
            is_scorer=player_data.get("is_scorer", idx == 0),
        )
        db.add(player)
    
    await db.commit()
    await db.refresh(group)
    
    return GroupResponse(
        id=group.id,
        name=group.name,
        group_handicap=group.group_handicap,
        qr_token=group.qr_token,
    )


@router.get("/{event_id}")
async def get_event(
    event_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Event).where(Event.id == event_id)
    )
    event = result.scalar_one_or_none()
    
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    
    return {
        "id": event.id,
        "name": event.name,
        "date": event.date.isoformat(),
        "hole_count": event.hole_count,
        "format": event.format.value,
        "status": event.status.value,
        "join_code": event.join_code,
    }


@router.put("/{event_id}/holes")
async def update_holes(
    event_id: int,
    request: UpdateHolesRequest,
    db: AsyncSession = Depends(get_db),
):
    for hole_data in request.holes:
        result = await db.execute(
            select(Hole).where(Hole.id == hole_data["id"], Hole.event_id == event_id)
        )
        hole = result.scalar_one_or_none()
        if hole:
            hole.par = hole_data["par"]
    await db.commit()
    return {"message": "Holes updated"}


@router.put("/{event_id}/groups/{group_id}")
async def update_group(
    event_id: int,
    group_id: int,
    request: UpdateGroupRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Group).where(Group.id == group_id, Group.event_id == event_id)
    )
    group = result.scalar_one_or_none()
    if group is None:
        raise HTTPException(status_code=404, detail="Group not found")

    group.group_handicap = request.group_handicap

    # Replace players
    result = await db.execute(select(Player).where(Player.group_id == group_id))
    existing = result.scalars().all()
    for p in existing:
        await db.delete(p)
    await db.flush()

    for idx, pd in enumerate(request.players):
        player = Player(
            group_id=group_id,
            name=pd.get("name", ""),
            handicap=pd.get("handicap", 0),
            is_scorer=pd.get("is_scorer", idx == 0),
        )
        db.add(player)

    await db.commit()
    return {"message": "Group updated"}


@router.delete("/{event_id}/groups/{group_id}")
async def delete_group(
    event_id: int,
    group_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Group).where(Group.id == group_id, Group.event_id == event_id)
    )
    group = result.scalar_one_or_none()
    if group is None:
        raise HTTPException(status_code=404, detail="Group not found")
    await db.delete(group)
    await db.commit()
    return {"message": "Group deleted"}