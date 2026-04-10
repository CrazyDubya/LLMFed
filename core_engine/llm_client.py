"""LLM client — delegates to the unified llm_abstraction layer.

Maintains the same public interface (send_prompt(dict) -> dict) so that
core_engine.engine and api_gateway.main continue to work unchanged.
Internally all calls route through llm_abstraction.provider for consistent
retry, circuit-breaking, and cost tracking.
"""

import logging
import json
import os

from core_engine.dispatcher import LLMDispatcher
from llm_abstraction.provider import LLMMessage, get_llm

logger = logging.getLogger(__name__)

_NOOP = {"action_id": "noop", "description": "Stub action", "meta": {}}


class LLMClient:
    """Thin shim over the unified LLM abstraction.

    The engine calls ``send_prompt(dict) -> dict``. This class serialises
    the dict to JSON, sends it as a user message through the unified
    provider, and parses the JSON response back into a dict.
    """

    def __init__(self) -> None:
        self._llm = None  # lazy — avoids import-time side effects
        self._dispatcher = LLMDispatcher()

    def _get_llm(self):
        """Lazy-initialise the LLM abstraction."""
        if self._llm is not None:
            return self._llm
        try:
            self._llm = get_llm()
            return self._llm
        except Exception as e:
            logger.warning("LLM abstraction unavailable: %s", e)
            return None

    def send_prompt(self, prompt: dict) -> dict:
        """Route to the unified LLM provider and return an action dict.

        Always returns a dict with at least action_id, description, meta.
        """
        if not isinstance(prompt, dict) or not prompt:
            logger.error("send_prompt called with empty or non-dict prompt")
            return dict(_NOOP)

        llm = self._get_llm()
        if llm is None:
            return self._fallback_stub()

        try:
            response = llm.generate_with_messages(
                messages=[LLMMessage(role="user", content=json.dumps(prompt))],
                temperature=0.7,
            )
            return self._parse_response(response.content)
        except Exception as e:
            logger.error("LLM call failed: %s", e)
            return self._fallback_stub()

    def _parse_response(self, content: str) -> dict:
        """Parse the LLM text response into a structured action dict."""
        try:
            parsed = json.loads(content)
            if isinstance(parsed, dict):
                return parsed
        except (json.JSONDecodeError, TypeError) as e:
            logger.debug("LLM returned non-JSON content: %s", e)
        return dict(_NOOP)

    def _fallback_stub(self) -> dict:
        """Return a random stub action from the dispatcher."""
        fallback = self._dispatcher.choose_action()
        return {
            "action_id": fallback.action_id,
            "description": fallback.description,
            "meta": fallback.meta,
        }
