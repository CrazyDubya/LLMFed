"""
LRU response cache for LLM calls.

Caches responses keyed on a hash of (model, messages, temperature, max_tokens).
Configurable max_size and TTL. Thread-safe via a simple lock.
"""

import hashlib
import json
import threading
import time
import logging
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """A cached LLM response with metadata."""

    response: Any  # LLMResponse
    created_at: float = field(default_factory=time.monotonic)
    hit_count: int = 0


class LLMResponseCache:
    """Thread-safe LRU cache for LLM responses with TTL expiry."""

    def __init__(self, max_size: int = 256, ttl_seconds: float = 300.0):
        self._max_size = max_size
        self._ttl = ttl_seconds
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0

    @staticmethod
    def _make_key(
        model: str,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: Optional[int],
    ) -> str:
        """Create a deterministic cache key from request parameters."""
        raw = json.dumps(
            {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
            sort_keys=True,
        )
        return hashlib.sha256(raw.encode()).hexdigest()

    def get(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: Optional[int],
    ) -> Optional[Any]:
        """Look up a cached response. Returns None on miss or expired entry."""
        key = self._make_key(model, messages, temperature, max_tokens)
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                self._misses += 1
                return None
            # Check TTL
            if time.monotonic() - entry.created_at > self._ttl:
                del self._cache[key]
                self._misses += 1
                return None
            # Move to end (most recently used)
            self._cache.move_to_end(key)
            entry.hit_count += 1
            self._hits += 1
            return entry.response

    def put(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: Optional[int],
        response: Any,
    ) -> None:
        """Store a response in the cache, evicting oldest if at capacity."""
        key = self._make_key(model, messages, temperature, max_tokens)
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                self._cache[key] = CacheEntry(response=response)
            else:
                if len(self._cache) >= self._max_size:
                    self._cache.popitem(last=False)  # evict oldest
                self._cache[key] = CacheEntry(response=response)

    def clear(self) -> None:
        """Clear the entire cache."""
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0

    def stats(self) -> Dict[str, Any]:
        """Return cache hit/miss statistics."""
        with self._lock:
            total = self._hits + self._misses
            return {
                "size": len(self._cache),
                "max_size": self._max_size,
                "ttl_seconds": self._ttl,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": round(self._hits / total, 3) if total > 0 else 0.0,
            }
