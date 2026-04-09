"""Test event CRUD, lifecycle transitions."""
import pytest
from datetime import date

from app.tables import Event, EventStatus, EventFormat


@pytest.mark.asyncio
async def test_create_event(db):
    """POST /events creates event with auto-generated holes."""
    from app.routers.events import create_event, CreateEventRequest
    
    request = CreateEventRequest(name="Test Event", date=date(2026, 4, 15), hole_count=18)
    response = await create_event(request, db)
    
    assert response.name == "Test Event"
    assert response.hole_count == 18
    assert response.status == "draft"
    assert response.join_code is not None


@pytest.mark.asyncio
async def test_create_event_with_custom_hole_count(db):
    """Event can have non-standard hole count (e.g., 16)."""
    from app.routers.events import create_event, CreateEventRequest
    
    request = CreateEventRequest(name="9 Hole Event", date=date(2026, 4, 15), hole_count=9)
    response = await create_event(request, db)
    
    assert response.hole_count == 9


@pytest.mark.asyncio
async def test_start_event_draft_to_active(db):
    """POST /events/{id}/start transitions draft → active."""
    from app.routers.events import create_event, start_event, CreateEventRequest
    
    request = CreateEventRequest(name="Test Event", date=date(2026, 4, 15))
    event_response = await create_event(request, db)
    
    response = await start_event(event_response.id, db)
    
    assert response["status"] == "active"


@pytest.mark.asyncio
async def test_start_event_already_active_fails(db):
    """Cannot start event that's already active."""
    from app.routers.events import create_event, start_event, CreateEventRequest
    from fastapi import HTTPException
    
    request = CreateEventRequest(name="Test Event", date=date(2026, 4, 15))
    event_response = await create_event(request, db)
    
    await start_event(event_response.id, db)
    
    with pytest.raises(HTTPException) as exc:
        await start_event(event_response.id, db)
    
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_close_event_active_to_closed(db):
    """POST /events/{id}/close transitions active → closed."""
    from app.routers.events import create_event, start_event, close_event, CreateEventRequest
    
    request = CreateEventRequest(name="Test Event", date=date(2026, 4, 15))
    event_response = await create_event(request, db)
    
    await start_event(event_response.id, db)
    response = await close_event(event_response.id, db)
    
    assert response["status"] == "closed"


@pytest.mark.asyncio
async def test_close_event_not_active_fails(db):
    """Cannot close event that's not active."""
    from app.routers.events import create_event, close_event, CreateEventRequest
    from fastapi import HTTPException
    
    request = CreateEventRequest(name="Test Event", date=date(2026, 4, 15))
    event_response = await create_event(request, db)
    
    with pytest.raises(HTTPException) as exc:
        await close_event(event_response.id, db)
    
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_create_group(db):
    """POST /events/{id}/groups creates group with QR token."""
    from app.routers.events import create_event, create_group, CreateEventRequest, CreateGroupRequest
    
    request = CreateEventRequest(name="Test Event", date=date(2026, 4, 15))
    event_response = await create_event(request, db)
    
    group_request = CreateGroupRequest(
        name="Group 1",
        group_handicap=5,
        players=[
            {"name": "Player 1", "handicap": 10, "is_scorer": True},
            {"name": "Player 2", "handicap": 15, "is_scorer": False},
        ]
    )
    response = await create_group(event_response.id, group_request, db)
    
    assert response.name == "Group 1"
    assert response.group_handicap == 5
    assert response.qr_token is not None


@pytest.mark.asyncio
async def test_create_group_with_no_players(db):
    """POST /events/{id}/groups with empty players creates group shell (UI adds players later)."""
    from app.routers.events import create_event, create_group, CreateEventRequest, CreateGroupRequest

    request = CreateEventRequest(name="Test Event", date=date(2026, 4, 15))
    event_response = await create_event(request, db)

    group_request = CreateGroupRequest(name="Group 1", group_handicap=0, players=[])
    response = await create_group(event_response.id, group_request, db)

    assert response.name == "Group 1"
    assert response.qr_token is not None


@pytest.mark.asyncio
async def test_get_event(db):
    """GET /events/{id} returns event details."""
    from app.routers.events import create_event, get_event, CreateEventRequest

    request = CreateEventRequest(name="Test Event", date=date(2026, 4, 15))
    event_response = await create_event(request, db)

    response = await get_event(event_response.id, db)

    assert response["name"] == "Test Event"
    assert response["status"] == "draft"