"""
Authentication and user management service.
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from models.game_models import UserDB
from api_gateway.security import get_password_hash, verify_password, create_access_token

logger = logging.getLogger(__name__)


def register_user(db: Session, email: str, username: str, password: str,
                  display_name: str = None) -> UserDB:
    """Register a new user account."""
    password_hash = get_password_hash(password)
    user = UserDB(
        email=email,
        username=username,
        password_hash=password_hash,
        display_name=display_name or username,
    )
    db.add(user)
    try:
        db.commit()
        db.refresh(user)
        return user
    except IntegrityError:
        db.rollback()
        raise ValueError("Username or email already exists")


def authenticate_user(db: Session, username: str, password: str) -> UserDB:
    """Authenticate a user and return the user record."""
    user = db.query(UserDB).filter(UserDB.username == username).first()
    if not user or not verify_password(password, user.password_hash):
        raise ValueError("Invalid username or password")
    if not user.is_active:
        raise ValueError("Account is disabled")
    return user


def create_user_token(user: UserDB) -> str:
    """Create a JWT access token for a user."""
    return create_access_token(
        data={"sub": user.id, "username": user.username}
    )


def get_user_by_id(db: Session, user_id: str) -> UserDB:
    """Get a user by their ID."""
    user = db.query(UserDB).filter(UserDB.id == user_id).first()
    if not user:
        raise ValueError("User not found")
    return user
