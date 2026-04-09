from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.tables import ChatMessage, Event, EventStatus, Group, Hole, Score
from app.templates import templates

router = APIRouter(tags=["pages"])


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")


@router.get("/create-event", response_class=HTMLResponse)
async def create_event_page(request: Request):
    return templates.TemplateResponse(request=request, name="create_event.html")


@router.get("/event/{event_id}/setup", response_class=HTMLResponse)
async def event_setup_page(event_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    result = await db.execute(
        select(Group).options(selectinload(Group.players)).where(Group.event_id == event_id)
    )
    groups = result.scalars().all()

    result = await db.execute(select(Hole).where(Hole.event_id == event_id))
    holes = result.scalars().all()

    return templates.TemplateResponse(request=request, name="event_setup.html", context={
        "event": {
            "id": event.id,
            "name": event.name,
            "date": event.date.isoformat() if event.date else "",
            "status": event.status.value,
            "hole_count": event.hole_count,
        },
        "groups": [
            {
                "id": g.id,
                "name": g.name,
                "group_handicap": g.group_handicap,
                "qr_token": g.qr_token,
                "players": [{"name": p.name, "handicap": p.handicap, "is_scorer": p.is_scorer} for p in g.players],
            }
            for g in groups
        ],
        "holes": [{"id": h.id, "hole_number": h.hole_number, "par": h.par} for h in holes],
    })


@router.get("/score/{scorer_token}", response_class=HTMLResponse)
async def score_entry_page(scorer_token: str, request: Request, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Group).options(selectinload(Group.players)).where(Group.qr_token == scorer_token)
    )
    group = result.scalar_one_or_none()
    if group is None:
        raise HTTPException(status_code=404, detail="Invalid scorer token")

    result = await db.execute(select(Event).where(Event.id == group.event_id))
    event = result.scalar_one_or_none()

    result = await db.execute(select(Hole).where(Hole.event_id == event.id))
    holes = result.scalars().all()

    result = await db.execute(
        select(Score).options(selectinload(Score.hole)).where(Score.group_id == group.id)
    )
    scores = result.scalars().all()

    scores_by_hole = {
        s.hole.hole_number: {"gross_score": s.gross_score, "edit_count": s.edit_count}
        for s in scores
    }

    holes_played = len(scores)
    gross_total = sum(s.gross_score for s in scores)
    net_total = gross_total - group.group_handicap if holes_played == event.hole_count else None

    return templates.TemplateResponse(request=request, name="score_entry.html", context={
        "event": {
            "id": event.id,
            "name": event.name,
            "date": event.date.isoformat() if event.date else "",
            "hole_count": event.hole_count,
            "status": event.status.value,
        },
        "group": {
            "id": group.id,
            "name": group.name,
            "group_handicap": group.group_handicap,
            "players": [{"name": p.name, "handicap": p.handicap, "is_scorer": p.is_scorer} for p in group.players],
        },
        "holes": [{"id": h.id, "hole_number": h.hole_number, "par": h.par} for h in holes],
        "scores_by_hole": scores_by_hole,
        "holes_played": holes_played,
        "gross_total": gross_total,
        "net_total": net_total,
    })


@router.get("/leaderboard/{event_id}", response_class=HTMLResponse)
async def leaderboard_page(event_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    if event.status == EventStatus.draft:
        raise HTTPException(status_code=403, detail="Leaderboard is not available until the event has started")

    from app.services.leaderboard import get_leaderboard
    leaderboard_data = await get_leaderboard(db, event_id)

    chat_result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.event_id == event_id)
        .order_by(ChatMessage.created_at.asc())
        .limit(50)
    )
    messages = chat_result.scalars().all()

    return templates.TemplateResponse(request=request, name="leaderboard.html", context={
        "event": {
            "id": event.id,
            "name": event.name,
            "date": event.date.isoformat() if event.date else "",
            "status": event.status.value,
            "hole_count": event.hole_count,
        },
        "leaderboard": leaderboard_data.get("leaderboard", []),
        "is_final": leaderboard_data.get("is_final", False),
        "unread_count": 0,
        "event_id": event.id,
        "sender_name": "",
        "messages": messages,
    })


@router.get("/events/join", response_class=HTMLResponse)
async def join_event_page(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")


@router.post("/events/join", response_class=HTMLResponse)
async def join_event(request: Request, db: AsyncSession = Depends(get_db)):
    form_data = await request.form()
    join_code = form_data.get("join_code", "").strip()

    result = await db.execute(select(Group).where(Group.qr_token == join_code))
    group = result.scalar_one_or_none()

    if group:
        return RedirectResponse(url=f"/score/{join_code}", status_code=303)

    return templates.TemplateResponse(request=request, name="index.html", context={
        "error": "Invalid join code",
    })
