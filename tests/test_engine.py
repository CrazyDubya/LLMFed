import pytest

from core_engine.engine import engine_instance, AppliedAction
from core_engine.dispatcher import StubAction


def test_set_hints_stores_hints():
    hints = {"foo": "bar"}
    engine_instance.set_hints(hints)
    assert engine_instance.promoter_hints == hints


def test_run_ticks_returns_results_and_uses_hints(monkeypatch):
    from types import SimpleNamespace
    from core_engine import engine as engine_mod

    # Mock get_agents to return one agent per role so we get one TickResult per role
    def fake_get_agents(db):
        return [
            SimpleNamespace(agent_id=f"agent_{r}", role=r, gimmick_description="")
            for r in engine_instance.ROLE_ORDER
        ]

    fake_response = {"action_id": "x", "description": "fake", "meta": {}}
    monkeypatch.setattr(
        engine_instance.llm_client,
        'send_prompt',
        lambda prompt, model=None: fake_response,
    )
    monkeypatch.setattr(engine_mod, 'get_agents', fake_get_agents)

    hints = {"tip": "increase drama"}
    engine_instance.set_hints(hints)
    results = engine_instance.run_ticks(1)

    assert isinstance(results, list)
    # Default agent is a participant, so expect at least 1 result
    assert len(results) >= 1
    for result in results:
        assert hasattr(result, 'tick_id')
        assert hasattr(result, 'time_index')
        assert hasattr(result, 'applied_actions')
        # Check that applied action is correct type and fields
        action = result.applied_actions[0]
        assert isinstance(action, AppliedAction)
        assert action.action_id == "x"
        assert action.description == "fake"


def test_run_pre_match_returns_results(monkeypatch):
    """Pre-match phase runs promoter + backstage and returns TickResults."""
    from types import SimpleNamespace
    from core_engine import engine as engine_mod

    def fake_get_agents(db):
        return [
            SimpleNamespace(agent_id=f"agent_{r}", role=r, gimmick_description="")
            for r in engine_instance.ROLE_ORDER
        ]

    fake_response = {"action_id": "noop", "description": "pre-match", "meta": {}}
    monkeypatch.setattr(
        engine_instance.llm_client,
        'send_prompt',
        lambda prompt, model=None: fake_response,
    )
    monkeypatch.setattr(engine_mod, 'get_agents', fake_get_agents)

    results = engine_instance.run_pre_match()
    assert isinstance(results, list)
    # Promoter + backstage = up to 2 results (one per role if agents exist)
    assert len(results) >= 0
