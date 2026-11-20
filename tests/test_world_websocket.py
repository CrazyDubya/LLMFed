"""Regression coverage for the world feed's FastAPI WebSocket route."""

from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from api_gateway.main import app

WS_POLICY_VIOLATION = 1008


def _register(client: TestClient) -> dict:
    suffix = uuid4().hex[:10]
    with patch("api_gateway.routes.auth_routes.get_password_hash", lambda p: f"test-hash:{p}"):
        response = client.post("/game/auth/register", json={
            "email": f"ws-{suffix}@example.com",
            "username": f"ws_{suffix}",
            "password": "correct-password",
        })
    assert response.status_code == 201
    return response.json()


@pytest.fixture
def client():
    with TestClient(app, base_url="http://localhost") as test_client:
        yield test_client


def test_world_feed_connects_and_handles_messages(client):
    token = _register(client)["access_token"]
    with client.websocket_connect("ws://localhost/ws/test-world", subprotocols=["bearer", token]) as websocket:
        assert websocket.accepted_subprotocol == "bearer"
        assert websocket.receive_json() == {
            "type": "connected",
            "world_id": "test-world",
            "message": "Connected to world feed",
        }
        websocket.send_json({"type": "ping"})
        assert websocket.receive_json() == {"type": "pong"}
        websocket.send_text("")
        assert websocket.receive_json() == {
            "type": "error", "message": "Invalid JSON",
        }
        websocket.send_json({"type": "unknown"})
        assert websocket.receive_json() == {
            "type": "error", "message": "Unknown message type: unknown",
        }


@pytest.mark.parametrize(("subprotocols", "headers"), [
    ([], {}),
    (["bearer", "not-a-jwt"], {}),
    ([], {"Authorization": "Bearer not-a-jwt"}),
    ([], {"X-API-Key": "not-a-key"}),
], ids=["no-credentials", "bad-subprotocol-token", "bad-bearer", "bad-api-key"])
def test_world_feed_rejects_unauthenticated_clients(client, subprotocols, headers):
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("ws://localhost/ws/test-world", subprotocols=subprotocols, headers=headers):
            pass
    assert exc_info.value.code == WS_POLICY_VIOLATION


def test_world_feed_accepts_bearer_header_and_api_key(client):
    registered = _register(client)
    bearer = {"Authorization": f"Bearer {registered['access_token']}"}
    api_key = client.post("/game/auth/api-key", headers=bearer).json()["api_key"]
    for headers in (bearer, {"X-API-Key": api_key}):
        with client.websocket_connect("ws://localhost/ws/test-world", headers=headers) as websocket:
            assert websocket.receive_json()["type"] == "connected"


def test_world_feed_ignores_token_in_query_string(client):
    token = _register(client)["access_token"]
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(f"ws://localhost/ws/test-world?token={token}"):
            pass
    assert exc_info.value.code == WS_POLICY_VIOLATION
