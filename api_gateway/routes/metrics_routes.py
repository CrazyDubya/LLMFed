
"""
Observability routes — metrics, LLM health, and match config.

Endpoints:
    GET /metrics           — system-wide metrics snapshot
    GET /health/llm        — LLM provider health probe
    GET /match-profiles     — list available match simulation profiles
"""

import logging
import time
from typing import Any, Dict

from fastapi import APIRouter

logger = logging.getLogger(__name__)
router = APIRouter(tags=["monitoring"])


# -------------------------------------------------------------------------
# GET /metrics
# -------------------------------------------------------------------------


@router.get("/metrics", summary="System metrics snapshot")
async def get_metrics() -> Dict[str, Any]:
    """Return a snapshot of runtime metrics for monitoring/alerting."""
    metrics: Dict[str, Any] = {"timestamp": time.time()}

    # LLM budget
    try:
        llm = get_llm()
        metrics["llm_budget"] = llm.get_budget_summary()
        metrics["llm_provider"] = llm.provider_name
        metrics["llm_model"] = llm.model
        # Circuit breaker state
        cb = llm.provider.circuit
        metrics["llm_circuit_breaker"] = {
            "is_open": cb.is_open,
            "failures": cb._failures,
            "threshold": cb.threshold,
        }
    except Exception as e:
        metrics["llm_budget"] = {"error": str(e)}

    # WebSocket connections
    try:
        from api_gateway.websocket_hub import manager

        metrics["websocket"] = manager.stats()
    except Exception:
        metrics["websocket"] = {"error": "unavailable"}

    # LLM cache stats (if async wrapper is in use)
    try:

        # The cache stats are best accessed through AsyncLLM instances,
        # but we expose a basic cache summary if the singleton exists.
        metrics["llm_cache_note"] = (
            "Use AsyncLLM.cache_stats() for per-instance cache metrics"
        )
    except Exception:
        pass

    return metrics


# -------------------------------------------------------------------------
# GET /health/llm
# -------------------------------------------------------------------------


@router.get("/health/llm", summary="LLM provider health probe")
async def llm_health() -> Dict[str, Any]:
    """Probe the active LLM provider and return status + latency.

    Useful for load-balancer health checks and operator dashboards.
    """
    result: Dict[str, Any] = {"status": "unknown", "provider": None}
    try:
        llm = get_llm()
        result["provider"] = llm.provider_name
        result["model"] = llm.model

        cb = llm.provider.circuit
        if cb.is_open:
            result["status"] = "circuit_open"
            result["detail"] = "Circuit breaker is open — provider recently failed"
            return result

        # Quick validation probe (doesn't send a real request)
        is_valid = llm.provider.validate_config()
        if is_valid:
            result["status"] = "healthy"
        else:
            result["status"] = "misconfigured"
            result["detail"] = "Provider config validation failed"
    except Exception as e:
        result["status"] = "unavailable"
        result["detail"] = str(e)

    return result


# -------------------------------------------------------------------------
# GET /match-profiles
# -------------------------------------------------------------------------


@router.get("/match-profiles", summary="List match simulation profiles")
async def list_match_profiles() -> Dict[str, Any]:
    """Return available match simulation profiles and the active one."""
    from core_engine.match_config import list_profiles, get_match_config

    profiles = list_profiles()
    active = get_match_config()
    return {
        "profiles": list(profiles.keys()),
        "profile_details": profiles,
        "active_constants_sample": {
            k: v for i, (k, v) in enumerate(active.as_dict().items()) if i < 10
        },
    }
