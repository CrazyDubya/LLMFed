import json
from unittest.mock import patch, MagicMock

from core_engine.llm_client import LLMClient
from llm_abstraction.provider import LLMResponse


class DummyLLM:
    """Fake LLMAbstraction that returns controlled responses."""

    def __init__(self, content: str):
        self._content = content

    def generate_with_messages(self, messages, temperature=0.7, **kwargs):
        return LLMResponse(content=self._content, model="test-model")


def test_send_prompt_success():
    sample = {
        "event_id": "e1",
        "chosen_action_id": "punch",
        "commentary": "Hit!",
        "target_agent_id": None,
        "confidence_score": 0.8,
    }
    client = LLMClient()
    client._llm = DummyLLM(json.dumps(sample))
    result = client.send_prompt({"role": "test"})
    assert result == sample


def test_send_prompt_non_json():
    client = LLMClient()
    client._llm = DummyLLM("not valid json")
    result = client.send_prompt({"role": "test"})
    # Falls back to noop on parse failure
    assert result["action_id"] == "noop"
    assert result["description"] == "Stub action"


def test_send_prompt_empty_prompt():
    client = LLMClient()
    result = client.send_prompt({})
    assert result["action_id"] == "noop"
    assert result["description"] == "Stub action"


def test_send_prompt_non_dict():
    client = LLMClient()
    result = client.send_prompt("not a dict")
    assert result["action_id"] == "noop"


def test_send_prompt_llm_exception():
    """When the LLM raises, the client returns a stub action."""
    mock_llm = MagicMock()
    mock_llm.generate_with_messages.side_effect = Exception("API Error")
    client = LLMClient()
    client._llm = mock_llm
    result = client.send_prompt({"role": "test"})
    # Should fall back to stub (random action from dispatcher)
    assert "action_id" in result
    assert "description" in result


def test_send_prompt_llm_unavailable():
    """When no provider can be initialized, falls back to stub."""
    client = LLMClient()
    # Force _llm to None (no provider available)
    client._llm = None
    with patch(
        "core_engine.llm_client.get_llm", side_effect=RuntimeError("No provider")
    ):
        result = client.send_prompt({"role": "test"})
    assert "action_id" in result
    assert "description" in result
