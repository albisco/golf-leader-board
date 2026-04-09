"""End-to-end tests: full scorer flow, live broadcast, chat flow."""
import pytest
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock

from app.tables import Event, Group, Hole, Score, Player, EventStatus, ChatMessage


def test_leaderboard_template_no_recursive_htmx():
    """leaderboard.html must not have hx-get on #leaderboard-content.

    Regression test: hx-get="/leaderboard/{id}" on that div fetches the full
    page and injects it into itself, duplicating the chat section and WS script
    on every server response (~10s loop).
    """
    template_path = Path(__file__).parent.parent / "app" / "templates" / "leaderboard.html"
    html = template_path.read_text()

    # The div must exist but must NOT carry hx-get
    assert 'id="leaderboard-content"' in html, "#leaderboard-content div missing from template"
    # Find the line with the div and assert no hx-get on it
    for line in html.splitlines():
        if 'id="leaderboard-content"' in line:
            assert "hx-get" not in line, (
                "#leaderboard-content has hx-get — this causes the full page to be injected "
                "recursively, duplicating chat and WS script every ~10s"
            )


@pytest.mark.asyncio
async def test_full_scorer_flow(db):
    """Full flow: create event → start → add group → submit scores → get leaderboard."""
    from app.routers.events import create_event, start_event, create_group, CreateEventRequest, CreateGroupRequest
    from app.routers.scores import submit_score, get_leaderboard_endpoint, ScoreRequest
    from app.services.leaderboard import get_leaderboard
    
    # Create event
    event_req = CreateEventRequest(name="Golf Day", date=date(2026, 4, 15), hole_count=9)
    event = await create_event(event_req, db)
    
    # Start event
    await start_event(event.id, db)
    
    # Create group with players
    group_req = CreateGroupRequest(
        name="Group 1",
        group_handicap=5,
        players=[
            {"name": "Alice", "handicap": 12, "is_scorer": True},
            {"name": "Bob", "handicap": 18, "is_scorer": False},
        ]
    )
    group = await create_group(event.id, group_req, db)
    
    # Get holes for the event
    from sqlalchemy import select
    result = await db.execute(select(Hole).where(Hole.event_id == event.id))
    holes = result.scalars().all()
    
    # Submit scores for each hole (only 3, not all 9, so net_total will be None)
    for hole in holes[:3]:
        score_req = ScoreRequest(group_id=group.id, hole_id=hole.id, gross_score=4)
        await submit_score(score_req, db)
    
    # Get leaderboard
    leaderboard = await get_leaderboard(db, event.id)
    
    assert leaderboard["leaderboard"][0]["group_name"] == "Group 1"
    assert leaderboard["leaderboard"][0]["holes_played"] == 3
    assert leaderboard["leaderboard"][0]["gross_total"] == 12
    assert leaderboard["leaderboard"][0]["net_total"] is None  # Not all holes played yet


@pytest.mark.asyncio
async def test_leaderboard_endpoint(db):
    """GET /leaderboard/{event_id} returns leaderboard data."""
    from app.routers.scores import get_leaderboard_endpoint
    from app.routers.events import create_event, start_event, create_group, CreateEventRequest, CreateGroupRequest
    from app.routers.scores import submit_score, ScoreRequest
    from app.services.leaderboard import get_leaderboard
    
    event_req = CreateEventRequest(name="Golf Day", date=date(2026, 4, 15), hole_count=9)
    event = await create_event(event_req, db)
    await start_event(event.id, db)
    
    group_req = CreateGroupRequest(name="Group 1", group_handicap=0, players=[{"name": "Player", "handicap": 10}])
    group = await create_group(event.id, group_req, db)
    
    from sqlalchemy import select
    result = await db.execute(select(Hole).where(Hole.event_id == event.id))
    hole = result.scalars().first()
    
    await submit_score(ScoreRequest(group_id=group.id, hole_id=hole.id, gross_score=4), db)
    
    response = await get_leaderboard_endpoint(event.id, db)
    
    assert response["event"]["name"] == "Golf Day"
    assert len(response["leaderboard"]) == 1


@pytest.mark.asyncio
async def test_chat_message(db):
    """POST /chat creates message and returns it."""
    from app.routers.chat import send_chat_message, ChatMessageRequest
    from app.routers.events import create_event, start_event, CreateEventRequest
    
    event_req = CreateEventRequest(name="Golf Day", date=date(2026, 4, 15))
    event = await create_event(event_req, db)
    await start_event(event.id, db)
    
    request = ChatMessageRequest(
        event_id=event.id,
        sender_name="Alice",
        content="Great shot on hole 5!"
    )
    response = await send_chat_message(request, db)
    
    assert response.sender_name == "Alice"
    assert response.content == "Great shot on hole 5!"


@pytest.mark.asyncio
async def test_chat_rejected_for_draft_event(db):
    """Chat messages not allowed for draft events."""
    from app.routers.chat import send_chat_message, ChatMessageRequest
    from app.routers.events import create_event, CreateEventRequest
    from fastapi import HTTPException
    
    event_req = CreateEventRequest(name="Golf Day", date=date(2026, 4, 15))
    event = await create_event(event_req, db)
    
    request = ChatMessageRequest(
        event_id=event.id,
        sender_name="Alice",
        content="Hello"
    )
    
    with pytest.raises(HTTPException) as exc:
        await send_chat_message(request, db)
    
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_event_lifecycle(db):
    """Event transitions: draft → active → closed."""
    from app.routers.events import create_event, start_event, close_event, get_event, CreateEventRequest
    
    event_req = CreateEventRequest(name="Golf Day", date=date(2026, 4, 15))
    event = await create_event(event_req, db)
    
    # Check draft status
    response = await get_event(event.id, db)
    assert response["status"] == "draft"
    
    # Start event
    await start_event(event.id, db)
    response = await get_event(event.id, db)
    assert response["status"] == "active"
    
    # Close event
    await close_event(event.id, db)
    response = await get_event(event.id, db)
    assert response["status"] == "closed"


@pytest.mark.asyncio
async def test_multiple_groups_leaderboard(db):
    """Leaderboard sorts multiple groups correctly."""
    from app.routers.events import create_event, start_event, create_group, CreateEventRequest, CreateGroupRequest
    from app.routers.scores import submit_score, ScoreRequest
    from app.services.leaderboard import get_leaderboard
    
    event_req = CreateEventRequest(name="Golf Day", date=date(2026, 4, 15), hole_count=2)
    event = await create_event(event_req, db)
    await start_event(event.id, db)
    
    # Create two groups
    group1_req = CreateGroupRequest(name="Group A", group_handicap=0, players=[{"name": "P1", "handicap": 10}])
    group1 = await create_group(event.id, group1_req, db)
    
    group2_req = CreateGroupRequest(name="Group B", group_handicap=5, players=[{"name": "P2", "handicap": 15}])
    group2 = await create_group(event.id, group2_req, db)
    
    from sqlalchemy import select
    result = await db.execute(select(Hole).where(Hole.event_id == event.id))
    holes = result.scalars().all()
    
    # Group A scores 4, 5 = 9 gross
    await submit_score(ScoreRequest(group_id=group1.id, hole_id=holes[0].id, gross_score=4), db)
    await submit_score(ScoreRequest(group_id=group1.id, hole_id=holes[1].id, gross_score=5), db)
    
    # Group B scores 3, 4 = 7 gross, 7-5=2 net
    await submit_score(ScoreRequest(group_id=group2.id, hole_id=holes[0].id, gross_score=3), db)
    await submit_score(ScoreRequest(group_id=group2.id, hole_id=holes[1].id, gross_score=4), db)
    
    leaderboard = await get_leaderboard(db, event.id)
    
    assert leaderboard["is_final"] is True
    # Group B has lower net (2) than Group A (9)
    assert leaderboard["leaderboard"][0]["group_name"] == "Group B"
    assert leaderboard["leaderboard"][0]["net_total"] == 2
    assert leaderboard["leaderboard"][1]["group_name"] == "Group A"
    assert leaderboard["leaderboard"][1]["net_total"] == 9