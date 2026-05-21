"""
LLM Abstraction Layer

Provides a unified interface for different LLM providers with automatic fallback.
UnifiedLLMClient is the engine's primary LLM interface (OpenAI-compatible).
"""

from .unified import UnifiedLLMClient, get_unified_llm
from .provider import (
    LLMAbstraction,
    LLMMessage,
    LLMResponse,
    LLMProviderBase,
    OpenAIProvider,
    OllamaProvider,
    get_llm
)

__all__ = [
    "UnifiedLLMClient",
    "get_unified_llm",
    "LLMAbstraction",
    "LLMMessage",
    "LLMResponse",
    "LLMProviderBase",
    "OpenAIProvider",
    "OllamaProvider",
    "get_llm"
]

