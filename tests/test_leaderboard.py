"""Test leaderboard sort logic (mid-round, final, tiebreaker, DNF)."""
import pytest
from datetime import date

from app.tables import Event, Group, Hole, Score, Player, EventStatus


@pytest.mark.asyncio
async def test_mid_round_sort_by_holes_played(db):
    """Groups with more holes played rank higher; within equal holes, lower gross ranks higher."""
    from app.services.leaderboard import get_leaderboard
    
    event = Event(name="Test", date=date(2026, 4, 15), join_code="test123", status=EventStatus.active, hole_count=18)
    db.add(event)
    await db.flush()
    
    hole1 = Hole(event_id=event.id, hole_number=1, par=4)
    hole2 = Hole(event_id=event.id, hole_number=2, par=4)
    hole3 = Hole(event_id=event.id, hole_number=3, par=4)
    db.add_all([hole1, hole2, hole3])
    await db.flush()
    
    group_a = Group(event_id=event.id, name="Group A", group_handicap=5, qr_token="qra")
    group_b = Group(event_id=event.id, name="Group B", group_handicap=10, qr_token="qrb")
    db.add_all([group_a, group_b])
    await db.flush()
    
    db.add(Score(group_id=group_a.id, hole_id=hole1.id, gross_score=4))
    db.add(Score(group_id=group_a.id, hole_id=hole2.id, gross_score=5))
    db.add(Score(group_id=group_b.id, hole_id=hole1.id, gross_score=3))
    await db.commit()
    
    result = await get_leaderboard(db, event.id)
    
    # Group A has more holes played (2) than Group B (1), so Group A ranks first
    assert result["leaderboard"][0]["group_name"] == "Group A"
    assert result["leaderboard"][0]["holes_played"] == 2
    assert result["leaderboard"][1]["group_name"] == "Group B"
    assert result["leaderboard"][1]["holes_played"] == 1


@pytest.mark.asyncio
async def test_final_sort_by_net_total(db):
    """When all holes complete, sort by net total (gross - handicap), then gross as tiebreaker."""
    from app.services.leaderboard import get_leaderboard
    
    event = Event(name="Test", date=date(2026, 4, 15), join_code="test123", status=EventStatus.active, hole_count=2)
    db.add(event)
    await db.flush()
    
    hole1 = Hole(event_id=event.id, hole_number=1, par=4)
    hole2 = Hole(event_id=event.id, hole_number=2, par=4)
    db.add_all([hole1, hole2])
    await db.flush()
    
    group_a = Group(event_id=event.id, name="Group A", group_handicap=5, qr_token="qra")
    group_b = Group(event_id=event.id, name="Group B", group_handicap=0, qr_token="qrb")
    db.add_all([group_a, group_b])
    await db.flush()
    
    db.add(Score(group_id=group_a.id, hole_id=hole1.id, gross_score=5))
    db.add(Score(group_id=group_a.id, hole_id=hole2.id, gross_score=5))
    db.add(Score(group_id=group_b.id, hole_id=hole1.id, gross_score=4))
    db.add(Score(group_id=group_b.id, hole_id=hole2.id, gross_score=6))
    await db.commit()
    
    result = await get_leaderboard(db, event.id)
    
    assert result["is_final"] is True
    assert result["leaderboard"][0]["group_name"] == "Group A"  # net 5 < net 10
    assert result["leaderboard"][0]["net_total"] == 5
    assert result["leaderboard"][1]["group_name"] == "Group B"
    assert result["leaderboard"][1]["net_total"] == 10


@pytest.mark.asyncio
async def test_incomplete_group_ranked_below(db):
    """Groups with fewer holes played are ranked below complete groups."""
    from app.services.leaderboard import get_leaderboard
    
    event = Event(name="Test", date=date(2026, 4, 15), join_code="test123", status=EventStatus.active, hole_count=2)
    db.add(event)
    await db.flush()
    
    hole1 = Hole(event_id=event.id, hole_number=1, par=4)
    hole2 = Hole(event_id=event.id, hole_number=2, par=4)
    db.add_all([hole1, hole2])
    await db.flush()
    
    group_a = Group(event_id=event.id, name="Group A", group_handicap=0, qr_token="qra")
    group_b = Group(event_id=event.id, name="Group B", group_handicap=0, qr_token="qrb")
    db.add_all([group_a, group_b])
    await db.flush()
    
    db.add(Score(group_id=group_a.id, hole_id=hole1.id, gross_score=4))
    db.add(Score(group_id=group_a.id, hole_id=hole2.id, gross_score=4))
    db.add(Score(group_id=group_b.id, hole_id=hole1.id, gross_score=3))
    await db.commit()
    
    result = await get_leaderboard(db, event.id)
    
    assert result["leaderboard"][0]["group_name"] == "Group A"
    assert result["leaderboard"][0]["holes_played"] == 2
    assert result["leaderboard"][1]["group_name"] == "Group B"
    assert result["leaderboard"][1]["holes_played"] == 1


@pytest.mark.asyncio
async def test_tiebreaker_shared_placing(db):
    """Groups with identical net AND gross share placing without crash."""
    from app.services.leaderboard import get_leaderboard
    
    event = Event(name="Test", date=date(2026, 4, 15), join_code="test123", status=EventStatus.active, hole_count=2)
    db.add(event)
    await db.flush()
    
    hole1 = Hole(event_id=event.id, hole_number=1, par=4)
    hole2 = Hole(event_id=event.id, hole_number=2, par=4)
    db.add_all([hole1, hole2])
    await db.flush()
    
    group_a = Group(event_id=event.id, name="Group A", group_handicap=0, qr_token="qra")
    group_b = Group(event_id=event.id, name="Group B", group_handicap=0, qr_token="qrb")
    db.add_all([group_a, group_b])
    await db.flush()
    
    db.add(Score(group_id=group_a.id, hole_id=hole1.id, gross_score=4))
    db.add(Score(group_id=group_a.id, hole_id=hole2.id, gross_score=4))
    db.add(Score(group_id=group_b.id, hole_id=hole1.id, gross_score=4))
    db.add(Score(group_id=group_b.id, hole_id=hole2.id, gross_score=4))
    await db.commit()
    
    result = await get_leaderboard(db, event.id)
    
    assert result["is_final"] is True
    assert result["leaderboard"][0]["net_total"] == 8
    assert result["leaderboard"][1]["net_total"] == 8


@pytest.mark.asyncio
async def test_non_standard_hole_count(db):
    """16-hole event leaderboard shows final when all 16 submitted."""
    from app.services.leaderboard import get_leaderboard
    
    event = Event(name="Test", date=date(2026, 4, 15), join_code="test123", status=EventStatus.active, hole_count=16)
    db.add(event)
    await db.flush()
    
    holes = [Hole(event_id=event.id, hole_number=i, par=4) for i in range(1, 17)]
    db.add_all(holes)
    await db.flush()
    
    group = Group(event_id=event.id, name="Group 1", group_handicap=5, qr_token="qr1")
    db.add(group)
    await db.flush()
    
    for hole in holes[:16]:
        db.add(Score(group_id=group.id, hole_id=hole.id, gross_score=4))
    await db.commit()
    
    result = await get_leaderboard(db, event.id)
    
    assert result["is_final"] is True
    assert result["leaderboard"][0]["holes_played"] == 16
    assert result["leaderboard"][0]["gross_total"] == 64
    assert result["leaderboard"][0]["net_total"] == 59