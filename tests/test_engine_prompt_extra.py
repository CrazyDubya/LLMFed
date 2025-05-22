import pytest
from core_engine.engine import engine_instance
import builtins

def test_engine_prompt_includes_state_and_actions(monkeypatch):
    # Stub agent list
    class DummyAgentDB:
        def __init__(self):
            self.gimmick_description = "Masked Marvel"
            self.current_heat = 42
            self.momentum = 7
            self.agent_id = "agentX"
    dummy_db = DummyAgentDB()
    # Monkeypatch get_agents and get_agent_by_id
    monkeypatch.setattr('core_engine.engine.get_agents', lambda db: [dummy_db])
    monkeypatch.setattr('core_engine.engine.get_agent_by_id', lambda db, aid: dummy_db)

    captured = {}
    def fake_send_prompt(prompt):
        captured.update(prompt)
        return {"action_id": "noop", "description": "Stub", "meta": {}}
    monkeypatch.setattr(engine_instance.llm_client, 'send_prompt', fake_send_prompt)

    # Run one tick
    engine_instance.set_hints({})
    results = engine_instance.run_ticks(1)
    # Ensure prompt had state and available_actions
    assert 'state' in captured
    state = captured['state']
    # The state current_tick should match the TickResult time_index
    assert state['current_tick'] == results[0].time_index
    assert state['gimmick_description'] == "Masked Marvel"
    assert state['heat'] == 42
    assert state['momentum'] == 7
    # available_actions should be a list of dicts
    assert 'available_actions' in captured
    actions = captured['available_actions']
    assert isinstance(actions, list) and len(actions) > 0
    # Each action should have action_id and name keys
    assert 'action_id' in actions[0] and 'name' in actions[0]
    # Match context and scheduler guidance
    assert 'opponent_id' in state
    assert state['opponent_id'] is None  # only one agent
    assert state['stipulation'] == 'StandardMatch'
    assert 'current_spot' in state and state['current_spot'] == {'segment': results[0].time_index}
    assert 'mode' in state and state['mode'] == 'tick'
