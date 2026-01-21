"""
Tests for API security features.

Tests JWT authentication, CORS, rate limiting, and security headers.
"""

import pytest
from fastapi.testclient import TestClient
from api_gateway.security import create_access_token, decode_token, TokenData
from datetime import timedelta


def test_create_access_token():
    """Test JWT token creation."""
    token = create_access_token(
        data={"sub": "test_user", "username": "testuser"},
        expires_delta=timedelta(minutes=15)
    )
    
    assert token is not None
    assert isinstance(token, str)
    assert len(token) > 50  # JWT tokens are typically long


def test_decode_valid_token():
    """Test decoding a valid JWT token."""
    token = create_access_token(
        data={"sub": "test_user", "username": "testuser"}
    )
    
    token_data = decode_token(token)
    
    assert isinstance(token_data, TokenData)
    assert token_data.user_id == "test_user"
    assert token_data.username == "testuser"


def test_decode_invalid_token():
    """Test decoding an invalid JWT token."""
    from fastapi import HTTPException
    
    with pytest.raises(HTTPException) as exc_info:
        decode_token("invalid_token_string")
    
    assert exc_info.value.status_code == 401
    assert "Could not validate credentials" in exc_info.value.detail


def test_decode_expired_token():
    """Test decoding an expired JWT token."""
    from fastapi import HTTPException
    import time
    
    # Create token that expires immediately
    token = create_access_token(
        data={"sub": "test_user"},
        expires_delta=timedelta(seconds=-1)  # Already expired
    )
    
    with pytest.raises(HTTPException) as exc_info:
        decode_token(token)
    
    assert exc_info.value.status_code == 401


def test_password_hashing():
    """Test password hashing and verification."""
    from api_gateway.security import get_password_hash, verify_password
    
    password = "test_password_123"
    hashed = get_password_hash(password)
    
    assert hashed != password
    assert len(hashed) > 50
    
    # Verify correct password
    assert verify_password(password, hashed) is True
    
    # Verify incorrect password
    assert verify_password("wrong_password", hashed) is False


def test_security_headers_present():
    """Test that security headers are present in responses."""
    # This test would require the full app context
    # For now, we'll test the middleware logic
    from api_gateway.main import app
    
    client = TestClient(app)
    response = client.get("/")
    
    # Check for security headers
    assert "x-content-type-options" in response.headers
    assert response.headers["x-content-type-options"] == "nosniff"
    
    assert "x-frame-options" in response.headers
    assert response.headers["x-frame-options"] == "DENY"
    
    assert "x-xss-protection" in response.headers
    assert "strict-transport-security" in response.headers
    assert "content-security-policy" in response.headers


def test_cors_headers():
    """Test CORS headers configuration."""
    from api_gateway.main import app
    
    client = TestClient(app)
    
    # Test preflight request
    response = client.options(
        "/",
        headers={"Origin": "http://localhost:3000"}
    )
    
    # Check CORS headers
    assert "access-control-allow-origin" in response.headers


def test_rate_limiting_decorator():
    """Test that rate limiting decorator is applied."""
    from api_gateway.main import app
    
    # This would require actual rate limit testing
    # For now, verify the app has the limiter
    assert hasattr(app.state, 'limiter')


def test_debug_endpoint_protection():
    """Test that debug endpoint is protected."""
    from api_gateway.main import app
    import os
    
    client = TestClient(app)
    
    # Ensure DEBUG_MODE is not set
    original_debug = os.environ.get("DEBUG_MODE")
    if "DEBUG_MODE" in os.environ:
        del os.environ["DEBUG_MODE"]
    
    try:
        response = client.get("/engine/debug")
        
        # Should return 404 when debug is disabled
        assert response.status_code == 404
        assert response.json()["detail"] == "Endpoint not found"
    finally:
        # Restore original value
        if original_debug:
            os.environ["DEBUG_MODE"] = original_debug


def test_token_expiration_configuration():
    """Test token expiration configuration."""
    from api_gateway.security import ACCESS_TOKEN_EXPIRE_MINUTES
    
    assert isinstance(ACCESS_TOKEN_EXPIRE_MINUTES, int)
    assert ACCESS_TOKEN_EXPIRE_MINUTES > 0


def test_jwt_secret_key_configuration():
    """Test JWT secret key configuration."""
    from api_gateway.security import SECRET_KEY
    
    assert SECRET_KEY is not None
    assert len(SECRET_KEY) > 0


def test_token_data_model():
    """Test TokenData model."""
    token_data = TokenData(user_id="test123", username="testuser")
    
    assert token_data.user_id == "test123"
    assert token_data.username == "testuser"


def test_token_response_model():
    """Test Token response model."""
    from api_gateway.security import Token
    
    token = Token(access_token="test_token", token_type="bearer")
    
    assert token.access_token == "test_token"
    assert token.token_type == "bearer"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
