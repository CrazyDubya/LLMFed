"""Tests for async LLM support."""

import pytest
from unittest.mock import patch

from llm_abstraction.provider import (
    LLMAbstraction,
    LLMResponse,
    LLMMessage,
    OpenAIProvider,
)
from llm_abstraction.async_support import AsyncLLM


def _make_mock_llm():
    """Create an LLMAbstraction with a mocked provider."""
    with patch.object(OpenAIProvider, "validate_config", return_value=True):
        llm = LLMAbstraction(provider="openai", model="test-model", api_key="test")
    return llm


class TestAsyncLLM:
    def test_init_with_llm(self):
        llm = _make_mock_llm()
        allm = AsyncLLM(llm=llm)
        assert allm._llm is llm

    @pytest.mark.asyncio
    async def test_generate(self):
        llm = _make_mock_llm()
        with patch.object(OpenAIProvider, "generate") as mock_gen:
            mock_gen.return_value = LLMResponse(
                content="async response", model="test-model"
            )
            allm = AsyncLLM(llm=llm, enable_cache=False)
            response = await allm.generate("Hello")
            assert response.content == "async response"
            assert mock_gen.called

    @pytest.mark.asyncio
    async def test_generate_uses_cache(self):
        llm = _make_mock_llm()
        call_count = 0

        def _mock_generate(messages, temperature=0.7, max_tokens=None, **kw):
            nonlocal call_count
            call_count += 1
            return LLMResponse(content=f"response_{call_count}", model="test-model")

        with patch.object(OpenAIProvider, "generate", side_effect=_mock_generate):
            allm = AsyncLLM(llm=llm, enable_cache=True, cache_ttl=60.0)
            r1 = await allm.generate("Hello", temperature=0.7)
            r2 = await allm.generate("Hello", temperature=0.7)

            # Second call should be a cache hit
            assert r1.content == "response_1"
            assert r2.content == "response_1"
            assert r2.cached is True
            assert call_count == 1

    @pytest.mark.asyncio
    async def test_generate_batch(self):
        llm = _make_mock_llm()
        with patch.object(OpenAIProvider, "generate") as mock_gen:
            mock_gen.return_value = LLMResponse(
                content="batch response", model="test-model"
            )
            allm = AsyncLLM(llm=llm, enable_cache=False)
            responses = await allm.generate_batch(["Q1", "Q2", "Q3"], max_concurrent=2)
            assert len(responses) == 3
            assert all(r.content == "batch response" for r in responses)

    @pytest.mark.asyncio
    async def test_generate_with_messages(self):
        llm = _make_mock_llm()
        with patch.object(OpenAIProvider, "generate") as mock_gen:
            mock_gen.return_value = LLMResponse(
                content="msg response", model="test-model"
            )
            allm = AsyncLLM(llm=llm, enable_cache=False)
            messages = [
                LLMMessage(role="system", content="Be helpful"),
                LLMMessage(role="user", content="Hi"),
            ]
            response = await allm.generate_with_messages(messages)
            assert response.content == "msg response"

    def test_cache_stats(self):
        llm = _make_mock_llm()
        allm = AsyncLLM(llm=llm, enable_cache=True)
        stats = allm.cache_stats()
        assert stats["enabled"] is True
        assert stats["size"] == 0

    def test_cache_disabled(self):
        llm = _make_mock_llm()
        allm = AsyncLLM(llm=llm, enable_cache=False)
        stats = allm.cache_stats()
        assert stats["enabled"] is False

    def test_clear_cache(self):
        llm = _make_mock_llm()
        allm = AsyncLLM(llm=llm, enable_cache=True)
        allm.clear_cache()  # should not raise

    def test_budget_summary(self):
        llm = _make_mock_llm()
        allm = AsyncLLM(llm=llm)
        summary = allm.get_budget_summary()
        assert "request_count" in summary
        assert summary["request_count"] == 0
