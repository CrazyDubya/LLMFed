from core_engine.prompt_builder import PromptBuilder
from models.entities import EventContext, PossibleAction

def test_build_prompt_includes_context_and_hints():
    context = EventContext(
        event_id="evt1",
        event_type="TestEvent",
        description="Testing",
        requesting_agent_id="agent1"
    )
    hints = {"tip": "increase drama"}
    payload = PromptBuilder.build_prompt(context, hints)

    assert payload["event_id"] == "evt1"
    assert payload["event_type"] == "TestEvent"
    assert payload["description"] == "Testing"
    assert payload["requesting_agent_id"] == "agent1"
    assert payload["hints"] == hints
    assert payload.get("state") == {}
    assert payload.get("available_actions") == []
    # Check response_schema present and valid JSON schema
    schema = payload.get("response_schema")
    assert isinstance(schema, dict)
    assert "properties" in schema
