"""Tests for simulation orchestrator."""

import pytest
import uuid

from models.calendar import Card, Match
from simulation.orchestrator import build_demo_card, SimulationOrchestrator


def test_build_demo_card_returns_card():
    """build_demo_card returns a Card with at least one match."""
    from agent_service.database import SessionLocal, init_db
    from agent_service.crud import get_agents, create_agent
    from models.entities import AgentCreateData
    from core_engine.engine import engine_instance

    init_db()
    db = SessionLocal()
    try:
        agents = get_agents(db)
        if len(agents) < 2:
            for role in engine_instance.ROLE_ORDER:
                if not any(getattr(a, "role", None) == role for a in agents):
                    create_agent(
                        db,
                        AgentCreateData(
                            user_id=str(uuid.uuid4()),
                            name=f"Test_{role}",
                            role=role,
                            gimmick_description="Test",
                            llm_config={"model": "test", "temperature": 0.7},
                        ),
                    )
            db.commit()
    finally:
        db.close()

    card = build_demo_card("test-fed")
    assert isinstance(card, Card)
    assert card.federation_id == "test-fed"
    assert len(card.matches) >= 1
    match = card.matches[0]
    assert match.card_id == card.card_id
    assert len(match.participant_ids) >= 0


def test_run_card_with_mock_llm(monkeypatch):
    """run_card runs matches (with mocked LLM and federation)."""
    from core_engine import engine as engine_mod
    from agent_service.database import SessionLocal, init_db
    from agent_service.crud import create_federation, get_federation_by_id
    from models.entities import FederationCreateData
    from types import SimpleNamespace

    init_db()
    db = SessionLocal()
    try:
        from models.db_models import FederationDB
        fed = db.query(FederationDB).first()
        fed_id = fed.federation_id if fed else None
        if not fed_id:
            fed = create_federation(
                db,
                FederationCreateData(
                    name="Test Fed Sim",
                    description="Test",
                    tier="test",
                    owner_user_id=str(uuid.uuid4()),
                ),
            )
            fed_id = fed.federation_id if fed else str(uuid.uuid4())
        db.commit()
    finally:
        db.close()

    fake_response = {"action_id": "noop", "description": "fake", "meta": {}}
    monkeypatch.setattr(
        engine_mod.engine_instance.llm_client,
        "send_prompt",
        lambda prompt, model=None: fake_response,
    )
    agents = [
        SimpleNamespace(agent_id=f"a_{r}", role=r, gimmick_description="", llm_config={})
        for r in engine_mod.engine_instance.ROLE_ORDER
    ]
    monkeypatch.setattr(engine_mod, "get_agents", lambda db: agents)

    cid = str(uuid.uuid4())
    mid = str(uuid.uuid4())
    card = Card(
        card_id=cid,
        federation_id=fed_id,
        name="Test Card",
        matches=[
            Match(
                match_id=mid,
                card_id=cid,
                participant_ids=["a_participant", "a_participant"],
            ),
        ],
    )

    orch = SimulationOrchestrator()
    results = orch.run_card(card, fed_id, max_ticks_per_match=5)
    assert isinstance(results, list)
    assert len(results) == 1
    assert len(results[0]) >= 1
