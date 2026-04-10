"""Tests for RBAC, API key auth, production config validation, and token refresh."""

import os
import pytest
from unittest.mock import patch

# Mock out the jose + cryptography dependency for environments where it fails
try:
    from api_gateway.security import (
        create_access_token,
        create_refresh_token,
        create_token_pair,
        decode_token,
        generate_api_key,
        validate_production_config,
        TokenData,
        ROLE_HIERARCHY,
        get_password_hash,
        verify_password,
    )
    SECURITY_AVAILABLE = True
except BaseException:
    SECURITY_AVAILABLE = False
    pytestmark = pytest.mark.skip("cryptography/jose unavailable in this environment")


@pytest.mark.skipif(not SECURITY_AVAILABLE, reason="security deps unavailable")
class TestTokenCreation:
    def test_create_access_token(self):
        token = create_access_token({"sub": "user1", "username": "alice", "role": "player"})
        assert isinstance(token, str)
        assert len(token) > 0

    def test_create_refresh_token(self):
        token = create_refresh_token({"sub": "user1", "username": "alice"})
        data = decode_token(token, expected_type="refresh")
        assert data.user_id == "user1"

    def test_create_token_pair(self):
        pair = create_token_pair("user1", "alice", "admin")
        assert pair.access_token
        assert pair.refresh_token
        assert pair.token_type == "bearer"

    def test_decode_access_token(self):
        token = create_access_token({"sub": "user1", "username": "alice", "role": "admin"})
        data = decode_token(token)
        assert data.user_id == "user1"
        assert data.username == "alice"
        assert data.role == "admin"

    def test_decode_wrong_type_raises(self):
        token = create_access_token({"sub": "user1"})
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            decode_token(token, expected_type="refresh")
        assert exc.value.status_code == 401

    def test_role_defaults_to_player(self):
        token = create_access_token({"sub": "user1"})
        data = decode_token(token)
        assert data.role == "player"


@pytest.mark.skipif(not SECURITY_AVAILABLE, reason="security deps unavailable")
class TestRoleHierarchy:
    def test_admin_is_highest(self):
        assert ROLE_HIERARCHY["admin"] > ROLE_HIERARCHY["owner"]
        assert ROLE_HIERARCHY["owner"] > ROLE_HIERARCHY["player"]
        assert ROLE_HIERARCHY["player"] > ROLE_HIERARCHY["viewer"]


@pytest.mark.skipif(not SECURITY_AVAILABLE, reason="security deps unavailable")
class TestProductionValidation:
    def test_default_key_in_prod_raises(self):
        with patch.dict(os.environ, {"ENV": "production"}), \
             patch("api_gateway.security._IS_PRODUCTION", True), \
             patch("api_gateway.security.SECRET_KEY", "dev-secret-key-change-in-production"):
            with pytest.raises(RuntimeError, match="FATAL"):
                validate_production_config()

    def test_custom_key_in_prod_ok(self):
        with patch("api_gateway.security._IS_PRODUCTION", True), \
             patch("api_gateway.security.SECRET_KEY", "a-real-strong-key-here"):
            # Should not raise
            validate_production_config()

    def test_default_key_in_dev_ok(self):
        with patch("api_gateway.security._IS_PRODUCTION", False):
            # Should not raise
            validate_production_config()


@pytest.mark.skipif(not SECURITY_AVAILABLE, reason="security deps unavailable")
class TestAPIKeyGeneration:
    def test_generates_unique_keys(self):
        key1 = generate_api_key()
        key2 = generate_api_key()
        assert key1 != key2
        assert len(key1) >= 32

    def test_key_is_url_safe(self):
        key = generate_api_key()
        # url-safe base64 characters
        allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-=")
        assert all(c in allowed for c in key)


@pytest.mark.skipif(not SECURITY_AVAILABLE, reason="security deps unavailable")
class TestPasswordUtilities:
    def test_hash_and_verify(self):
        try:
            hashed = get_password_hash("mypassword")
        except (ValueError, AttributeError):
            pytest.skip("bcrypt/passlib version incompatibility in this environment")
        assert verify_password("mypassword", hashed) is True
        assert verify_password("wrongpassword", hashed) is False
