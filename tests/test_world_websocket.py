"""Regression coverage for the world feed's FastAPI WebSocket route."""

from fastapi.testclient import TestClient

from api_gateway.main import app


def test_world_feed_connects_and_handles_messages():
    with TestClient(app, base_url="http://localhost") as client:
        with client.websocket_connect("ws://localhost/ws/test-world") as websocket:
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
