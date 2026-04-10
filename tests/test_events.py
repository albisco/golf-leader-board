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


@pytest.mark.asyncio
async def test_update_group_handicap_persists(db):
    """Regression: ISSUE-2679 — group_handicap saved via PUT must be readable on next page load.

    Found by /qa on 2026-04-10
    Report: .gstack/qa-reports/qa-report-localhost-2026-04-10.md

    Before fix: saveGroup() called alert() without location.reload(), so the QR codes
    tab showed the stale Jinja-rendered handicap (0) instead of the newly saved value.
    The backend was saving correctly — this test verifies the backend contract holds.
    """
    from app.routers.events import (
        create_event, create_group, update_group,
        CreateEventRequest, CreateGroupRequest, UpdateGroupRequest,
    )
    from sqlalchemy import select
    from app.tables import Group

    event = await create_event(CreateEventRequest(name="Test Event", date=date(2026, 4, 15)), db)
    group = await create_group(event.id, CreateGroupRequest(name="Group 1", group_handicap=0), db)

    # Save group with handicap 12 (UpdateGroupRequest requires >=2 players, 1 scorer)
    await update_group(event.id, group.id, UpdateGroupRequest(
        group_handicap=12,
        players=[
            {"name": "Player 1", "handicap": 10, "is_scorer": True},
            {"name": "Player 2", "handicap": 8, "is_scorer": False},
        ]
    ), db)

    # Verify the handicap is persisted — simulates what the page reload reads from DB
    result = await db.execute(select(Group).where(Group.id == group.id))
    saved = result.scalar_one()
    assert saved.group_handicap == 12, (
        f"Expected group_handicap=12 after update, got {saved.group_handicap}. "
        "If this fails, the QR tab will show stale handicap on page reload."
    )

@pytest.mark.asyncio
async def test_create_event_with_groups_in_one_call(db):
    """create_event with group_count creates groups in the same transaction.

    Perf fix: eliminates N sequential HTTP calls for group creation.
    One round-trip to the DB instead of 1 + N.
    """
    from app.routers.events import create_event, CreateEventRequest
    from sqlalchemy import select
    from app.tables import Group

    response = await create_event(
        CreateEventRequest(name="Golf Day", date=date(2026, 4, 15), group_count=4), db
    )

    groups = (await db.execute(
        select(Group).where(Group.event_id == response.id)
    )).scalars().all()

    assert len(groups) == 4
    assert [g.name for g in groups] == ["Group 1", "Group 2", "Group 3", "Group 4"]
    assert all(g.qr_token for g in groups)
