import pytest
from core_engine.engine import engine_instance, AppliedAction


@pytest.mark.asyncio
async def test_run_multiple_ticks(monkeypatch):
    # Stub agent list
    dummy = type('A', (), {'agent_id': 'agent1'})()

    async def fake_get_agents(db):
        return [dummy]

    monkeypatch.setattr('core_engine.engine.get_agents', fake_get_agents)
    # Fake LLM response
    fake = {"action_id": "foo", "description": "bar", "meta": {}}

    async def fake_generate_action_async(prompt):
        return fake

    monkeypatch.setattr(engine_instance.llm_client, 'generate_action_async', fake_generate_action_async)

    # Run 3 ticks
    engine_instance.set_hints({})
    results = await engine_instance.run_ticks(3)
    assert isinstance(results, list) and len(results) == 3
    for tick in results:
        action = tick.applied_actions[0]
        assert isinstance(action, AppliedAction)
        assert action.action_id == "foo"
        assert action.description == "bar"


@pytest.mark.asyncio
async def test_llm_transient_error_fallback(monkeypatch):
    """Transient LLM errors (timeout, rate-limit) fall back to a stub action.

    We monkeypatch the underlying provider's ``generate_async`` so that the
    real ``generate_action_async`` runs its transient-error catch-and-fallback
    logic.
    """
    from llm_abstraction.provider import LLMTransientError

    dummy = type('A', (), {'agent_id': 'agent2'})()

    async def fake_get_agents(db):
        return [dummy]

    monkeypatch.setattr('core_engine.engine.get_agents', fake_get_agents)

    async def raise_transient(messages, **kwargs):
        raise LLMTransientError("LLM timed out")

    monkeypatch.setattr(engine_instance.llm_client.provider, 'generate_async', raise_transient)

    engine_instance.set_hints({})
    results = await engine_instance.run_ticks(1)
    action = results[0].applied_actions[0]
    assert isinstance(action, AppliedAction)
    # Transient error → fallback stub with a random dispatcher action
    assert action.action_id is not None


@pytest.mark.asyncio
async def test_llm_permanent_error_propagates(monkeypatch):
    """Permanent LLM errors (auth, config) propagate to the caller."""
    from llm_abstraction.provider import LLMPermanentError

    dummy = type('A', (), {'agent_id': 'agent3'})()

    async def fake_get_agents(db):
        return [dummy]

    monkeypatch.setattr('core_engine.engine.get_agents', fake_get_agents)

    async def raise_permanent(messages, **kwargs):
        raise LLMPermanentError("Invalid API key")

    monkeypatch.setattr(engine_instance.llm_client.provider, 'generate_async', raise_permanent)

    engine_instance.set_hints({})
    with pytest.raises(LLMPermanentError, match="Invalid API key"):
        await engine_instance.run_ticks(1)
