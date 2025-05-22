import pytest
from core_engine.engine import engine_instance, AppliedAction

def test_run_multiple_ticks(monkeypatch):
    # Stub agent list
    dummy = type('A', (), {'agent_id': 'agent1'})()
    monkeypatch.setattr('core_engine.engine.get_agents', lambda db: [dummy])
    # Fake LLM response
    fake = {"action_id": "foo", "description": "bar", "meta": {}}
    monkeypatch.setattr(engine_instance.llm_client, 'send_prompt', lambda prompt: fake)

    # Run 3 ticks
    engine_instance.set_hints({})
    results = engine_instance.run_ticks(3)
    assert isinstance(results, list) and len(results) == 3
    for tick in results:
        action = tick.applied_actions[0]
        assert isinstance(action, AppliedAction)
        assert action.action_id == "foo"
        assert action.description == "bar"


def test_llm_exception_fallback(monkeypatch):
    # Stub agent list
    dummy = type('A', (), {'agent_id': 'agent2'})()
    monkeypatch.setattr('core_engine.engine.get_agents', lambda db: [dummy])
    # Simulate LLM error
    def raise_err(prompt):
        raise RuntimeError("LLM down")
    monkeypatch.setattr(engine_instance.llm_client, 'send_prompt', raise_err)

    engine_instance.set_hints({})
    results = engine_instance.run_ticks(1)
    action = results[0].applied_actions[0]
    assert isinstance(action, AppliedAction)
    assert action.action_id == "noop"
    assert action.description == "Stub action"
