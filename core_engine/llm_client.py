import logging
import json
import os
import httpx
from core_engine.dispatcher import LLMDispatcher

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

# Default model for LLM calls (override via OPENAI_MODEL env var)
# MODEL_NAME will serve as fallback if env var missing
MODEL_NAME = os.getenv("OPENAI_MODEL", "long-gemma:latest")

class LLMClient:
    """Client wrapper for OpenAI calls with fallback stub mode."""
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        if OPENAI_AVAILABLE and self.api_key:
            openai.api_key = self.api_key
        else:
            logging.warning("OpenAI API key missing or openai package not installed; using stub mode.")
        # Override API base for local proxies (e.g., Ollama)
        base = os.getenv("OPENAI_API_BASE", "")
        self.api_base = base
        if base:
            logging.info(f"Using API base: {base}")
        # If using local proxy, allow calls without API key
        self.force_remote = False
        if base and ("127.0.0.1" in base or "localhost" in base):
            self.force_remote = True
            # Set dummy API key so openai library allows requests through local proxy
            openai.api_key = "local_proxy_dummy"
            self.api_key = "local_proxy_dummy"
        # Dynamically pick up model name at init
        self.model_name = os.getenv("OPENAI_MODEL", MODEL_NAME)

    def send_prompt(self, prompt: dict) -> dict:
        """
        Send the prompt to the LLM and return a dict with action_id, description, meta.
        If OpenAI is unavailable or no key, returns a stub action.
        """
        # If using local proxy, send directly via HTTPX to avoid API key enforcement
        if self.force_remote:
            base_url = self.api_base or ''
            url = base_url.rstrip('/') + '/chat/completions'
            payload = {
                'model': self.model_name,
                'messages': [{'role': 'user', 'content': json.dumps(prompt)}],
                'stream': False,
            }
            try:
                resp = httpx.post(url, json=payload, timeout=30)
            except Exception as e:
                logging.error(f"Connection error to local proxy ({url}): {e}")
                return {"action_id": "noop", "description": "Stub action", "meta": {}}
            try:
                resp.raise_for_status()
            except httpx.HTTPError as e:
                logging.error(f"HTTP error from local proxy ({url}): {e}")
                return {"action_id": "noop", "description": "Stub action", "meta": {}}
            # parse JSON response
            try:
                data = resp.json()
                content = data['choices'][0]['message']['content']
                return json.loads(content)
            except Exception:
                # likely empty or non-JSON response
                logging.debug(f"Local proxy returned non-JSON or empty body: '{resp.text}'")
                return {"action_id": "noop", "description": "Stub action", "meta": {}}

        # Use OpenAI library when not using local proxy
        if OPENAI_AVAILABLE and (self.api_key):
            try:
                # Use new OpenAI v1 interface for chat completions
                response = openai.chat.completions.create(
                    model=self.model_name,
                    messages=[{"role": "user", "content": json.dumps(prompt)}]
                )
                content = response.choices[0].message.content
                return json.loads(content)
            except Exception as e:
                err_text = str(e)
                fallback_model = "gpt-4"
                # retry if custom model not found
                if "model_not_found" in err_text and self.model_name != fallback_model:
                    logging.warning(f"Model {self.model_name} not found, retrying with {fallback_model}")
                    try:
                        response = openai.chat.completions.create(
                            model=fallback_model,
                            messages=[{"role": "user", "content": json.dumps(prompt)}]
                        )
                        content = response.choices[0].message.content
                        return json.loads(content)
                    except Exception as e2:
                        logging.error(f"Fallback model error: {e2}")
                logging.error(f"LLM API error: {e}")
        # Fallback to dispatcher stub on any unhandled error (e.g., OpenAI API failures)
        dispatcher = LLMDispatcher()
        fallback = dispatcher.choose_action()
        return {"action_id": fallback.action_id, "description": fallback.description, "meta": fallback.meta}
