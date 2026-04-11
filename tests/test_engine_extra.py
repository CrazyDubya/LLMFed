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


def test_llm_transient_error_fallback(monkeypatch):
    """Transient LLM errors (timeout, rate-limit) fall back to a stub action.

    We monkeypatch the underlying ``_get_llm`` so that the real
    ``send_prompt`` runs its transient-error catch-and-fallback logic.
    """
    from llm_abstraction.provider import LLMTransientError

    dummy = type('A', (), {'agent_id': 'agent2'})()
    monkeypatch.setattr('core_engine.engine.get_agents', lambda db: [dummy])

    # Make the underlying LLM generate call raise a transient error
    class _BrokenLLM:
        def generate_with_messages(self, **kwargs):
            raise LLMTransientError("LLM timed out")

    monkeypatch.setattr(engine_instance.llm_client, '_llm', _BrokenLLM())

    engine_instance.set_hints({})
    results = engine_instance.run_ticks(1)
    action = results[0].applied_actions[0]
    assert isinstance(action, AppliedAction)
    # Transient error → fallback stub with a random dispatcher action
    assert action.action_id is not None


def test_llm_permanent_error_propagates(monkeypatch):
    """Permanent LLM errors (auth, config) propagate to the caller."""
    from llm_abstraction.provider import LLMPermanentError

    dummy = type('A', (), {'agent_id': 'agent3'})()
    monkeypatch.setattr('core_engine.engine.get_agents', lambda db: [dummy])

    def raise_permanent(prompt):
        raise LLMPermanentError("Invalid API key")
    monkeypatch.setattr(engine_instance.llm_client, 'send_prompt', raise_permanent)

    engine_instance.set_hints({})
    with pytest.raises(LLMPermanentError, match="Invalid API key"):
        engine_instance.run_ticks(1)
