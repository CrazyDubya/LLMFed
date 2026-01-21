"""
LLM Abstraction Layer

Provides a unified interface for different LLM providers with automatic fallback.
"""

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
    "LLMAbstraction",
    "LLMMessage",
    "LLMResponse",
    "LLMProviderBase",
    "OpenAIProvider",
    "OllamaProvider",
    "get_llm"
]

