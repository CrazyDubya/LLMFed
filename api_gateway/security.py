"""
Security and authentication utilities for the LLMFed API.

Provides JWT token generation/validation, API key authentication,
role-based access control (RBAC), and production safety checks.
"""

import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, status, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from passlib.context import CryptContext
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

# Role hierarchy: admin > owner > player > viewer
ROLE_HIERARCHY = {"admin": 4, "owner": 3, "player": 2, "viewer": 1}

# Production safety
_IS_PRODUCTION = os.getenv("ENV", "").lower() in ("production", "prod")

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# HTTP Bearer token scheme (auto_error=False allows optional auth)
security = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class TokenData(BaseModel):
    """Decoded token payload."""

    user_id: str
    username: Optional[str] = None
    role: str = "player"


class Token(BaseModel):
    """Token response model."""

    access_token: str
    token_type: str


class TokenPair(BaseModel):
    """Access + refresh token pair."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


# ---------------------------------------------------------------------------
# Production safety check
# ---------------------------------------------------------------------------


def validate_production_config() -> None:
    """Reject the default JWT secret in production.

    Should be called at application startup.
    """
    if _IS_PRODUCTION and SECRET_KEY == "dev-secret-key-change-in-production":
        raise RuntimeError(
            "FATAL: JWT_SECRET_KEY is set to the default dev value in production. "
            "Set a strong secret via the JWT_SECRET_KEY environment variable."
        )
    if _IS_PRODUCTION:
        logger.info("Production security config validated")


# ---------------------------------------------------------------------------
# Password utilities
# ---------------------------------------------------------------------------


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Generate password hash."""
    return pwd_context.hash(password)


# ---------------------------------------------------------------------------
# API key utilities
# ---------------------------------------------------------------------------


def generate_api_key() -> str:
    """Generate a random 48-character API key."""
    return secrets.token_urlsafe(36)


# ---------------------------------------------------------------------------
# Token creation
# ---------------------------------------------------------------------------


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(data: dict) -> str:
    """Create a JWT refresh token (longer-lived, for token renewal)."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_token_pair(user_id: str, username: str, role: str = "player") -> TokenPair:
    """Create both access and refresh tokens for a user."""
    payload = {"sub": user_id, "username": username, "role": role}
    return TokenPair(
        access_token=create_access_token(payload),
        refresh_token=create_refresh_token(payload),
    )


# ---------------------------------------------------------------------------
# Token decoding
# ---------------------------------------------------------------------------


def decode_token(token: str, expected_type: str = "access") -> TokenData:
    """Decode and validate a JWT token.

    Raises HTTPException on invalid or expired tokens.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        token_type = payload.get("type", "access")
        if token_type != expected_type:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Expected {expected_type} token, got {token_type}",
            )
        return TokenData(
            user_id=user_id,
            username=payload.get("username"),
            role=payload.get("role", "player"),
        )
    except jwt.InvalidTokenError:
        raise credentials_exception


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    x_api_key: Optional[str] = Header(None),
) -> TokenData:
    """Authenticate via JWT bearer token OR X-API-Key header.

    Raises 401 if neither is provided or both are invalid.
    """
    # Try JWT first
    if credentials is not None:
        return decode_token(credentials.credentials)

    # Try API key
    if x_api_key is not None:
        return _authenticate_api_key(x_api_key)

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required (Bearer token or X-API-Key header)",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    x_api_key: Optional[str] = Header(None),
) -> Optional[TokenData]:
    """Optionally authenticate — returns None if no credentials provided."""
    if credentials is not None:
        try:
            return decode_token(credentials.credentials)
        except HTTPException:
            return None
    if x_api_key is not None:
        try:
            return _authenticate_api_key(x_api_key)
        except HTTPException:
            return None
    return None


def require_role(*allowed_roles: str):
    """Dependency factory: require the authenticated user to have one of the allowed roles.

    Usage::

        @router.post("/admin-only")
        def admin_endpoint(user: TokenData = Depends(require_role("admin"))):
            ...

        @router.post("/owner-or-admin")
        def mixed_endpoint(user: TokenData = Depends(require_role("admin", "owner"))):
            ...
    """

    async def _check(
        current_user: TokenData = Depends(get_current_user),
    ) -> TokenData:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{current_user.role}' not authorized. Requires: {', '.join(allowed_roles)}",
            )
        return current_user

    return _check


def require_minimum_role(minimum_role: str):
    """Dependency factory: require at least *minimum_role* in the role hierarchy.

    Example: require_minimum_role("owner") allows admin and owner but blocks player/viewer.
    """
    min_level = ROLE_HIERARCHY.get(minimum_role, 0)

    async def _check(
        current_user: TokenData = Depends(get_current_user),
    ) -> TokenData:
        user_level = ROLE_HIERARCHY.get(current_user.role, 0)
        if user_level < min_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires at least '{minimum_role}' role",
            )
        return current_user

    return _check


# ---------------------------------------------------------------------------
# API key authentication (internal helper)
# ---------------------------------------------------------------------------


def _authenticate_api_key(api_key: str) -> TokenData:
    """Look up a user by API key. Raises 401 if not found."""
    # Lazy import to avoid circular dependency with database
    from agent_service.database import SessionLocal
    from models.game_models import UserDB

    db = None
    try:
        db = SessionLocal()
        user = db.query(UserDB).filter(UserDB.api_key == api_key).first()
        if user is None or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key",
            )
        return TokenData(
            user_id=user.id,
            username=user.username,
            role=getattr(user, "role", "player"),
        )
    except HTTPException:
        raise
    except Exception:
        if db is not None:
            db.rollback()
        raise
    finally:
        if db is not None:
            db.close()
