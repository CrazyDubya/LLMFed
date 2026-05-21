"""
Unified LLM client: single interface for OpenAI, Ollama, and any OpenAI-compatible API.

Consolidates core_engine/llm_client and llm_abstraction/provider into one system.
All providers use OpenAI-compatible /chat/completions for consistency.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, Optional

import httpx

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

logger = logging.getLogger(__name__)

_NOOP = {"action_id": "noop", "description": "Stub action", "meta": {}}
DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "llama3.2:3b")
DEFAULT_BASE = os.getenv("OPENAI_API_BASE", "http://127.0.0.1:11434/v1")
TIMEOUT = int(os.getenv("LLM_TIMEOUT", "120"))


def _is_local_base(base: str) -> bool:
    """True if base URL points to local Ollama/compatible proxy."""
    return bool(base and ("127.0.0.1" in base or "localhost" in base))


class UnifiedLLMClient:
    """
    Single LLM client for engine. Supports OpenAI, Ollama, and OpenAI-compatible APIs.

    - Local base (127.0.0.1/localhost): use httpx POST to {base}/chat/completions
    - Remote OpenAI: use openai SDK if available
    - Fallback: stub action on error
    """

    def __init__(
        self,
        api_base: Optional[str] = None,
        api_key: Optional[str] = None,
        default_model: Optional[str] = None,
        timeout: int = TIMEOUT,
        use_openai_sdk_for_remote: bool = True,
    ) -> None:
        self.api_base = (api_base or os.getenv("OPENAI_API_BASE") or "").rstrip("/")
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self.default_model = default_model or DEFAULT_MODEL
        self.timeout = timeout
        self.use_openai_sdk = use_openai_sdk_for_remote and OPENAI_AVAILABLE
        self._is_local = _is_local_base(self.api_base)
        if self._is_local and self.api_base and not self.api_key:
            self.api_key = "ollama"  # Dummy for local
        # Backward compat with old LLMClient (force_remote, model_name)
        self.force_remote = self._is_local
        self._model_name = self.default_model

    @property
    def model_name(self) -> str:
        return self._model_name

    @model_name.setter
    def model_name(self, value: str) -> None:
        self._model_name = value
        self.default_model = value

    def send_prompt(self, prompt: Dict[str, Any], model: Optional[str] = None) -> Dict[str, Any]:
        """
        Send prompt to LLM and return action dict.

        Expects prompt with keys like preamble, event_id, role, available_actions, etc.
        Returns dict with action_id, description, meta (or _NOOP on error).
        """
        if not isinstance(prompt, dict) or not prompt:
            logger.error("send_prompt called with empty or non-dict prompt")
            return dict(_NOOP)

        effective_model = model or self.default_model

        try:
            use_local = self._is_local or getattr(self, "force_remote", False)
            if use_local and self.api_base:
                return self._send_via_httpx(prompt, effective_model)
            if self.use_openai_sdk and self.api_key and not use_local:
                return self._send_via_openai_sdk(prompt, effective_model)
            if self.api_base:
                return self._send_via_httpx(prompt, effective_model)
        except Exception as e:
            logger.error(f"LLM send_prompt error: {e}")

        return self._fallback_stub()

    def _send_via_httpx(
        self, prompt: Dict[str, Any], model: str
    ) -> Dict[str, Any]:
        """Send via httpx to OpenAI-compatible /chat/completions (Ollama, etc)."""
        url = f"{self.api_base}/chat/completions"
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": json.dumps(prompt)}],
            "stream": False,
            "temperature": 0.7,
        }
        headers = {}
        if self.api_key and self.api_key != "ollama":
            headers["Authorization"] = f"Bearer {self.api_key}"
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(url, json=payload, headers=headers or None)
            resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            logger.warning("LLM returned non-JSON content, using stub")
            return dict(_NOOP)

    def _send_via_openai_sdk(
        self, prompt: Dict[str, Any], model: str
    ) -> Dict[str, Any]:
        """Send via OpenAI Python SDK."""
        client = openai.OpenAI(
            api_key=self.api_key,
            base_url=self.api_base if self._is_local else None,
        )
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": json.dumps(prompt)}],
            temperature=0.7,
        )
        content = response.choices[0].message.content
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            logger.warning("OpenAI returned non-JSON content, using stub")
            return dict(_NOOP)

    def _fallback_stub(self) -> Dict[str, Any]:
        """Return stub action when LLM unavailable."""
        from core_engine.dispatcher import LLMDispatcher
        stub = LLMDispatcher().choose_action()
        return {"action_id": stub.action_id, "description": stub.description, "meta": stub.meta}


# Singleton for engine
_unified_client: Optional[UnifiedLLMClient] = None


def get_unified_llm() -> UnifiedLLMClient:
    """Get or create the unified LLM client singleton."""
    global _unified_client
    if _unified_client is None:
        _unified_client = UnifiedLLMClient()
    return _unified_client
