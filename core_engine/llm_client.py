"""LLM client: re-exports UnifiedLLMClient for backward compatibility.

Engine now uses llm_abstraction.unified.get_unified_llm() directly.
This module remains for scripts/tests that import LLMClient from core_engine.llm_client.
"""

from llm_abstraction.unified import UnifiedLLMClient, get_unified_llm

LLMClient = UnifiedLLMClient  # Backward compat

__all__ = ["LLMClient", "UnifiedLLMClient", "get_unified_llm"]
