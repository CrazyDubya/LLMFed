"""Integration tests for the game authentication routes."""

from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from api_gateway.main import app
from models.game_models import UserDB
from agent_service.database import AsyncSessionLocal


client = TestClient(app, base_url="http://localhost")


def _credentials():
    suffix = uuid4().hex[:10]
    return {
        "email": f"auth-{suffix}@example.com",
        "username": f"auth_{suffix}",
        "password": "correct-password",
    }


def _fake_hash(password: str) -> str:
    return f"test-hash:{password}"


def _fake_verify(password: str, hashed: str) -> bool:
    return hashed == _fake_hash(password)


def test_auth_register_login_me_and_api_key_lifecycle():
    credentials = _credentials()
    with patch("api_gateway.routes.auth_routes.get_password_hash", _fake_hash), patch(
        "api_gateway.routes.auth_routes.verify_password", _fake_verify
    ):
        registered = client.post("/game/auth/register", json=credentials)
        assert registered.status_code == 201
        access_token = registered.json()["access_token"]

        me = client.get(
            "/game/auth/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert me.status_code == 200
        assert me.json()["username"] == credentials["username"]

        logged_in = client.post(
            "/game/auth/login",
            json={"username": credentials["username"], "password": credentials["password"]},
        )
        assert logged_in.status_code == 200

        api_key_response = client.post(
            "/game/auth/api-key",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert api_key_response.status_code == 200
        api_key = api_key_response.json()["api_key"]

        api_key_me = client.get("/game/auth/me", headers={"X-API-Key": api_key})
        assert api_key_me.status_code == 200

        revoked = client.delete(
            "/game/auth/api-key",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert revoked.status_code == 200
        assert client.get("/game/auth/me", headers={"X-API-Key": api_key}).status_code == 401


def test_inactive_user_cannot_use_existing_access_or_refresh_token():
    credentials = _credentials()
    with patch("api_gateway.routes.auth_routes.get_password_hash", _fake_hash), patch(
        "api_gateway.routes.auth_routes.verify_password", _fake_verify
    ):
        registered = client.post("/game/auth/register", json=credentials)
        assert registered.status_code == 201
        tokens = registered.json()
        user_id = tokens["user"]["id"]

        # Disable the account using the same async database used by the app.
        import asyncio

        async def disable_user():
            async with AsyncSessionLocal() as db:
                user = await db.get(UserDB, user_id)
                user.is_active = False
                await db.commit()

        asyncio.run(disable_user())

        assert client.get(
            "/game/auth/me",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        ).status_code == 401
        assert client.post(
            "/game/auth/refresh",
            params={"refresh_token": tokens["refresh_token"]},
        ).status_code == 401
