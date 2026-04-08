import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.tables import MagicLink, Organizer


async def get_organizer_by_email(db: AsyncSession, email: str) -> Organizer | None:
    result = await db.execute(
        select(Organizer).where(Organizer.email == email)
    )
    return result.scalar_one_or_none()


async def get_or_create_organizer(db: AsyncSession, email: str) -> Organizer:
    organizer = await get_organizer_by_email(db, email)
    if organizer is None:
        organizer = Organizer(email=email)
        db.add(organizer)
        await db.flush()
    return organizer


async def create_magic_link(
    db: AsyncSession, organizer: Organizer, expires_hours: int = 24
) -> MagicLink:
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=expires_hours)

    magic_link = MagicLink(
        organizer_id=organizer.id,
        token=token,
        expires_at=expires_at,
    )
    db.add(magic_link)
    await db.flush()
    return magic_link


async def verify_magic_link(
    db: AsyncSession, token: str
) -> Organizer | None:
    result = await db.execute(
        select(MagicLink).where(MagicLink.token == token)
    )
    magic_link = result.scalar_one_or_none()
    
    if magic_link is None:
        return None
    
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    expires = magic_link.expires_at.replace(tzinfo=None) if magic_link.expires_at.tzinfo else magic_link.expires_at
    
    if expires < now:
        return None
    
    result = await db.execute(
        select(Organizer).where(Organizer.id == magic_link.organizer_id)
    )
    return result.scalar_one_or_none()