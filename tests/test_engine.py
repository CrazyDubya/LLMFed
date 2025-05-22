import pytest

from core_engine.engine import engine_instance, AppliedAction
from core_engine.dispatcher import StubAction


def test_set_hints_stores_hints():
    hints = {"foo": "bar"}
    engine_instance.set_hints(hints)
    assert engine_instance.promoter_hints == hints


def test_run_ticks_returns_results_and_uses_hints(monkeypatch):
    # Prepare fake LLM response
    fake_response = {"action_id": "x", "description": "fake", "meta": {}}
    monkeypatch.setattr(engine_instance.llm_client, 'send_prompt', lambda prompt: fake_response)

    # Set hints and run
    hints = {"tip": "increase drama"}
    engine_instance.set_hints(hints)
    results = engine_instance.run_ticks(1)

    # Validate results
    assert isinstance(results, list) 
    # Expect one TickResult per role
    expected = len(engine_instance.role_order)
    assert len(results) == expected
    for result in results:
        assert hasattr(result, 'tick_id')
        assert hasattr(result, 'time_index')
        assert hasattr(result, 'applied_actions')
        # Check that applied action is correct type and fields
        action = result.applied_actions[0]
        assert isinstance(action, AppliedAction)
        assert action.action_id == "x"
        assert action.description == "fake"
