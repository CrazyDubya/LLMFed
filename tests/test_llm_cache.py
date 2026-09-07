"""Tests for LLM response cache."""

import time
from llm_abstraction.cache import LLMResponseCache


class TestLLMResponseCache:
    def test_put_and_get(self):
        cache = LLMResponseCache(max_size=10, ttl_seconds=60)
        msgs = [{"role": "user", "content": "hello"}]
        cache.put("gpt-4", msgs, 0.7, None, "response_1")
        result = cache.get("gpt-4", msgs, 0.7, None)
        assert result == "response_1"

    def test_miss_returns_none(self):
        cache = LLMResponseCache(max_size=10, ttl_seconds=60)
        result = cache.get("gpt-4", [{"role": "user", "content": "hi"}], 0.7, None)
        assert result is None

    def test_different_params_different_keys(self):
        cache = LLMResponseCache(max_size=10, ttl_seconds=60)
        msgs = [{"role": "user", "content": "hello"}]
        cache.put("gpt-4", msgs, 0.7, None, "resp_a")
        cache.put("gpt-4", msgs, 0.9, None, "resp_b")
        assert cache.get("gpt-4", msgs, 0.7, None) == "resp_a"
        assert cache.get("gpt-4", msgs, 0.9, None) == "resp_b"

    def test_ttl_expiry(self):
        cache = LLMResponseCache(max_size=10, ttl_seconds=0.01)
        msgs = [{"role": "user", "content": "hello"}]
        cache.put("gpt-4", msgs, 0.7, None, "response")
        time.sleep(0.02)
        assert cache.get("gpt-4", msgs, 0.7, None) is None

    def test_lru_eviction(self):
        cache = LLMResponseCache(max_size=2, ttl_seconds=60)
        cache.put("m", [{"role": "user", "content": "a"}], 0.7, None, "resp_a")
        cache.put("m", [{"role": "user", "content": "b"}], 0.7, None, "resp_b")
        # Cache is full. Adding a third should evict "a" (oldest).
        cache.put("m", [{"role": "user", "content": "c"}], 0.7, None, "resp_c")
        assert cache.get("m", [{"role": "user", "content": "a"}], 0.7, None) is None
        assert cache.get("m", [{"role": "user", "content": "b"}], 0.7, None) == "resp_b"
        assert cache.get("m", [{"role": "user", "content": "c"}], 0.7, None) == "resp_c"

    def test_overwrite_existing_key(self):
        cache = LLMResponseCache(max_size=10, ttl_seconds=60)
        msgs = [{"role": "user", "content": "hello"}]
        cache.put("gpt-4", msgs, 0.7, None, "old")
        cache.put("gpt-4", msgs, 0.7, None, "new")
        assert cache.get("gpt-4", msgs, 0.7, None) == "new"

    def test_clear(self):
        cache = LLMResponseCache(max_size=10, ttl_seconds=60)
        msgs = [{"role": "user", "content": "hello"}]
        cache.put("gpt-4", msgs, 0.7, None, "response")
        cache.clear()
        assert cache.get("gpt-4", msgs, 0.7, None) is None

    def test_stats(self):
        cache = LLMResponseCache(max_size=10, ttl_seconds=60)
        msgs = [{"role": "user", "content": "hello"}]
        cache.put("gpt-4", msgs, 0.7, None, "response")
        cache.get("gpt-4", msgs, 0.7, None)  # hit
        cache.get("gpt-4", [{"role": "user", "content": "miss"}], 0.7, None)  # miss

        stats = cache.stats()
        assert stats["size"] == 1
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["hit_rate"] == 0.5
