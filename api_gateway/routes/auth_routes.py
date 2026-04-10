"""Authentication routes: registration, login, me."""

import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from agent_service.database import get_db
from api_gateway.security import get_current_user, TokenData
from models.game_schemas import (
    UserRegister, UserLogin, UserResponse, TokenResponse,
)
from game_service.auth_service import register_user, authenticate_user, create_user_token

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
        token = create_user_token(user)
        return TokenResponse(
            access_token=token,
            user=UserResponse.model_validate(user),
        )
    except ValueError as e:
        _handle_value_error(e)


@router.post("/auth/login", response_model=TokenResponse)
def api_login(data: UserLogin, db: Session = Depends(get_db)):
    """Login and receive JWT token."""
    try:
        user = authenticate_user(db, data.username, data.password)
        token = create_user_token(user)
        return TokenResponse(
            access_token=token,
            user=UserResponse.model_validate(user),
        )
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


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
