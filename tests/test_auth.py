"""Test magic-link authentication."""
import pytest
from datetime import date, datetime, timedelta, timezone
from fastapi import HTTPException

from app.tables import Event, EventStatus


@pytest.mark.asyncio
async def test_send_magic_link(db):
    """POST /auth/magic-link creates organizer and magic link."""
    from app.routers.auth import send_magic_link, MagicLinkRequest
    
    request = MagicLinkRequest(email="test@example.com")
    response = await send_magic_link(request, db)
    
    assert "Magic link sent" in response.message


@pytest.mark.asyncio
async def test_verify_valid_token(db):
    """GET /auth/verify with valid token returns organizer email."""
    from app.routers.auth import send_magic_link, verify_token, MagicLinkRequest
    
    request = MagicLinkRequest(email="test@example.com")
    await send_magic_link(request, db)
    
    from app.tables import MagicLink
    from sqlalchemy import select
    result = await db.execute(select(MagicLink))
    magic_link = result.scalar_one()
    
    response = await verify_token(token=magic_link.token, db=db)
    
    assert response.email == "test@example.com"


@pytest.mark.asyncio
async def test_verify_invalid_token(db):
    """GET /auth/verify with invalid token returns 401."""
    from app.routers.auth import verify_token
    from fastapi import HTTPException
    
    with pytest.raises(HTTPException) as exc:
        await verify_token(token="invalid-token", db=db)
    
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_verify_expired_token(db):
    """GET /auth/verify with expired token returns 401."""
    from app.routers.auth import send_magic_link, verify_token, MagicLinkRequest
    from app.tables import MagicLink
    from sqlalchemy import select
    
    request = MagicLinkRequest(email="test@example.com")
    await send_magic_link(request, db)
    
    result = await db.execute(select(MagicLink))
    magic_link = result.scalar_one()
    
    past_time = datetime.now(timezone.utc) - timedelta(hours=25)
    magic_link.expires_at = past_time
    await db.commit()
    
    with pytest.raises(HTTPException) as exc:
        await verify_token(token=magic_link.token, db=db)
    
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_token_reusable_within_expiry(db):
    """Magic link can be reused within 24-hour expiry window."""
    from app.routers.auth import send_magic_link, verify_token, MagicLinkRequest
    from app.tables import MagicLink
    from sqlalchemy import select
    
    request = MagicLinkRequest(email="test@example.com")
    await send_magic_link(request, db)
    
    result = await db.execute(select(MagicLink))
    magic_link = result.scalar_one()
    token = magic_link.token
    
    response1 = await verify_token(token=token, db=db)
    assert response1.email == "test@example.com"
    
    response2 = await verify_token(token=token, db=db)
    assert response2.email == "test@example.com"