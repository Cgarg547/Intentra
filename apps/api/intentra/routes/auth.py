import secrets
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from intentra.database import get_db
from intentra.models.intent_contract import UserRecord
from intentra.models.session import SessionRecord
from intentra.services.auth import (
    generate_session_token,
    hash_password,
    hash_session_token,
    session_cookie_requires_https,
    session_expiry,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

COOKIE_NAME = "intentra_session"
logger = logging.getLogger(__name__)

class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)


class UserResponse(BaseModel):
    id: uuid.UUID
    email: EmailStr


async def current_user(
    request: Request,
    intentra_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
) -> UserRecord:
    if not intentra_session:
        code = "AUTHENTICATION_REQUIRED"
        logger.warning("request_rejected", extra={
            "event_name": "request_rejected", "error_code": code,
            "correlation_id": getattr(request.state, "correlation_id", None),
        })
        raise HTTPException(status_code=401, detail="Not authenticated",
                            headers={"X-Intentra-Error-Code": code})

    token_hash = hash_session_token(intentra_session)

    result = await db.execute(
        select(SessionRecord, UserRecord)
        .join(UserRecord, SessionRecord.user_id == UserRecord.id)
        .where(
            SessionRecord.token_hash == token_hash,
            SessionRecord.revoked_at.is_(None),
            SessionRecord.expires_at > datetime.now(timezone.utc),
        )
    )

    row = result.one_or_none()

    if row is None:
        code = "SESSION_INVALID"
        logger.warning("request_rejected", extra={
            "event_name": "request_rejected", "error_code": code,
            "correlation_id": getattr(request.state, "correlation_id", None),
        })
        raise HTTPException(status_code=401, detail="Invalid session",
                            headers={"X-Intentra-Error-Code": code})

    return row[1]


async def create_session(
    db: AsyncSession,
    user: UserRecord,
    response: Response,
) -> None:
    token = generate_session_token()

    db.add(
        SessionRecord(
            user_id=user.id,
            token_hash=hash_session_token(token),
            expires_at=session_expiry(),
        )
    )

    await db.commit()

    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        secure=session_cookie_requires_https(),
        samesite="lax",
        max_age=8 * 60 * 60,
        path="/",
    )


@router.post("/register", response_model=UserResponse, status_code=201)
async def register(
    credentials: Credentials,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    email = str(credentials.email).lower()

    existing = await db.scalar(
        select(UserRecord).where(UserRecord.email == email)
    )

    if existing:
        raise HTTPException(status_code=409, detail="Account already exists")

    user = UserRecord(
        email=email,
        password_hash=hash_password(credentials.password),
    )

    db.add(user)
    await db.flush()
    await create_session(db, user, response)

    return UserResponse(id=user.id, email=user.email)


@router.post("/login", response_model=UserResponse)
async def login(
    credentials: Credentials,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    email = str(credentials.email).lower()

    user = await db.scalar(
        select(UserRecord).where(UserRecord.email == email)
    )

    if user is None or not verify_password(
        credentials.password, user.password_hash
    ):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    await create_session(db, user, response)

    return UserResponse(id=user.id, email=user.email)


@router.get("/me", response_model=UserResponse)
async def me(user: UserRecord = Depends(current_user)):
    return UserResponse(id=user.id, email=user.email)


@router.post("/logout", status_code=204)
async def logout(
    response: Response,
    intentra_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    if intentra_session:
        session = await db.scalar(
            select(SessionRecord).where(
                SessionRecord.token_hash == hash_session_token(
                    intentra_session
                )
            )
        )

        if session and session.revoked_at is None:
            session.revoked_at = datetime.now(timezone.utc)
            await db.commit()

    response.delete_cookie(COOKIE_NAME, path="/")
