import json
import logging
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List, Optional
import httpx
from core_engine.dispatcher import LLMDispatcher

logger = logging.getLogger(__name__)

# Re-use custom exceptions
from core_engine.exceptions import (
    LLMError,
    LLMNetworkError,
)


@dataclass
class LLMMessage:
    role: str
    content: str


@dataclass
class StreamChunk:
    text: str
    is_final: bool = False
    usage: Optional[Dict[str, int]] = None


@dataclass
class LLMResponse:
    content: str
    provider: str
    model: str
    usage: Optional[Dict[str, int]] = None
    raw_response: Any = None
    cost_usd: float = 0.0
    latency_ms: float = 0.0


class LLMPermanentError(LLMError):
    pass


class LLMTransientError(LLMError):
    pass


class BudgetExceededError(LLMError):
    pass


def estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    # simple estimate
    rates = {
        "gpt-4": (0.03 / 1000, 0.06 / 1000),
        "gpt-3.5-turbo": (0.0015 / 1000, 0.002 / 1000),
        "long-gemma": (0.0, 0.0),
    }
    rate_p, rate_c = rates.get(model, (0.001 / 1000, 0.002 / 1000))
    return (prompt_tokens * rate_p) + (completion_tokens * rate_c)


class LLMProviderBase(ABC):
    def __init__(self, model: str, **kwargs):
        self.model = model
        self.config = kwargs
        self.client = httpx.AsyncClient()

    @abstractmethod
    def validate_config(self) -> bool:
        pass

    @abstractmethod
    async def generate_async(self, messages: List[LLMMessage], **kwargs) -> LLMResponse:
        pass

    # We maintain synchronous generate just for testing/fallback if really needed, but it shouldn't be used
    def generate(self, messages: List[LLMMessage], **kwargs) -> LLMResponse:
        import asyncio

        return asyncio.run(self.generate_async(messages, **kwargs))

    def generate_stream(
        self, messages: List[LLMMessage], **kwargs
    ) -> Iterator[StreamChunk]:
        raise NotImplementedError()


class OpenAIProvider(LLMProviderBase):
    def validate_config(self) -> bool:
        return bool(os.getenv("OPENAI_API_KEY"))

    async def generate_async(self, messages: List[LLMMessage], **kwargs) -> LLMResponse:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise LLMPermanentError("OPENAI_API_KEY not set")

        t0 = time.monotonic()
        payload = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": kwargs.get("temperature", 0.7),
        }
        if kwargs.get("max_tokens"):
            payload["max_tokens"] = kwargs.get("max_tokens")

        try:
            response = await self.client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json=payload,
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            return LLMResponse(
                content=content,
                provider="openai",
                model=self.model,
                usage=usage,
                cost_usd=estimate_cost(
                    self.model,
                    usage.get("prompt_tokens", 0),
                    usage.get("completion_tokens", 0),
                ),
                latency_ms=(time.monotonic() - t0) * 1000,
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (401, 403):
                raise LLMPermanentError(f"OpenAI Auth Error: {e}")
            raise LLMTransientError(f"OpenAI Error: {e}")
        except Exception as e:
            raise LLMNetworkError(f"OpenAI network error: {e}")


class OllamaProvider(LLMProviderBase):
    def validate_config(self) -> bool:
        return True

    async def generate_async(self, messages: List[LLMMessage], **kwargs) -> LLMResponse:
        base_url = os.getenv("OPENAI_API_BASE", "http://127.0.0.1:11434/v1")
        # Ensure it points to the chat completions endpoint if standard ollama
        url = (
            base_url
            if base_url.endswith("/chat/completions")
            else f"{base_url}/chat/completions"
        )
        if "11434/v1" in base_url and not base_url.endswith("/chat/completions"):
            url = "http://127.0.0.1:11434/v1/chat/completions"

        t0 = time.monotonic()
        payload = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": kwargs.get("temperature", 0.7),
        }
        try:
            response = await self.client.post(url, json=payload, timeout=30.0)
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            return LLMResponse(
                content=content,
                provider="ollama",
                model=self.model,
                usage=usage,
                cost_usd=0.0,
                latency_ms=(time.monotonic() - t0) * 1000,
            )
        except httpx.HTTPStatusError as e:
            raise LLMTransientError(f"Ollama HTTP Error: {e}")
        except Exception as e:
            raise LLMNetworkError(f"Ollama network error: {e}")


_PROVIDER_REGISTRY: Dict[str, type] = {
    "openai": OpenAIProvider,
    "ollama": OllamaProvider,
}


@dataclass
class TokenBudget:
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_cost_usd: float = 0.0
    request_count: int = 0
    lifetime_prompt_tokens: int = 0
    lifetime_completion_tokens: int = 0
    lifetime_cost_usd: float = 0.0
    lifetime_request_count: int = 0
    soft_limit_usd: float = 0.0
    hard_limit_usd: float = 0.0
    _soft_warned: bool = field(default=False, repr=False)

    def __post_init__(self):
        if self.soft_limit_usd == 0:
            self.soft_limit_usd = float(os.getenv("LLMFED_BUDGET_SOFT_USD", "0"))
        if self.hard_limit_usd == 0:
            self.hard_limit_usd = float(os.getenv("LLMFED_BUDGET_HARD_USD", "0"))

    def check_budget(self) -> None:
        if self.hard_limit_usd > 0 and self.lifetime_cost_usd >= self.hard_limit_usd:
            raise BudgetExceededError("LLM budget hard limit reached")
        if (
            self.soft_limit_usd > 0
            and self.lifetime_cost_usd >= self.soft_limit_usd
            and not self._soft_warned
        ):
            self._soft_warned = True

    def record(self, response: LLMResponse) -> None:
        self.request_count += 1
        self.lifetime_request_count += 1
        self.total_cost_usd += response.cost_usd
        self.lifetime_cost_usd += response.cost_usd
        if response.usage:
            prompt = response.usage.get("prompt_tokens", 0)
            completion = response.usage.get("completion_tokens", 0)
            self.total_prompt_tokens += prompt
            self.total_completion_tokens += completion
            self.lifetime_prompt_tokens += prompt
            self.lifetime_completion_tokens += completion


class LLMAbstraction:
    """
    Main LLM abstraction interface, now fully async and handling JSON parsing and fallbacks directly.
    Replaces core_engine/llm_client.py
    """

    def __init__(
        self,
        provider: str = "auto",
        model: Optional[str] = None,
        fallback_providers: Optional[List[str]] = None,
        **kwargs,
    ):
        self.provider_name = provider
        self.model = model or os.getenv("OPENAI_MODEL", "long-gemma")
        self.fallback_providers = fallback_providers or ["ollama", "openai"]
        self.config = kwargs
        self.budget = TokenBudget()
        self.provider = self._initialize_provider()
        self._dispatcher = LLMDispatcher()

    def _initialize_provider(self) -> LLMProviderBase:
        if self.provider_name == "auto":
            for provider_name in self.fallback_providers:
                try:
                    provider = self._create_provider(provider_name)
                    if provider.validate_config():
                        return provider
                except Exception:
                    pass
            raise RuntimeError("No LLM provider could be initialized")

        provider = self._create_provider(self.provider_name)
        if not provider.validate_config():
            raise RuntimeError(f"Provider {self.provider_name} configuration invalid")
        return provider

    def _create_provider(self, provider_name: str) -> LLMProviderBase:
        cls = _PROVIDER_REGISTRY.get(provider_name)
        if cls is None:
            raise ValueError(f"Unknown provider: {provider_name}")
        return cls(self.model, **self.config)

    async def generate_action_async(self, prompt: dict) -> dict:
        """
        Takes a structured dictionary prompt, sends it to the LLM, and parses the JSON response.
        Handles fallbacks for transient errors.
        """
        if not isinstance(prompt, dict) or not prompt:
            logger.error("generate_action_async called with empty or non-dict prompt")
            return self._fallback_stub()

        self.budget.check_budget()
        messages = [LLMMessage(role="user", content=json.dumps(prompt))]

        try:
            response = await self.provider.generate_async(
                messages=messages,
                temperature=0.7,
            )
            self.budget.record(response)
            return self._parse_response(response.content)
        except LLMPermanentError:
            raise
        except Exception as e:
            logger.warning(f"LLM call failed (transient), using fallback: {e}")
            return self._fallback_stub()

    def _parse_response(self, content: str) -> dict:
        try:
            parsed = json.loads(content)
            if isinstance(parsed, dict):
                return parsed
        except (json.JSONDecodeError, TypeError) as e:
            logger.debug(f"LLM returned non-JSON content: {e}")
        return self._fallback_stub()

    def _fallback_stub(self) -> dict:
        fallback = self._dispatcher.choose_action()
        return {
            "action_id": fallback.action_id,
            "description": fallback.description,
            "meta": fallback.meta,
        }


# Keeping these for backwards compatibility until everything is refactored, but they should be avoided
# in favor of Dependency Injection
import threading

_default_llm: Optional[LLMAbstraction] = None
_default_llm_lock = threading.Lock()


def get_llm() -> LLMAbstraction:
    global _default_llm
    if _default_llm is None:
        with _default_llm_lock:
            if _default_llm is None:
                _default_llm = LLMAbstraction(provider="auto")
    return _default_llm


def reset_llm() -> None:
    global _default_llm
    with _default_llm_lock:
        _default_llm = None
