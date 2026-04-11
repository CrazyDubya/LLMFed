"""
LLM Abstraction Layer

Provides a unified interface for interacting with different LLM providers
(OpenAI, Ollama, Anthropic, Gemini) with consistent error handling,
retry logic, circuit breaking, streaming, and cost tracking.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Iterator
from dataclasses import dataclass, field
import logging
import os
import time
import hashlib
import json

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Error taxonomy — lets callers distinguish transient from permanent failures
# ---------------------------------------------------------------------------


class LLMError(Exception):
    """Base class for all LLM-related errors."""


class LLMTransientError(LLMError):
    """Transient error — safe to retry (timeout, rate-limit, 5xx)."""


class LLMPermanentError(LLMError):
    """Permanent error — do NOT retry (auth, bad config, invalid request)."""


class LLMCircuitOpenError(LLMTransientError):
    """The circuit breaker is open for this provider."""


def _classify_llm_error(exc: Exception) -> LLMError:
    """Wrap a provider SDK exception into the appropriate LLMError subclass."""
    msg = str(exc)
    exc_type = type(exc).__name__

    def _wrap(err: LLMError) -> LLMError:
        err.__cause__ = exc
        return err

    # Auth / config errors are permanent
    if any(tok in msg.lower() for tok in ("auth", "api key", "api_key", "unauthorized", "forbidden", "invalid_api_key")):
        return _wrap(LLMPermanentError(f"Authentication/config error: {msg}"))
    if any(tok in exc_type.lower() for tok in ("auth", "permission")):
        return _wrap(LLMPermanentError(f"{exc_type}: {msg}"))

    # Rate-limit / timeout / connection errors are transient
    if any(tok in msg.lower() for tok in ("rate", "timeout", "timed out", "connection", "503", "529")):
        return _wrap(LLMTransientError(f"Transient error: {msg}"))
    if isinstance(exc, (ConnectionError, TimeoutError, OSError)):
        return _wrap(LLMTransientError(f"Transient error: {msg}"))

    # Default: treat as transient so the circuit breaker can handle it
    return _wrap(LLMTransientError(f"Unknown LLM error: {msg}"))


# ---------------------------------------------------------------------------
# Cost tables (USD per 1K tokens as of 2025)
# ---------------------------------------------------------------------------
_COST_PER_1K: Dict[str, Dict[str, float]] = {
    # OpenAI
    "gpt-4": {"prompt": 0.03, "completion": 0.06},
    "gpt-4-turbo": {"prompt": 0.01, "completion": 0.03},
    "gpt-4o": {"prompt": 0.005, "completion": 0.015},
    "gpt-4o-mini": {"prompt": 0.00015, "completion": 0.0006},
    "gpt-3.5-turbo": {"prompt": 0.0005, "completion": 0.0015},
    # Anthropic
    "claude-opus-4-20250514": {"prompt": 0.015, "completion": 0.075},
    "claude-sonnet-4-20250514": {"prompt": 0.003, "completion": 0.015},
    "claude-haiku-4-5-20251001": {"prompt": 0.001, "completion": 0.005},
    # Gemini
    "gemini-2.0-flash": {"prompt": 0.0001, "completion": 0.0004},
    "gemini-2.5-pro": {"prompt": 0.00125, "completion": 0.01},
}


def estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Estimate the USD cost of a request based on model and token counts."""
    costs = _COST_PER_1K.get(model)
    if not costs:
        # Try prefix matching for versioned model names
        for key, val in _COST_PER_1K.items():
            if model.startswith(key):
                costs = val
                break
    if not costs:
        return 0.0
    return (prompt_tokens / 1000 * costs["prompt"]) + (
        completion_tokens / 1000 * costs["completion"]
    )


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class LLMMessage:
    """Represents a message in an LLM conversation."""

    role: str  # "system", "user", "assistant"
    content: str


@dataclass
class LLMResponse:
    """Standardized LLM response format."""

    content: str
    model: str
    usage: Optional[Dict[str, int]] = None
    finish_reason: Optional[str] = None
    raw_response: Optional[Any] = None
    cost_usd: float = 0.0
    latency_ms: float = 0.0
    cached: bool = False


@dataclass
class StreamChunk:
    """A single chunk from a streaming LLM response."""

    content: str
    finish_reason: Optional[str] = None
    model: Optional[str] = None


# ---------------------------------------------------------------------------
# Circuit breaker
# ---------------------------------------------------------------------------


class CircuitBreaker:
    """Simple circuit breaker: opens after *threshold* failures in a row,
    re-closes after *cooldown_seconds* elapse."""

    def __init__(self, threshold: int = 3, cooldown_seconds: float = 60.0):
        self.threshold = threshold
        self.cooldown_seconds = cooldown_seconds
        self._failures: int = 0
        self._opened_at: Optional[float] = None

    @property
    def is_open(self) -> bool:
        if self._opened_at is None:
            return False
        if time.monotonic() - self._opened_at >= self.cooldown_seconds:
            # Half-open: allow a probe
            return False
        return True

    def record_success(self) -> None:
        self._failures = 0
        self._opened_at = None

    def record_failure(self, permanent: bool = False) -> None:
        """Record a failure. Only transient failures (permanent=False) count
        toward opening the circuit; permanent errors are config problems that
        retrying won't fix."""
        if permanent:
            return
        self._failures += 1
        if self._failures >= self.threshold:
            self._opened_at = time.monotonic()
            logger.warning(
                "Circuit breaker opened after %d consecutive failures", self._failures
            )


# ---------------------------------------------------------------------------
# Retry helper
# ---------------------------------------------------------------------------


def _retry_with_backoff(
    fn,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    retryable_exceptions: tuple = (Exception,),
):
    """Call *fn* with exponential backoff (sync). Returns the first successful result."""
    last_exc = None
    for attempt in range(max_retries + 1):
        try:
            return fn()
        except retryable_exceptions as e:
            last_exc = e
            if attempt == max_retries:
                break
            delay = min(base_delay * (2**attempt), max_delay)
            logger.warning(
                "Retry %d/%d after %.1fs: %s", attempt + 1, max_retries, delay, e
            )
            time.sleep(delay)
    raise last_exc  # type: ignore[misc]


async def _async_retry_with_backoff(
    fn,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    retryable_exceptions: tuple = (Exception,),
):
    """Call async *fn* with exponential backoff using ``asyncio.sleep``
    so the event loop is never blocked."""
    import asyncio

    last_exc = None
    for attempt in range(max_retries + 1):
        try:
            return await fn()
        except retryable_exceptions as e:
            last_exc = e
            if attempt == max_retries:
                break
            delay = min(base_delay * (2**attempt), max_delay)
            logger.warning(
                "Async retry %d/%d after %.1fs: %s", attempt + 1, max_retries, delay, e
            )
            await asyncio.sleep(delay)
    raise last_exc  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Provider base
# ---------------------------------------------------------------------------


class LLMProviderBase(ABC):
    """Base class for LLM providers."""

    def __init__(self, model: str, **kwargs):
        self.model = model
        self.config = kwargs
        self.circuit = CircuitBreaker(
            threshold=kwargs.get("circuit_threshold", 3),
            cooldown_seconds=kwargs.get("circuit_cooldown", 60.0),
        )
        self.max_retries: int = kwargs.get("max_retries", 2)

    @abstractmethod
    def generate(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> LLMResponse:
        """Generate a completion from the LLM."""
        pass

    def generate_stream(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> Iterator[StreamChunk]:
        """Stream completion tokens. Override in providers that support it."""
        # Default: yield the entire response as one chunk
        resp = self.generate(messages, temperature, max_tokens, **kwargs)
        yield StreamChunk(
            content=resp.content, finish_reason=resp.finish_reason, model=resp.model
        )

    @abstractmethod
    def validate_config(self) -> bool:
        """Validate that the provider is properly configured."""
        pass


# ---------------------------------------------------------------------------
# OpenAI provider
# ---------------------------------------------------------------------------


class OpenAIProvider(LLMProviderBase):
    """OpenAI API provider (also works for any OpenAI-compatible endpoint)."""

    def __init__(self, model: str, api_key: Optional[str] = None, **kwargs):
        super().__init__(model, **kwargs)
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.api_base = kwargs.get("api_base") or os.getenv(
            "OPENAI_API_BASE", "https://api.openai.com/v1"
        )
        self._client = None  # lazily initialised, reused across requests

    def _get_client(self):
        """Return the shared OpenAI client, creating it on first use."""
        if self._client is None:
            import openai
            self._client = openai.OpenAI(api_key=self.api_key, base_url=self.api_base)
        return self._client

    def validate_config(self) -> bool:
        return self.api_key is not None

    def generate(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> LLMResponse:
        if self.circuit.is_open:
            raise LLMCircuitOpenError(f"OpenAI circuit breaker is open for {self.model}")

        t0 = time.monotonic()
        client = self._get_client()

        def _call():
            openai_messages = [
                {"role": msg.role, "content": msg.content} for msg in messages
            ]
            return client.chat.completions.create(
                model=self.model,
                messages=openai_messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )

        try:
            response = _retry_with_backoff(
                _call, max_retries=self.max_retries
            )
            self.circuit.record_success()
        except Exception as exc:
            classified = _classify_llm_error(exc)
            self.circuit.record_failure(permanent=isinstance(classified, LLMPermanentError))
            raise classified from exc

        choice = response.choices[0]
        usage_dict = None
        prompt_tokens = completion_tokens = 0
        if response.usage:
            prompt_tokens = response.usage.prompt_tokens
            completion_tokens = response.usage.completion_tokens
            usage_dict = {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }

        return LLMResponse(
            content=choice.message.content,
            model=response.model,
            usage=usage_dict,
            finish_reason=choice.finish_reason,
            raw_response=response,
            cost_usd=estimate_cost(self.model, prompt_tokens, completion_tokens),
            latency_ms=(time.monotonic() - t0) * 1000,
        )

    def generate_stream(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> Iterator[StreamChunk]:
        if self.circuit.is_open:
            raise LLMCircuitOpenError(f"OpenAI circuit breaker is open for {self.model}")

        client = self._get_client()
        openai_messages = [
            {"role": msg.role, "content": msg.content} for msg in messages
        ]
        try:
            stream = client.chat.completions.create(
                model=self.model,
                messages=openai_messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
            )
            for chunk in stream:
                delta = chunk.choices[0].delta if chunk.choices else None
                if delta and delta.content:
                    yield StreamChunk(
                        content=delta.content,
                        finish_reason=chunk.choices[0].finish_reason,
                        model=chunk.model,
                    )
            # Record success only after the full stream has been consumed
            self.circuit.record_success()
        except Exception as exc:
            classified = _classify_llm_error(exc)
            self.circuit.record_failure(permanent=isinstance(classified, LLMPermanentError))
            raise classified from exc


# ---------------------------------------------------------------------------
# Ollama provider
# ---------------------------------------------------------------------------


class OllamaProvider(LLMProviderBase):
    """Ollama local LLM provider."""

    def __init__(self, model: str, **kwargs):
        super().__init__(model, **kwargs)
        self.api_base = kwargs.get("api_base") or os.getenv(
            "OLLAMA_API_BASE", "http://127.0.0.1:11434"
        )

    def validate_config(self) -> bool:
        try:
            import httpx

            response = httpx.get(f"{self.api_base}/api/tags", timeout=2.0)
            return response.status_code == 200
        except Exception:
            return False

    def generate(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> LLMResponse:
        if self.circuit.is_open:
            raise LLMCircuitOpenError(f"Ollama circuit breaker is open for {self.model}")

        t0 = time.monotonic()

        def _call():
            import httpx

            prompt = "\n".join(f"{msg.role}: {msg.content}" for msg in messages)
            payload: Dict[str, Any] = {
                "model": self.model,
                "prompt": prompt,
                "temperature": temperature,
                "stream": False,
            }
            if max_tokens:
                payload["max_tokens"] = max_tokens

            resp = httpx.post(
                f"{self.api_base}/api/generate", json=payload, timeout=60.0
            )
            resp.raise_for_status()
            return resp.json()

        try:
            data = _retry_with_backoff(_call, max_retries=self.max_retries)
            self.circuit.record_success()
        except Exception as exc:
            classified = _classify_llm_error(exc)
            self.circuit.record_failure(permanent=isinstance(classified, LLMPermanentError))
            raise classified from exc

        return LLMResponse(
            content=data.get("response", ""),
            model=self.model,
            finish_reason="stop",
            raw_response=data,
            latency_ms=(time.monotonic() - t0) * 1000,
        )


# ---------------------------------------------------------------------------
# Anthropic provider
# ---------------------------------------------------------------------------


class AnthropicProvider(LLMProviderBase):
    """Anthropic Claude API provider."""

    def __init__(self, model: str, api_key: Optional[str] = None, **kwargs):
        super().__init__(model, **kwargs)
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self._client = None  # lazily initialised, reused across requests

    def _get_client(self):
        """Return the shared Anthropic client, creating it on first use."""
        if self._client is None:
            import anthropic
            self._client = anthropic.Anthropic(api_key=self.api_key)
        return self._client

    def validate_config(self) -> bool:
        return self.api_key is not None

    def generate(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> LLMResponse:
        if self.circuit.is_open:
            raise LLMCircuitOpenError(
                f"Anthropic circuit breaker is open for {self.model}"
            )

        t0 = time.monotonic()

        def _call():
            client = self._get_client()

            # Separate system message from conversation messages
            system_msg = None
            conv_messages = []
            for msg in messages:
                if msg.role == "system":
                    system_msg = msg.content
                else:
                    conv_messages.append({"role": msg.role, "content": msg.content})

            # Ensure at least one user message
            if not conv_messages:
                conv_messages = [{"role": "user", "content": ""}]

            create_kwargs: Dict[str, Any] = {
                "model": self.model,
                "messages": conv_messages,
                "temperature": temperature,
                "max_tokens": max_tokens or 1024,
            }
            if system_msg:
                create_kwargs["system"] = system_msg

            return client.messages.create(**create_kwargs)

        try:
            response = _retry_with_backoff(
                _call, max_retries=self.max_retries
            )
            self.circuit.record_success()
        except Exception as exc:
            classified = _classify_llm_error(exc)
            self.circuit.record_failure(permanent=isinstance(classified, LLMPermanentError))
            raise classified from exc

        content = ""
        for block in response.content:
            if hasattr(block, "text"):
                content += block.text

        prompt_tokens = getattr(response.usage, "input_tokens", 0)
        completion_tokens = getattr(response.usage, "output_tokens", 0)

        return LLMResponse(
            content=content,
            model=response.model,
            usage={
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
            finish_reason=response.stop_reason,
            raw_response=response,
            cost_usd=estimate_cost(self.model, prompt_tokens, completion_tokens),
            latency_ms=(time.monotonic() - t0) * 1000,
        )

    def generate_stream(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> Iterator[StreamChunk]:
        if self.circuit.is_open:
            raise LLMCircuitOpenError(
                f"Anthropic circuit breaker is open for {self.model}"
            )

        client = self._get_client()

        system_msg = None
        conv_messages = []
        for msg in messages:
            if msg.role == "system":
                system_msg = msg.content
            else:
                conv_messages.append({"role": msg.role, "content": msg.content})
        if not conv_messages:
            conv_messages = [{"role": "user", "content": ""}]

        create_kwargs: Dict[str, Any] = {
            "model": self.model,
            "messages": conv_messages,
            "temperature": temperature,
            "max_tokens": max_tokens or 1024,
        }
        if system_msg:
            create_kwargs["system"] = system_msg

        try:
            with client.messages.stream(**create_kwargs) as stream:
                for text in stream.text_stream:
                    yield StreamChunk(content=text, model=self.model)
            # Record success only after the full stream has been consumed
            self.circuit.record_success()
        except Exception as exc:
            classified = _classify_llm_error(exc)
            self.circuit.record_failure(permanent=isinstance(classified, LLMPermanentError))
            raise classified from exc


# ---------------------------------------------------------------------------
# Google Gemini provider
# ---------------------------------------------------------------------------


class GeminiProvider(LLMProviderBase):
    """Google Gemini API provider."""

    def __init__(self, model: str, api_key: Optional[str] = None, **kwargs):
        super().__init__(model, **kwargs)
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        self._client = None  # lazily initialised, reused across requests

    def _get_client(self):
        """Return the shared Gemini client, creating it on first use."""
        if self._client is None:
            from google import genai
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    def validate_config(self) -> bool:
        return self.api_key is not None

    def generate(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> LLMResponse:
        if self.circuit.is_open:
            raise LLMCircuitOpenError(
                f"Gemini circuit breaker is open for {self.model}"
            )

        t0 = time.monotonic()

        def _call():
            client = self._get_client()

            # Build contents from messages
            system_instruction = None
            contents = []
            for msg in messages:
                if msg.role == "system":
                    system_instruction = msg.content
                else:
                    role = "model" if msg.role == "assistant" else "user"
                    contents.append({"role": role, "parts": [{"text": msg.content}]})

            if not contents:
                contents = [{"role": "user", "parts": [{"text": ""}]}]

            config: Dict[str, Any] = {"temperature": temperature}
            if max_tokens:
                config["max_output_tokens"] = max_tokens

            generate_kwargs: Dict[str, Any] = {
                "model": self.model,
                "contents": contents,
                "config": config,
            }
            if system_instruction:
                generate_kwargs["config"]["system_instruction"] = system_instruction

            return client.models.generate_content(**generate_kwargs)

        try:
            response = _retry_with_backoff(
                _call, max_retries=self.max_retries
            )
            self.circuit.record_success()
        except Exception as exc:
            classified = _classify_llm_error(exc)
            self.circuit.record_failure(permanent=isinstance(classified, LLMPermanentError))
            raise classified from exc

        content = response.text or ""
        usage_meta = getattr(response, "usage_metadata", None)
        prompt_tokens = getattr(usage_meta, "prompt_token_count", 0) if usage_meta else 0
        completion_tokens = (
            getattr(usage_meta, "candidates_token_count", 0) if usage_meta else 0
        )

        return LLMResponse(
            content=content,
            model=self.model,
            usage={
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            }
            if usage_meta
            else None,
            finish_reason="stop",
            raw_response=response,
            cost_usd=estimate_cost(self.model, prompt_tokens, completion_tokens),
            latency_ms=(time.monotonic() - t0) * 1000,
        )


# ---------------------------------------------------------------------------
# Provider registry
# ---------------------------------------------------------------------------

_PROVIDER_REGISTRY: Dict[str, type] = {
    "openai": OpenAIProvider,
    "ollama": OllamaProvider,
    "anthropic": AnthropicProvider,
    "gemini": GeminiProvider,
}


# ---------------------------------------------------------------------------
# Token budget tracker
# ---------------------------------------------------------------------------


class BudgetExceededError(LLMError):
    """Raised when the LLM budget hard limit has been reached."""


@dataclass
class TokenBudget:
    """Track cumulative token usage across requests with optional caps.

    Call :meth:`reset` periodically (e.g. at the start of each game day)
    to prevent unbounded accumulation in long-running processes.

    Budget limits (set via env vars or constructor):
        * ``LLMFED_BUDGET_SOFT_USD`` — log a warning, switch to shorter max_tokens
        * ``LLMFED_BUDGET_HARD_USD`` — raise :class:`BudgetExceededError`
    """

    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_cost_usd: float = 0.0
    request_count: int = 0
    # Lifetime counters survive resets — useful for billing/monitoring
    lifetime_prompt_tokens: int = 0
    lifetime_completion_tokens: int = 0
    lifetime_cost_usd: float = 0.0
    lifetime_request_count: int = 0

    # Configurable budget caps (0 = unlimited)
    soft_limit_usd: float = 0.0
    hard_limit_usd: float = 0.0
    _soft_warned: bool = field(default=False, repr=False)

    def __post_init__(self):
        # Allow env-var overrides
        if self.soft_limit_usd == 0:
            self.soft_limit_usd = float(os.getenv("LLMFED_BUDGET_SOFT_USD", "0"))
        if self.hard_limit_usd == 0:
            self.hard_limit_usd = float(os.getenv("LLMFED_BUDGET_HARD_USD", "0"))

    def check_budget(self) -> None:
        """Raise if hard limit exceeded; warn on soft limit."""
        if self.hard_limit_usd > 0 and self.lifetime_cost_usd >= self.hard_limit_usd:
            raise BudgetExceededError(
                f"LLM budget hard limit reached: ${self.lifetime_cost_usd:.4f} >= ${self.hard_limit_usd:.4f}"
            )
        if self.soft_limit_usd > 0 and self.lifetime_cost_usd >= self.soft_limit_usd and not self._soft_warned:
            self._soft_warned = True
            logger.warning(
                "LLM budget soft limit reached: $%.4f >= $%.4f — consider reducing max_tokens",
                self.lifetime_cost_usd, self.soft_limit_usd,
            )

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
        # Drop heavy raw_response to prevent memory growth
        response.raw_response = None

    def reset(self) -> Dict[str, Any]:
        """Reset window counters and return the snapshot before reset."""
        snapshot = self.summary()
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_cost_usd = 0.0
        self.request_count = 0
        self._soft_warned = False
        return snapshot

    @property
    def total_tokens(self) -> int:
        return self.total_prompt_tokens + self.total_completion_tokens

    @property
    def is_over_soft_limit(self) -> bool:
        return self.soft_limit_usd > 0 and self.lifetime_cost_usd >= self.soft_limit_usd

    def summary(self) -> Dict[str, Any]:
        return {
            "request_count": self.request_count,
            "total_prompt_tokens": self.total_prompt_tokens,
            "total_completion_tokens": self.total_completion_tokens,
            "total_tokens": self.total_tokens,
            "total_cost_usd": round(self.total_cost_usd, 6),
            "lifetime_request_count": self.lifetime_request_count,
            "lifetime_cost_usd": round(self.lifetime_cost_usd, 6),
            "soft_limit_usd": self.soft_limit_usd,
            "hard_limit_usd": self.hard_limit_usd,
            "is_over_soft_limit": self.is_over_soft_limit,
        }


# ---------------------------------------------------------------------------
# Main abstraction
# ---------------------------------------------------------------------------


class LLMAbstraction:
    """
    Main LLM abstraction interface.

    Automatically selects and manages LLM providers with fallback support.
    """

    def __init__(
        self,
        provider: str = "auto",
        model: Optional[str] = None,
        fallback_providers: Optional[List[str]] = None,
        **kwargs,
    ):
        self.provider_name = provider
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
        self.fallback_providers = fallback_providers or ["ollama", "openai"]
        self.config = kwargs
        self.budget = TokenBudget()
        self.provider = self._initialize_provider()

    def _initialize_provider(self) -> LLMProviderBase:
        if self.provider_name == "auto":
            for provider_name in self.fallback_providers:
                try:
                    provider = self._create_provider(provider_name)
                    if provider.validate_config():
                        logger.info("Using LLM provider: %s", provider_name)
                        return provider
                except Exception as e:
                    logger.warning("Failed to initialize %s: %s", provider_name, e)

            raise RuntimeError("No LLM provider could be initialized")

        provider = self._create_provider(self.provider_name)
        if not provider.validate_config():
            raise RuntimeError(
                f"Provider {self.provider_name} configuration invalid"
            )
        return provider

    def _create_provider(self, provider_name: str) -> LLMProviderBase:
        cls = _PROVIDER_REGISTRY.get(provider_name)
        if cls is None:
            raise ValueError(
                f"Unknown provider: {provider_name}. "
                f"Available: {list(_PROVIDER_REGISTRY.keys())}"
            )
        return cls(self.model, **self.config)

    def _effective_max_tokens(self, max_tokens: Optional[int]) -> Optional[int]:
        """Reduce max_tokens when over the soft budget limit."""
        if self.budget.is_over_soft_limit and (max_tokens is None or max_tokens > 100):
            return 100  # conserve tokens while still producing useful output
        return max_tokens

    def generate(
        self,
        prompt: str,
        system_message: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> LLMResponse:
        self.budget.check_budget()
        messages = []
        if system_message:
            messages.append(LLMMessage(role="system", content=system_message))
        messages.append(LLMMessage(role="user", content=prompt))

        response = self.provider.generate(
            messages=messages,
            temperature=temperature,
            max_tokens=self._effective_max_tokens(max_tokens),
            **kwargs,
        )
        self.budget.record(response)
        return response

    def generate_with_messages(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> LLMResponse:
        self.budget.check_budget()
        response = self.provider.generate(
            messages=messages,
            temperature=temperature,
            max_tokens=self._effective_max_tokens(max_tokens),
            **kwargs,
        )
        self.budget.record(response)
        return response

    def stream(
        self,
        prompt: str,
        system_message: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> Iterator[StreamChunk]:
        """Stream tokens from the LLM provider."""
        messages = []
        if system_message:
            messages.append(LLMMessage(role="system", content=system_message))
        messages.append(LLMMessage(role="user", content=prompt))
        return self.provider.generate_stream(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )

    def get_budget_summary(self) -> Dict[str, Any]:
        return self.budget.summary()


# ---------------------------------------------------------------------------
# Singleton (thread-safe with double-checked locking)
# ---------------------------------------------------------------------------

import threading

_default_llm: Optional[LLMAbstraction] = None
_default_llm_lock = threading.Lock()


def get_llm() -> LLMAbstraction:
    """Get the default LLM instance (created once, reused).

    Thread-safe: uses double-checked locking to avoid creating
    duplicate instances under concurrent access.
    """
    global _default_llm
    if _default_llm is None:
        with _default_llm_lock:
            if _default_llm is None:
                _default_llm = LLMAbstraction(provider="auto")
    return _default_llm


def reset_llm() -> None:
    """Reset the singleton (useful for testing)."""
    global _default_llm
    with _default_llm_lock:
        _default_llm = None
