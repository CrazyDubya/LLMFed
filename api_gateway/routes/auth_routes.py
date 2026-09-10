"""Authentication routes: registration, login, refresh, API key management."""

import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from agent_service.database import get_db
from api_gateway.security import (
    get_current_user,
    require_role,
    TokenData,
    create_token_pair,
    decode_token,
    generate_api_key,
)
from models.game_schemas import (
    UserRegister, UserLogin, UserResponse, TokenResponse,
)
from game_service.auth_service import register_user, authenticate_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/game", tags=["game-auth"])


def _handle_value_error(e: ValueError):
    raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------

@router.post("/auth/register", response_model=TokenResponse, status_code=201)
def api_register(data: UserRegister, db: Session = Depends(get_db)):
    """Register a new user account."""
    try:
        user = register_user(db, data.email, data.username, data.password, data.display_name)
        pair = create_token_pair(user.id, user.username, getattr(user, "role", "player"))
        return TokenResponse(
            access_token=pair.access_token,
            user=UserResponse.model_validate(user),
        )
    except ValueError as e:
        _handle_value_error(e)


@router.post("/auth/login", response_model=TokenResponse)
def api_login(data: UserLogin, db: Session = Depends(get_db)):
    """Login and receive JWT token."""
    try:
        user = authenticate_user(db, data.username, data.password)
        pair = create_token_pair(user.id, user.username, getattr(user, "role", "player"))
        return TokenResponse(
            access_token=pair.access_token,
            user=UserResponse.model_validate(user),
        )
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.post("/auth/refresh")
def api_refresh_token(refresh_token: str, db: Session = Depends(get_db)):
    """Exchange a refresh token for a new access + refresh token pair."""
    token_data = decode_token(refresh_token, expected_type="refresh")
    pair = create_token_pair(token_data.user_id, token_data.username or "", token_data.role)
    return {
        "access_token": pair.access_token,
        "refresh_token": pair.refresh_token,
        "token_type": "bearer",
    }


@router.get("/auth/me", response_model=UserResponse)
def api_get_me(
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get current user info."""
    from game_service.auth_service import get_user_by_id
    try:
        user = get_user_by_id(db, current_user.user_id)
        return UserResponse.model_validate(user)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/auth/api-key")
def api_generate_api_key(
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate a new API key for the current user."""
    from models.game_models import UserDB
    user = db.query(UserDB).filter(UserDB.id == current_user.user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    new_key = generate_api_key()
    user.api_key = new_key
    db.commit()

    return {"api_key": new_key, "message": "Save this key — it won't be shown again."}


@router.delete("/auth/api-key")
def api_revoke_api_key(
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Revoke the current user's API key."""
    from models.game_models import UserDB
    user = db.query(UserDB).filter(UserDB.id == current_user.user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    user.api_key = None
    db.commit()

    return {"message": "API key revoked"}
