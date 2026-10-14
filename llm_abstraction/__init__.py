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
    StreamChunk,
    TokenBudget,
    estimate_cost,
    get_llm,
    reset_llm,
    # Error taxonomy
    LLMError,
    LLMTransientError,
    LLMPermanentError,
    BudgetExceededError,
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
    # Streaming
    "StreamChunk",
    # Errors
    "LLMError",
    "LLMTransientError",
    "LLMPermanentError",
    "BudgetExceededError",
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
