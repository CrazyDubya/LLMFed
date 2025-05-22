import json
import pytest
import httpx

from core_engine.llm_client import LLMClient

class DummyResponse:
    def __init__(self, status_code=200, body=None, text=''):
        self._status_code = status_code
        self._body = body or {}
        self.text = text

    def raise_for_status(self):
        if self._status_code >= 400:
            raise httpx.HTTPStatusError('Error', request=None, response=None)

    def json(self):
        return self._body

@pytest.fixture(autouse=True)
def restore_post(monkeypatch):
    # ensure monkeypatch resets after each test
    yield

def test_send_prompt_success(monkeypatch):
    sample = {"event_id":"e1","chosen_action_id":"punch","commentary":"Hit!","target_agent_id":None,"confidence_score":0.8}
    body = {"choices":[{"message":{"content":json.dumps(sample)}}]}
    
    def mock_post(url, json, timeout):
        return DummyResponse(status_code=200, body=body)

    monkeypatch.setattr(httpx, 'post', mock_post)
    client = LLMClient()
    client.force_remote = True
    result = client.send_prompt({})
    assert result == sample

@pytest.mark.parametrize("status_code", [400, 500])
def test_send_prompt_http_error(monkeypatch, status_code):
    def mock_post(url, json, timeout):
        return DummyResponse(status_code=status_code)

    monkeypatch.setattr(httpx, 'post', mock_post)
    client = LLMClient()
    client.force_remote = True
    result = client.send_prompt({})
    # fallback stub
    assert result['action_id'] == 'noop'
    assert result['description'] == 'Stub action'

def test_send_prompt_non_json(monkeypatch):
    def mock_post(url, json, timeout):
        return DummyResponse(status_code=200, body=None, text='')

    monkeypatch.setattr(httpx, 'post', mock_post)
    client = LLMClient()
    client.force_remote = True
    result = client.send_prompt({})
    # stub on parse failure
    assert result['action_id'] == 'noop'
    assert result['description'] == 'Stub action'
