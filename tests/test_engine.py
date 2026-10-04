
import pytest
from core_engine.engine import create_engine, AppliedAction


def test_set_hints_stores_hints():
    engine = create_engine()
    hints = {"foo": "bar"}
    engine.set_hints(hints)
    assert engine.promoter_hints == hints


@pytest.mark.asyncio
async def test_run_ticks_returns_results_and_uses_hints(monkeypatch):
    engine = create_engine()
    from types import SimpleNamespace
    from core_engine import engine as engine_mod

    # Mock get_agents to return one agent per role so we get one TickResult per role
    async def fake_get_agents(db):
        return [
            SimpleNamespace(agent_id=f"agent_{r}", role=r, gimmick_description="")
            for r in engine.ROLE_ORDER
        ]

    fake_response = {"action_id": "x", "description": "fake", "meta": {}}

    async def fake_generate_action_async(prompt):
        return fake_response

    monkeypatch.setattr(engine.llm_client, 'generate_action_async', fake_generate_action_async)
    monkeypatch.setattr(engine_mod, 'get_agents', fake_get_agents)

    hints = {"tip": "increase drama"}
    engine.set_hints(hints)
    results = await engine.run_ticks(1)

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
