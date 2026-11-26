"""Tests for core API routes (agents, federations, engine, health, metrics).

Uses FastAPI TestClient to exercise the HTTP layer end-to-end against
an in-memory SQLite database.
"""
import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from agent_service.database import SessionLocal
from api_gateway.main import app  # noqa: E402
from models.game_models import GameFederationDB, ShowDB, WorldDB

# Table creation for the agent-service tables happens once per session via
# the autouse fixture in tests/conftest.py (init_db() is async and can't be
# called synchronously here at import/collection time).

client = TestClient(
    app,
    base_url="http://localhost",
    raise_server_exceptions=False,
)


@pytest.fixture(scope="module", autouse=True)
def _authenticated_client(_create_agent_service_tables):
    """Register a real user and attach its token to the module client.

    core_routes.py's endpoints require authentication, and get_current_user
    re-validates the token's subject against the users table — a
    self-signed token for a non-existent user id would 401. Depending on
    the session-scoped table-creation fixture ensures the users table
    exists before this registration runs.
    """
    with patch("api_gateway.routes.auth_routes.get_password_hash", lambda p: f"test-hash:{p}"):
        resp = client.post("/game/auth/register", json={
            "email": f"core-routes-{uuid.uuid4().hex[:10]}@test.local",
            "username": f"core_routes_{uuid.uuid4().hex[:10]}",
            "password": "irrelevant",
        })
    token = resp.json()["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"
    yield


def _unique(prefix: str = "") -> str:
    """Generate a unique name for test isolation."""
    return f"{prefix}{uuid.uuid4().hex[:8]}"


class TestWorldShows:
    @pytest.fixture
    def listing_url(self):
        world_id = _unique("shows-")
        other_id = _unique("other-")
        fed_id = _unique("fed-")
        other_fed = _unique("fed-")
        with SessionLocal.begin() as db:
            db.add_all([WorldDB(id=world_id, name=world_id), WorldDB(id=other_id, name=other_id)])
            db.flush()
            db.add_all([
                GameFederationDB(id=fed_id, world_id=world_id, name="Summit Wrestling"),
                GameFederationDB(id=other_fed, world_id=other_id, name="Other Wrestling"),
            ])
            db.flush()
            db.add_all([
                ShowDB(id=f"{world_id}-{i:03}", world_id=world_id, federation_id=fed_id,
                       name=f"Show {i}", game_date="2026-02-01" if i > 104 else "2026-01-01",
                       is_completed=i <= 104)
                for i in range(1, 206)
            ])
            db.add(ShowDB(world_id=other_id, federation_id=other_fed, name="Other show",
                          game_date="2026-03-01", is_completed=True))
        return f"/worlds/{world_id}/shows"

    def test_offset_reaches_all_shows_in_stable_order(self, listing_url):
        rows = []
        for offset in (0, 100, 200):
            response = client.get(listing_url, params={"limit": 100, "offset": offset})
            assert response.status_code == 200
            rows.extend(response.json())
        assert [row["name"] for row in rows] == [f"Show {i}" for i in range(205, 0, -1)]
        assert client.get(listing_url, params={"offset": -1}).status_code == 422
        assert client.get(listing_url, params={"limit": 201}).status_code == 422

    def test_filtered_pages_include_global_counts(self, listing_url):
        for status, offset, expected in (
            ("completed", 100, [4, 3, 2, 1]),
            ("upcoming", 100, [105]),
            ("completed", 200, []),
        ):
            response = client.get(listing_url, params={
                "include_counts": True, "status": status, "offset": offset, "limit": 100,
            })
            assert response.status_code == 200
            page = response.json()
            assert page["counts"] == {"all": 205, "completed": 104, "upcoming": 101}
            assert [row["name"] for row in page["shows"]] == [f"Show {i}" for i in expected]
        legacy = client.get(listing_url, params={"limit": 200, "completed_only": True})
        assert legacy.status_code == 200
        assert len(legacy.json()) == 104
        assert all(row["is_completed"] for row in legacy.json())


# ---------------------------------------------------------------------------
# Health & Monitoring
# ---------------------------------------------------------------------------

class TestHealthRoutes:
    def test_root_returns_welcome(self):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "Welcome" in resp.json()["message"]

    def test_health_check(self):
        resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert "version" in body
        assert "services" in body

    def test_metrics_endpoint(self):
        resp = client.get("/metrics/performance")
        assert resp.status_code == 200
        body = resp.json()
        assert "endpoints" in body
        assert "timestamp" in body

    def test_metrics_reset(self):
        resp = client.post("/metrics/performance/reset")
        assert resp.status_code == 200
        assert resp.json()["message"] == "Metrics reset successfully"


# ---------------------------------------------------------------------------
# Agent CRUD
# ---------------------------------------------------------------------------

def _agent_payload(**overrides):
    base = {
        "user_id": "test-user-1",
        "name": _unique("Agent-"),
        "role": "participant",
        "gimmick_description": "A test wrestler",
        "llm_config": {"model_name": "gpt-4", "temperature": 0.7},
        "federation_id": _unique("fed-"),
    }
    base.update(overrides)
    return base


class TestAgentRoutes:
    def test_create_agent(self):
        payload = _agent_payload()
        resp = client.post("/agents", json=payload)
        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == payload["name"]
        assert body["role"] == "participant"
        assert "agent_id" in body

    def test_create_agent_invalid_role(self):
        payload = _agent_payload(role="invalid_role")
        resp = client.post("/agents", json=payload)
        assert resp.status_code == 422

    def test_get_agent(self):
        create_resp = client.post("/agents", json=_agent_payload())
        agent_id = create_resp.json()["agent_id"]

        resp = client.get(f"/agents/{agent_id}")
        assert resp.status_code == 200
        assert resp.json()["agent_id"] == agent_id

    def test_get_agent_not_found(self):
        resp = client.get("/agents/nonexistent-id")
        assert resp.status_code == 404

    def test_update_agent(self):
        create_resp = client.post("/agents", json=_agent_payload())
        agent_id = create_resp.json()["agent_id"]

        resp = client.patch(f"/agents/{agent_id}", json={"name": "Updated Name"})
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated Name"

    def test_update_agent_not_found(self):
        resp = client.patch("/agents/nonexistent-id", json={"name": "X"})
        assert resp.status_code == 404

    def test_delete_agent(self):
        create_resp = client.post("/agents", json=_agent_payload())
        agent_id = create_resp.json()["agent_id"]

        resp = client.delete(f"/agents/{agent_id}")
        assert resp.status_code == 204

        resp = client.get(f"/agents/{agent_id}")
        assert resp.status_code == 404

    def test_delete_agent_not_found(self):
        resp = client.delete("/agents/nonexistent-id")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Federation CRUD
# ---------------------------------------------------------------------------

def _fed_payload(**overrides):
    base = {
        "name": _unique("Fed-"),
        "description": "A test federation",
        "tier": "independent",
        "owner_user_id": "test-owner-1",
    }
    base.update(overrides)
    return base


class TestFederationRoutes:
    def test_create_federation(self):
        payload = _fed_payload()
        resp = client.post("/federations", json=payload)
        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == payload["name"]
        assert "federation_id" in body

    def test_list_federations(self):
        client.post("/federations", json=_fed_payload())
        resp = client.get("/federations")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_get_federation(self):
        create_resp = client.post("/federations", json=_fed_payload())
        fed_id = create_resp.json()["federation_id"]

        resp = client.get(f"/federations/{fed_id}")
        assert resp.status_code == 200
        assert resp.json()["federation_id"] == fed_id

    def test_get_federation_not_found(self):
        resp = client.get("/federations/nonexistent-id")
        assert resp.status_code == 404

    def test_update_federation(self):
        create_resp = client.post("/federations", json=_fed_payload())
        fed_id = create_resp.json()["federation_id"]

        resp = client.patch(f"/federations/{fed_id}", json={"name": _unique("UpdFed-")})
        assert resp.status_code == 200

    def test_delete_federation(self):
        create_resp = client.post("/federations", json=_fed_payload())
        fed_id = create_resp.json()["federation_id"]

        resp = client.delete(f"/federations/{fed_id}")
        assert resp.status_code == 204

    def test_delete_federation_not_found(self):
        resp = client.delete("/federations/nonexistent-id")
        assert resp.status_code == 404

    def test_delete_federation_with_agents_fails(self):
        create_resp = client.post("/federations", json=_fed_payload())
        fed_id = create_resp.json()["federation_id"]

        agent = _agent_payload(federation_id=fed_id)
        client.post("/agents", json=agent)

        resp = client.delete(f"/federations/{fed_id}")
        assert resp.status_code == 409

    def test_list_agents_in_federation(self):
        create_resp = client.post("/federations", json=_fed_payload())
        fed_id = create_resp.json()["federation_id"]

        agent = _agent_payload(federation_id=fed_id)
        client.post("/agents", json=agent)

        resp = client.get(f"/federations/{fed_id}/agents")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1


# ---------------------------------------------------------------------------
# Engine routes
# ---------------------------------------------------------------------------

class TestEngineRoutes:
    def test_engine_advance(self):
        from unittest.mock import patch
        from core_engine.engine import Engine
        with patch.object(Engine, 'run_ticks', return_value=[]):
            resp = client.post("/engine/advance?n_ticks=1")
            assert resp.status_code == 200
            assert isinstance(resp.json(), list)

    def test_engine_requests(self):
        resp = client.get("/engine/requests")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_engine_narrative(self):
        resp = client.get("/engine/narrative")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_engine_debug_disabled_by_default(self):
        resp = client.get("/engine/debug")
        assert resp.status_code == 404

    def test_engine_debug_returns_tables_and_state_when_enabled(self, monkeypatch):
        monkeypatch.setenv("DEBUG_MODE", "true")

        resp = client.get("/engine/debug")

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert {"agents", "engine_requests"}.issubset(body["tables"])
        assert body["engine_state"]["current_tick"] == app.state.engine.state.current_tick
        assert isinstance(body["engine_state"]["pending_requests"], int)
