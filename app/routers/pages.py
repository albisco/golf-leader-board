from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.tables import Event, Group, Hole, Player, Score

router = APIRouter(tags=["pages"])


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    from app.templates import templates
    return templates.TemplateResponse("index.html", context={"request": request})


@router.get("/create-event", response_class=HTMLResponse)
async def create_event_page(request: Request):
    from app.templates import templates
    return templates.TemplateResponse("create_event.html", context={"request": request})


@router.get("/event/{event_id}/setup", response_class=HTMLResponse)
async def event_setup_page(event_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    from app.templates import templates
    
    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()
    
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    
    result = await db.execute(
        select(Group).options(
            selectinload(Group.players)
        ).where(Group.event_id == event_id)
    )
    groups = result.scalars().all()
    
    result = await db.execute(select(Hole).where(Hole.event_id == event_id))
    holes = result.scalars().all()
    
    return templates.TemplateResponse("event_setup.html", context={
        "request": request,
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
                "players": [{"name": p.name, "handicap": p.handicap, "is_scorer": p.is_scorer} for p in g.players]
            }
            for g in groups
        ],
        "holes": [{"id": h.id, "hole_number": h.hole_number, "par": h.par} for h in holes],
    })


@router.get("/score/{scorer_token}", response_class=HTMLResponse)
async def score_entry_page(scorer_token: str, request: Request, db: AsyncSession = Depends(get_db)):
    from app.templates import templates
    
    result = await db.execute(select(Group).where(Group.qr_token == scorer_token))
    group = result.scalar_one_or_none()
    
    if group is None:
        raise HTTPException(status_code=404, detail="Invalid scorer token")
    
    result = await db.execute(select(Event).where(Event.id == group.event_id))
    event = result.scalar_one_or_none()
    
    result = await db.execute(select(Hole).where(Hole.event_id == event.id))
    holes = result.scalars().all()
    
    result = await db.execute(select(Score).where(Score.group_id == group.id))
    scores = result.scalars().all()
    
    scores_by_hole = {}
    for s in scores:
        for h in holes:
            if h.id == s.hole_id:
                scores_by_hole[h.hole_number] = {"gross_score": s.gross_score, "edit_count": s.edit_count}
                break
    
    holes_played = len(scores)
    gross_total = sum(s.gross_score for s in scores)
    net_total = gross_total - group.group_handicap if holes_played == event.hole_count else None
    
    return templates.TemplateResponse("score_entry.html", context={
        "request": request,
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
            "players": [{"name": p.name, "handicap": p.handicap, "is_scorer": p.is_scorer} for p in group.players]
        },
        "holes": [{"id": h.id, "hole_number": h.hole_number, "par": h.par} for h in holes],
        "scores_by_hole": scores_by_hole,
        "holes_played": holes_played,
        "gross_total": gross_total,
        "net_total": net_total,
    })


@router.get("/leaderboard/{event_id}", response_class=HTMLResponse)
async def leaderboard_page(event_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    from app.templates import templates
    
    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()
    
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    
    from app.services.leaderboard import get_leaderboard
    leaderboard_data = await get_leaderboard(db, event_id)
    
    return templates.TemplateResponse("leaderboard.html", context={
        "request": request,
        "event": {
            "id": event.id,
            "name": event.name,
            "date": event.date.isoformat() if event.date else "",
            "status": event.status.value,
            "hole_count": event.hole_count,
        },
        "leaderboard": leaderboard_data.get("leaderboard", []),
        "is_final": leaderboard_data.get("is_final", False),
    })


@router.get("/events/join", response_class=HTMLResponse)
async def join_event_page(request: Request):
    from app.templates import templates
    return templates.TemplateResponse("index.html", context={"request": request})


@router.post("/events/join", response_class=HTMLResponse)
async def join_event(request: Request):
    from app.templates import templates
    form_data = await request.form()
    join_code = form_data.get("join_code", "")
    
    return templates.TemplateResponse("index.html", context={
        "request": request,
        "error": None
    })


@router.get("/score/{scorer_token}", response_class=HTMLResponse)
async def score_entry_page(scorer_token: str, request: Request, db: AsyncSession = Depends(get_db)):
    from app.templates import templates
    
    result = await db.execute(select(Group).where(Group.qr_token == scorer_token))
    group = result.scalar_one_or_none()
    
    if group is None:
        raise HTTPException(status_code=404, detail="Invalid scorer token")
    
    result = await db.execute(select(Event).where(Event.id == group.event_id))
    event = result.scalar_one_or_none()
    
    result = await db.execute(select(Hole).where(Hole.event_id == event.id))
    holes = result.scalars().all()
    
    result = await db.execute(select(Score).where(Score.group_id == group.id))
    scores = result.scalars().all()
    
    scores_by_hole = {}
    for s in scores:
        for h in holes:
            if h.id == s.hole_id:
                scores_by_hole[h.hole_number] = {"gross_score": s.gross_score, "edit_count": s.edit_count}
                break
    
    holes_played = len(scores)
    gross_total = sum(s.gross_score for s in scores)
    net_total = gross_total - group.group_handicap if holes_played == event.hole_count else None
    
    return templates.TemplateResponse("score_entry.html", {
        "request": request,
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
            "players": [{"name": p.name, "handicap": p.handicap, "is_scorer": p.is_scorer} for p in group.players]
        },
        "holes": [{"id": h.id, "hole_number": h.hole_number, "par": h.par} for h in holes],
        "scores_by_hole": scores_by_hole,
        "holes_played": holes_played,
        "gross_total": gross_total,
        "net_total": net_total,
    })


@router.get("/leaderboard/{event_id}", response_class=HTMLResponse)
async def leaderboard_page(event_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    from app.templates import templates
    
    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()
    
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    
    from app.services.leaderboard import get_leaderboard
    leaderboard_data = await get_leaderboard(db, event_id)
    
    return templates.TemplateResponse("leaderboard.html", {
        "request": request,
        "event": {
            "id": event.id,
            "name": event.name,
            "date": event.date.isoformat() if event.date else "",
            "status": event.status.value,
            "hole_count": event.hole_count,
        },
        "leaderboard": leaderboard_data.get("leaderboard", []),
        "is_final": leaderboard_data.get("is_final", False),
    })


@router.post("/events/join", response_class=HTMLResponse)
async def join_event(request: Request):
    from app.templates import templates
    from fastapi import Form
    from pydantic import BaseModel
    
    class JoinRequest(BaseModel):
        join_code: str
    
    form_data = await request.form()
    join_code = form_data.get("join_code", "")
    
    from sqlalchemy import select
    result = await get_db()
    db = next(result)
    
    try:
        result = await db.execute(select(Group).where(Group.qr_token == join_code))
        group = result.scalar_one_or_none()
        
        if group:
            from fastapi.templating import Jinja2Templates
            return templates.TemplateResponse("score_entry.html", {
                "request": request,
                "error": None
            })
    except:
        pass
    
    return templates.TemplateResponse("index.html", {
        "request": request,
        "error": "Invalid join code"
    })