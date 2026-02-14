"""LLM client with local-proxy, OpenAI, and stub fallback paths.

Each path is its own method so a reader can trace one at a time (Rule 1).
Every json.loads is guarded (Rule 4). Input is validated at entry (Rule 2).
"""

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

MODEL_NAME = os.getenv("OPENAI_MODEL", "long-gemma:latest")

_NOOP = {"action_id": "noop", "description": "Stub action", "meta": {}}

logger = logging.getLogger(__name__)


class LLMClient:
    """Client wrapper for OpenAI calls with fallback stub mode."""

    def __init__(self) -> None:
        self.api_key = os.getenv("OPENAI_API_KEY")
        if OPENAI_AVAILABLE and self.api_key:
            openai.api_key = self.api_key
        else:
            logger.warning("OpenAI API key missing or openai package not installed; using stub mode.")
        base = os.getenv("OPENAI_API_BASE", "")
        self.api_base = base
        if base:
            logger.info(f"Using API base: {base}")
        self.force_remote = False
        if base and ("127.0.0.1" in base or "localhost" in base):
            self.force_remote = True
            if OPENAI_AVAILABLE:
                openai.api_key = "local_proxy_dummy"
            self.api_key = "local_proxy_dummy"
        self.model_name = os.getenv("OPENAI_MODEL", MODEL_NAME)

    def send_prompt(self, prompt: dict) -> dict:
        """Route to the appropriate backend and return an action dict.

        Always returns a dict with at least action_id, description, meta.
        """
        if not isinstance(prompt, dict) or not prompt:
            logger.error("send_prompt called with empty or non-dict prompt")
            return dict(_NOOP)

        if self.force_remote:
            return self._send_via_local_proxy(prompt)

        if OPENAI_AVAILABLE and self.api_key:
            try:
                return self._send_via_openai(prompt)
            except Exception as e:
                logger.error(f"LLM API error: {e}")

        return self._fallback_stub()

    # ------------------------------------------------------------------
    # Private: one method per code-path
    # ------------------------------------------------------------------

    def _send_via_local_proxy(self, prompt: dict) -> dict:
        """Send to a local Ollama / OpenAI-compatible proxy via HTTPX."""
        url = (self.api_base or "").rstrip("/") + "/chat/completions"
        payload = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": json.dumps(prompt)}],
            "stream": False,
        }
        try:
            resp = httpx.post(url, json=payload, timeout=30)
            resp.raise_for_status()
        except Exception as e:
            logger.error(f"Local proxy error ({url}): {e}")
            return dict(_NOOP)

        try:
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            return json.loads(content)
        except (json.JSONDecodeError, KeyError, IndexError, TypeError) as e:
            logger.debug(f"Local proxy returned unparseable body: {e}")
            return dict(_NOOP)

    def _send_via_openai(self, prompt: dict) -> dict:
        """Send via the openai Python library. Retries once with gpt-4 on model_not_found."""
        fallback_model = "gpt-4"

        try:
            response = openai.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": json.dumps(prompt)}],
            )
            content = response.choices[0].message.content
            return json.loads(content)
        except json.JSONDecodeError:
            logger.error(f"OpenAI returned non-JSON content for model {self.model_name}")
            return dict(_NOOP)
        except Exception as e:
            if "model_not_found" not in str(e) or self.model_name == fallback_model:
                raise
            logger.warning(f"Model {self.model_name} not found, retrying with {fallback_model}")

        # Single retry with fallback model
        response = openai.chat.completions.create(
            model=fallback_model,
            messages=[{"role": "user", "content": json.dumps(prompt)}],
        )
        content = response.choices[0].message.content
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            logger.error(f"OpenAI returned non-JSON content for fallback model {fallback_model}")
            return dict(_NOOP)

    def _fallback_stub(self) -> dict:
        """Return a random stub action from the dispatcher."""
        fallback = LLMDispatcher().choose_action()
        return {"action_id": fallback.action_id, "description": fallback.description, "meta": fallback.meta}
