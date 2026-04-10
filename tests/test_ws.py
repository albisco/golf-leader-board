"""Test WebSocket connection manager, broadcast, disconnect cleanup."""
import pytest
from datetime import date
from unittest.mock import AsyncMock, MagicMock

from app.services.ws_manager import WSManager


@pytest.mark.asyncio
async def test_websocket_connect():
    """WebSocket connect adds to event's connection list."""
    manager = WSManager()
    ws = AsyncMock()
    
    await manager.connect(1, ws)
    
    assert 1 in manager.active_connections
    assert ws in manager.active_connections[1]


@pytest.mark.asyncio
async def test_websocket_disconnect():
    """WebSocket disconnect removes from event's connection list."""
    manager = WSManager()
    ws = AsyncMock()
    
    await manager.connect(1, ws)
    manager.disconnect(1, ws)
    
    assert 1 not in manager.active_connections


@pytest.mark.asyncio
async def test_websocket_multiple_connections():
    """Multiple connections can join same event."""
    manager = WSManager()
    ws1 = AsyncMock()
    ws2 = AsyncMock()
    
    await manager.connect(1, ws1)
    await manager.connect(1, ws2)
    
    assert len(manager.active_connections[1]) == 2


@pytest.mark.asyncio
async def test_websocket_broadcast():
    """Broadcast sends message to all connections for an event."""
    manager = WSManager()
    ws1 = AsyncMock()
    ws2 = AsyncMock()
    
    await manager.connect(1, ws1)
    await manager.connect(1, ws2)
    
    await manager.broadcast(1, {"type": "update", "data": "test"})
    
    ws1.send_json.assert_called_once_with({"type": "update", "data": "test"})
    ws2.send_json.assert_called_once_with({"type": "update", "data": "test"})


@pytest.mark.asyncio
async def test_websocket_broadcast_no_connections():
    """Broadcast to event with no connections does nothing."""
    manager = WSManager()
    
    await manager.broadcast(1, {"type": "update"})
    # No exception should be raised


@pytest.mark.asyncio
async def test_websocket_disconnect_removes_empty_event():
    """Disconnect cleans up event when last connection leaves."""
    manager = WSManager()
    ws = AsyncMock()
    
    await manager.connect(1, ws)
    manager.disconnect(1, ws)
    
    assert 1 not in manager.active_connections


@pytest.mark.asyncio
async def test_websocket_broadcast_removes_disconnected():
    """Broadcast removes failed connections from the list."""
    manager = WSManager()
    ws1 = AsyncMock()
    ws2 = AsyncMock()
    
    ws1.send_json.side_effect = Exception("Connection closed")
    
    await manager.connect(1, ws1)
    await manager.connect(1, ws2)
    
    await manager.broadcast(1, {"type": "update"})
    
    # ws1 should have been removed, ws2 should remain
    assert ws1 not in manager.active_connections.get(1, [])
    ws2.send_json.assert_called_once()


@pytest.mark.asyncio
async def test_websocket_text_message():
    """Broadcast can send text messages."""
    manager = WSManager()
    ws = AsyncMock()
    
    await manager.connect(1, ws)
    
    await manager.broadcast(1, "text message")
    
    ws.send_text.assert_called_once_with("text message")


def test_leaderboard_template_no_duplicate_ws_declaration():
    """leaderboard.html must not redeclare 'let ws' — doing so causes a
    SyntaxError in browsers that kills the entire script block, preventing
    WebSocket connection and all live updates."""
    import os
    template_path = os.path.join(
        os.path.dirname(__file__), '..', 'app', 'templates', 'leaderboard.html'
    )
    with open(template_path) as f:
        content = f.read()
    assert 'let ws' not in content, (
        "leaderboard.html declares 'let ws' but base.html already declares it. "
        "This causes a SyntaxError in browsers, killing all live updates. "
        "Use connectWebSocket() from base.html instead."
    )


@pytest.mark.asyncio
async def test_chat_post_broadcasts_to_ws(db):
    """POST /chat broadcasts {type: 'chat', message: {...}} to all WS clients."""
    from unittest.mock import AsyncMock, patch
    from app.routers.chat import send_chat_message, ChatMessageRequest
    from app.tables import Event, EventStatus

    event = Event(name="Test", date=date(2026, 4, 15), join_code="chat123", status=EventStatus.active)
    db.add(event)
    await db.commit()
    await db.refresh(event)

    with patch('app.routers.chat.ws_manager') as mock_manager:
        mock_manager.broadcast = AsyncMock()
        request = ChatMessageRequest(event_id=event.id, sender_name="Alice", content="Hello!")
        await send_chat_message(request, db)

    mock_manager.broadcast.assert_called_once()
    call_args = mock_manager.broadcast.call_args
    assert call_args[0][0] == event.id
    payload = call_args[0][1]
    assert payload["type"] == "chat"
    assert payload["message"]["sender_name"] == "Alice"
    assert payload["message"]["content"] == "Hello!"


@pytest.mark.asyncio
async def test_scorer_token_view(db):
    """GET /score/{scorer_token} returns group and event info."""
    from app.routers.scores import get_scorer_view
    from app.tables import Event, Group, EventStatus
    
    event = Event(name="Test Event", date=date(2026, 4, 15), join_code="test123", status=EventStatus.active)
    db.add(event)
    await db.flush()
    
    group = Group(event_id=event.id, name="Group 1", group_handicap=5, qr_token="valid-token")
    db.add(group)
    await db.commit()
    
    response = await get_scorer_view(scorer_token="valid-token", db=db)
    
    assert response["group"]["name"] == "Group 1"
    assert response["event"]["name"] == "Test Event"


@pytest.mark.asyncio
async def test_scorer_token_invalid(db):
    """GET /score/{scorer_token} with invalid token returns 404."""
    from app.routers.scores import get_scorer_view
    from fastapi import HTTPException
    
    with pytest.raises(HTTPException) as exc:
        await get_scorer_view(scorer_token="invalid-token", db=db)
    
    assert exc.value.status_code == 404