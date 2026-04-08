from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from app import auth
from app.database import get_db

router = APIRouter(prefix="/auth", tags=["auth"])


class MagicLinkRequest(BaseModel):
    email: EmailStr


class MagicLinkResponse(BaseModel):
    message: str


class VerifyResponse(BaseModel):
    email: str


@router.post("/magic-link", response_model=MagicLinkResponse)
async def send_magic_link(
    request: MagicLinkRequest,
    db: AsyncSession = Depends(get_db),
):
    organizer = await auth.get_or_create_organizer(db, request.email)
    magic_link = await auth.create_magic_link(db, organizer)
    
    magic_link_url = f"http://localhost:8000/auth/verify?token={magic_link.token}"
    print(f"[DEBUG] Magic link for {request.email}: {magic_link_url}")
    
    return MagicLinkResponse(
        message=f"Magic link sent to {request.email}. Check server logs for the link."
    )


@router.get("/verify", response_model=VerifyResponse)
async def verify_token(
    token: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    organizer = await auth.verify_magic_link(db, token)
    
    if organizer is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    return VerifyResponse(email=organizer.email)