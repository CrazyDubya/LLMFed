"""
Async wrappers for LLM providers.

Provides async generate/stream methods that run the synchronous provider
calls in a thread executor, plus asyncio.gather-based batch generation.
"""

import asyncio
import logging
from typing import List, Optional, Any, Dict

from llm_abstraction.provider import (
    LLMAbstraction,
    LLMMessage,
    LLMResponse,
)
from llm_abstraction.cache import LLMResponseCache

logger = logging.getLogger(__name__)


class AsyncLLM:
    """Async wrapper around LLMAbstraction with caching and batch support.

    Usage::

        allm = AsyncLLM()  # or AsyncLLM(llm=my_abstraction)
        response = await allm.generate("Hello")
        responses = await allm.generate_batch(["Q1", "Q2", "Q3"])
    """

    def __init__(
        self,
        llm: Optional[LLMAbstraction] = None,
        cache_max_size: int = 256,
        cache_ttl: float = 300.0,
        enable_cache: bool = True,
    ):
        if llm is None:
            from llm_abstraction.provider import get_llm
            llm = get_llm()
        self._llm = llm
        self._cache = LLMResponseCache(max_size=cache_max_size, ttl_seconds=cache_ttl) if enable_cache else None

    async def generate(
        self,
        prompt: str,
        system_message: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        use_cache: bool = True,
        **kwargs,
    ) -> LLMResponse:
        """Async generate — runs the sync provider in a thread executor."""
        messages_dicts = []
        if system_message:
            messages_dicts.append({"role": "system", "content": system_message})
        messages_dicts.append({"role": "user", "content": prompt})

        # Check cache
        if use_cache and self._cache is not None:
            cached = self._cache.get(
                self._llm.model, messages_dicts, temperature, max_tokens
            )
            if cached is not None:
                cached.cached = True
                return cached

        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self._llm.generate(
                prompt=prompt,
                system_message=system_message,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            ),
        )

        # Store in cache
        if use_cache and self._cache is not None:
            self._cache.put(
                self._llm.model, messages_dicts, temperature, max_tokens, response
            )

        return response

    async def generate_with_messages(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        use_cache: bool = True,
        **kwargs,
    ) -> LLMResponse:
        """Async generate with full message history."""
        messages_dicts = [{"role": m.role, "content": m.content} for m in messages]

        if use_cache and self._cache is not None:
            cached = self._cache.get(
                self._llm.model, messages_dicts, temperature, max_tokens
            )
            if cached is not None:
                cached.cached = True
                return cached

        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self._llm.generate_with_messages(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            ),
        )

        if use_cache and self._cache is not None:
            self._cache.put(
                self._llm.model, messages_dicts, temperature, max_tokens, response
            )

        return response

    async def generate_batch(
        self,
        prompts: List[str],
        system_message: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        max_concurrent: int = 5,
        **kwargs,
    ) -> List[LLMResponse]:
        """Generate responses for multiple prompts concurrently.

        Uses a semaphore to cap concurrency at *max_concurrent*.
        """
        semaphore = asyncio.Semaphore(max_concurrent)

        async def _bounded_generate(prompt: str) -> LLMResponse:
            async with semaphore:
                return await self.generate(
                    prompt=prompt,
                    system_message=system_message,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs,
                )

        return await asyncio.gather(*[_bounded_generate(p) for p in prompts])

    def cache_stats(self) -> Dict[str, Any]:
        """Return cache statistics."""
        if self._cache is None:
            return {"enabled": False}
        stats = self._cache.stats()
        stats["enabled"] = True
        return stats

    def clear_cache(self) -> None:
        """Clear the response cache."""
        if self._cache is not None:
            self._cache.clear()

    def get_budget_summary(self) -> Dict[str, Any]:
        """Proxy to the underlying LLM's budget tracker."""
        return self._llm.get_budget_summary()
