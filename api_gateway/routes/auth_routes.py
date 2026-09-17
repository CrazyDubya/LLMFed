"""Authentication routes: registration, login, refresh, API key management."""

import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from agent_service.database import get_db
from api_gateway.security import (
    get_current_user,
    TokenData,
    create_token_pair,
    decode_token,
    generate_api_key,
)
from models.game_schemas import (
    UserRegister, UserLogin, UserResponse, TokenResponse,
)
from api_gateway.security import get_password_hash, verify_password
from models.game_models import UserDB

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/game", tags=["game-auth"])


def _handle_value_error(e: ValueError):
    raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------

@router.post("/auth/register", response_model=TokenResponse, status_code=201)
async def api_register(data: UserRegister, db: AsyncSession = Depends(get_db)):
    """Register a new user account."""
    try:
        user = UserDB(
            email=data.email,
            username=data.username,
            password_hash=get_password_hash(data.password),
            display_name=data.display_name or data.username,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        pair = create_token_pair(user.id, user.username, getattr(user, "role", "player"))
        return TokenResponse(
            access_token=pair.access_token,
            refresh_token=pair.refresh_token,
            user=UserResponse.model_validate(user),
        )
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Username or email already exists")


@router.post("/auth/login", response_model=TokenResponse)
async def api_login(data: UserLogin, db: AsyncSession = Depends(get_db)):
    """Login and receive JWT token."""
    try:
        result = await db.execute(select(UserDB).where(UserDB.username == data.username))
        user = result.scalar_one_or_none()
        if user is None or not verify_password(data.password, user.password_hash):
            raise ValueError("Invalid username or password")
        if not user.is_active:
            raise ValueError("Account is disabled")
        pair = create_token_pair(user.id, user.username, getattr(user, "role", "player"))
        return TokenResponse(
            access_token=pair.access_token,
            refresh_token=pair.refresh_token,
            user=UserResponse.model_validate(user),
        )
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.post("/auth/refresh")
async def api_refresh_token(refresh_token: str, db: AsyncSession = Depends(get_db)):
    """Exchange a refresh token for a new access + refresh token pair."""
    token_data = decode_token(refresh_token, expected_type="refresh")
    result = await db.execute(
        select(UserDB).where(UserDB.id == token_data.user_id, UserDB.is_active.is_(True))
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=401, detail="User account is inactive or no longer exists")
    pair = create_token_pair(user.id, user.username, getattr(user, "role", "player"))
    return {
        "access_token": pair.access_token,
        "refresh_token": pair.refresh_token,
        "token_type": "bearer",
    }


@router.get("/auth/me", response_model=UserResponse)
async def api_get_me(
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get current user info."""
    try:
        result = await db.execute(select(UserDB).where(UserDB.id == current_user.user_id))
        user = result.scalar_one_or_none()
        if user is None:
            raise ValueError("User not found")
        return UserResponse.model_validate(user)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/auth/api-key")
async def api_generate_api_key(
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate a new API key for the current user."""
    from models.game_models import UserDB
    result = await db.execute(select(UserDB).where(UserDB.id == current_user.user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    new_key = generate_api_key()
    user.api_key = new_key
    await db.commit()

    return {"api_key": new_key, "message": "Save this key — it won't be shown again."}


@router.delete("/auth/api-key")
async def api_revoke_api_key(
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Revoke the current user's API key."""
    from models.game_models import UserDB
    result = await db.execute(select(UserDB).where(UserDB.id == current_user.user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    user.api_key = None
    await db.commit()

    return {"message": "API key revoked"}
