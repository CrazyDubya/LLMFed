"""Tests for core API routes (agents, federations, engine, health, metrics).

Uses FastAPI TestClient to exercise the HTTP layer end-to-end against
an in-memory SQLite database.
"""
import os
import uuid
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

# Allow the TestClient's "testserver" host through TrustedHostMiddleware
os.environ["ALLOWED_HOSTS"] = "localhost,127.0.0.1,testserver"

from api_gateway.main import app  # noqa: E402
from agent_service.database import init_db  # noqa: E402

# Initialise the test database once
init_db()

client = TestClient(app, raise_server_exceptions=False)


def _unique(prefix: str = "") -> str:
    """Generate a unique name for test isolation."""
    return f"{prefix}{uuid.uuid4().hex[:8]}"


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
        resp = client.get("/metrics")
        assert resp.status_code == 200
        body = resp.json()
        assert "endpoints" in body
        assert "timestamp" in body

    def test_metrics_reset(self):
        resp = client.post("/metrics/reset")
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
