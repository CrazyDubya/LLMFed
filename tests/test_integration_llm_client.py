import os
import json
import threading
import socketserver
from http.server import BaseHTTPRequestHandler, HTTPServer
import pytest
from core_engine.llm_client import LLMClient


def make_handler(response_body, status=200):
    class MockHandler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.dumps(response_body).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        
        def log_message(self, format, *args):
            # Suppress server logging
            return
    return MockHandler


@pytest.fixture(scope='module')
def mock_ollama_server():
    # Prepare a valid LLM response wrapper
    body = {"choices": [{"message": {"content": json.dumps({"action_id": "mockfoo", "description": "mockbar", "meta": {}})}}]}
    Handler = make_handler(body)
    server = HTTPServer(('localhost', 0), Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    api_base = f"http://localhost:{port}/v1"
    yield api_base
    server.shutdown()
    thread.join()


def test_send_prompt_success_integration(mock_ollama_server, monkeypatch):
    # Point client to mock server
    os.environ['OPENAI_API_BASE'] = mock_ollama_server
    client = LLMClient()
    client.force_remote = True
    prompt = {"foo": "bar"}
    result = client.send_prompt(prompt)
    assert result['action_id'] == 'mockfoo'
    assert result['description'] == 'mockbar'
    assert result['meta'] == {}


def test_send_prompt_http_error_integration(mock_ollama_server, monkeypatch):
    # Handler returns HTTP error status
    # Override handler to error
    error_body = {"error": "server error"}
    Handler = make_handler(error_body, status=500)
    server = HTTPServer(('localhost', 0), Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    os.environ['OPENAI_API_BASE'] = f"http://localhost:{port}/v1"
    client = LLMClient()
    client.force_remote = True
    # Expect stub noop
    result = client.send_prompt({})
    assert result['action_id'] == 'noop'
    server.shutdown()
    thread.join()


def test_send_prompt_non_json_integration(mock_ollama_server):
    # Handler returns non-JSON body
    class BadHandler(BaseHTTPRequestHandler):
        def do_POST(self):
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain')
            self.send_header('Content-Length', '10')
            self.end_headers()
            self.wfile.write(b"not a json")
        def log_message(self, format, *args): return
    server = HTTPServer(('localhost', 0), BadHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    os.environ['OPENAI_API_BASE'] = f"http://localhost:{port}/v1"
    client = LLMClient()
    client.force_remote = True
    result = client.send_prompt({})
    assert result['action_id'] == 'noop'
    server.shutdown()
    thread.join()
