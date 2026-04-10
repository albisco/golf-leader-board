"""Test score submission, upsert, edit_count, validation, closed-event rejection."""
import pytest
from datetime import date
from unittest.mock import AsyncMock, patch

from app.tables import Event, Group, Hole, EventStatus


@pytest.mark.asyncio
async def test_submit_score(db):
    """POST /scores creates new score for group/hole."""
    from app.routers.scores import submit_score, ScoreRequest
    
    event = Event(name="Test", date=date(2026, 4, 15), join_code="test123", status=EventStatus.active)
    db.add(event)
    await db.flush()
    
    for i in range(1, 19):
        hole = Hole(event_id=event.id, hole_number=i, par=4)
        db.add(hole)
    
    group = Group(event_id=event.id, name="Group 1", group_handicap=5, qr_token="qr123")
    db.add(group)
    await db.flush()
    
    request = ScoreRequest(group_id=group.id, hole_id=hole.id, gross_score=4)
    response = await submit_score(request, db)
    
    assert response.gross_score == 4
    assert response.edit_count == 0


@pytest.mark.asyncio
async def test_score_upsert(db):
    """Resubmitting score updates existing row, increments edit_count."""
    from app.routers.scores import submit_score, ScoreRequest
    
    event = Event(name="Test", date=date(2026, 4, 15), join_code="test123", status=EventStatus.active)
    db.add(event)
    await db.flush()
    
    hole = Hole(event_id=event.id, hole_number=1, par=4)
    db.add(hole)
    await db.flush()
    
    group = Group(event_id=event.id, name="Group 1", group_handicap=5, qr_token="qr123")
    db.add(group)
    await db.flush()
    
    request1 = ScoreRequest(group_id=group.id, hole_id=hole.id, gross_score=4)
    response1 = await submit_score(request1, db)
    assert response1.edit_count == 0
    
    request2 = ScoreRequest(group_id=group.id, hole_id=hole.id, gross_score=5)
    response2 = await submit_score(request2, db)
    assert response2.gross_score == 5
    assert response2.edit_count == 1


@pytest.mark.asyncio
async def test_score_edit_triggers_ws_broadcast(db):
    """Editing an existing score (edit_count > 0) must trigger WebSocket broadcast."""
    from app.routers.scores import submit_score, ScoreRequest

    event = Event(name="Test", date=date(2026, 4, 15), join_code="test123", status=EventStatus.active)
    db.add(event)
    await db.flush()

    hole = Hole(event_id=event.id, hole_number=1, par=4)
    db.add(hole)
    await db.flush()

    group = Group(event_id=event.id, name="Group 1", group_handicap=5, qr_token="qr123")
    db.add(group)
    await db.flush()

    # Submit initial score
    request1 = ScoreRequest(group_id=group.id, hole_id=hole.id, gross_score=4)
    await submit_score(request1, db)

    # Edit the score — broadcast must fire
    mock_broadcast = AsyncMock()
    with patch("app.routers.scores.ws_manager.broadcast", mock_broadcast):
        request2 = ScoreRequest(group_id=group.id, hole_id=hole.id, gross_score=5)
        response2 = await submit_score(request2, db)

    assert response2.edit_count == 1
    mock_broadcast.assert_called_once()
    call_args = mock_broadcast.call_args
    assert call_args[0][0] == event.id  # broadcast targets the correct event


@pytest.mark.asyncio
async def test_score_rejected_for_closed_event(db):
    """Submitting score to closed event returns 403."""
    from app.routers.scores import submit_score, ScoreRequest
    from fastapi import HTTPException
    
    event = Event(name="Test", date=date(2026, 4, 15), join_code="test123", status=EventStatus.closed)
    db.add(event)
    await db.flush()
    
    hole = Hole(event_id=event.id, hole_number=1, par=4)
    db.add(hole)
    await db.flush()
    
    group = Group(event_id=event.id, name="Group 1", group_handicap=5, qr_token="qr123")
    db.add(group)
    await db.flush()
    
    request = ScoreRequest(group_id=group.id, hole_id=hole.id, gross_score=4)
    
    with pytest.raises(HTTPException) as exc:
        await submit_score(request, db)
    
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_score_rejected_for_draft_event(db):
    """Submitting score to draft event returns 403."""
    from app.routers.scores import submit_score, ScoreRequest
    from fastapi import HTTPException
    
    event = Event(name="Test", date=date(2026, 4, 15), join_code="test123", status=EventStatus.draft)
    db.add(event)
    await db.flush()
    
    hole = Hole(event_id=event.id, hole_number=1, par=4)
    db.add(hole)
    await db.flush()
    
    group = Group(event_id=event.id, name="Group 1", group_handicap=5, qr_token="qr123")
    db.add(group)
    await db.flush()
    
    request = ScoreRequest(group_id=group.id, hole_id=hole.id, gross_score=4)
    
    with pytest.raises(HTTPException) as exc:
        await submit_score(request, db)
    
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_negative_score_rejected(db):
    """Score with negative gross_score returns 422."""
    from app.routers.scores import submit_score, ScoreRequest
    from fastapi import HTTPException
    
    event = Event(name="Test", date=date(2026, 4, 15), join_code="test123", status=EventStatus.active)
    db.add(event)
    await db.flush()
    
    hole = Hole(event_id=event.id, hole_number=1, par=4)
    db.add(hole)
    await db.flush()
    
    group = Group(event_id=event.id, name="Group 1", group_handicap=5, qr_token="qr123")
    db.add(group)
    await db.flush()
    
    request = ScoreRequest(group_id=group.id, hole_id=hole.id, gross_score=-1)
    
    with pytest.raises(HTTPException) as exc:
        await submit_score(request, db)
    
    assert exc.value.status_code == 422


@pytest.mark.asyncio
async def test_score_group_not_found(db):
    """Score with invalid group_id returns 404."""
    from app.routers.scores import submit_score, ScoreRequest
    from fastapi import HTTPException
    
    request = ScoreRequest(group_id=9999, hole_id=1, gross_score=4)
    
    with pytest.raises(HTTPException) as exc:
        await submit_score(request, db)
    
    assert exc.value.status_code == 404