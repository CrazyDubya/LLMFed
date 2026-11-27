"""Permanent (auth/config) errors must not be retried; transient ones still are."""
import asyncio
import pytest

from llm_abstraction import provider as prov


def _auth_error():
    return Exception("Error code: 401 - Incorrect API key provided")


def _transient_error():
    return Exception("Error code: 503 - Service Unavailable")


def _failing(exc, counter):
    def fn():
        counter["n"] += 1
        raise exc
    return fn


def test_sync_retry_skips_permanent_error(monkeypatch):
    monkeypatch.setattr(prov.time, "sleep", lambda s: None)
    calls = {"n": 0}
    with pytest.raises(Exception):
        prov._retry_with_backoff(_failing(_auth_error(), calls), max_retries=2)
    assert calls["n"] == 1


def test_sync_retry_still_retries_transient_error(monkeypatch):
    monkeypatch.setattr(prov.time, "sleep", lambda s: None)
    calls = {"n": 0}
    with pytest.raises(Exception):
        prov._retry_with_backoff(_failing(_transient_error(), calls), max_retries=2)
    assert calls["n"] == 3


def test_async_retry_skips_permanent_and_retries_transient():
    async def run(exc, counter):
        async def fn():
            counter["n"] += 1
            raise exc
        with pytest.raises(Exception):
            await prov._async_retry_with_backoff(fn, max_retries=2, base_delay=0.0)

    a, t = {"n": 0}, {"n": 0}
    asyncio.run(run(_auth_error(), a))
    asyncio.run(run(_transient_error(), t))
    assert a["n"] == 1
    assert t["n"] == 3
