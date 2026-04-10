"""
LLM Abstraction Layer

Provides a unified interface for different LLM providers with automatic fallback,
retry logic, circuit breaking, streaming, cost tracking, caching, and async support.
"""

from .provider import (
    LLMAbstraction,
    LLMMessage,
    LLMResponse,
    LLMProviderBase,
    OpenAIProvider,
    OllamaProvider,
    AnthropicProvider,
    GeminiProvider,
    StreamChunk,
    CircuitBreaker,
    TokenBudget,
    estimate_cost,
    get_llm,
    reset_llm,
)
from .cache import LLMResponseCache
from .async_support import AsyncLLM

__all__ = [
    # Core
    "LLMAbstraction",
    "LLMMessage",
    "LLMResponse",
    "LLMProviderBase",
    # Providers
    "OpenAIProvider",
    "OllamaProvider",
    "AnthropicProvider",
    "GeminiProvider",
    # Streaming
    "StreamChunk",
    # Reliability
    "CircuitBreaker",
    # Cost/budget
    "TokenBudget",
    "estimate_cost",
    # Caching
    "LLMResponseCache",
    # Async
    "AsyncLLM",
    # Singleton
    "get_llm",
    "reset_llm",
]
