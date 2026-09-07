"""
LLMFed API Gateway — application factory and middleware setup.

Route handlers live in ``api_gateway/routes/`` and ``api_gateway/game_routes.py``.
This module wires them together with middleware, error handling, and CORS.
"""

import os
import sys
import logging

# Configure local Ollama before any imports to enforce using long-gemma
os.environ.setdefault("OPENAI_MODEL", "long-gemma")
os.environ.setdefault("OPENAI_API_BASE", "http://127.0.0.1:11434/v1")

# Ensure project root is on sys.path for all internal imports
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend
from redis import asyncio as aioredis
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

# Setup OpenTelemetry
provider = TracerProvider()
processor = BatchSpanProcessor(ConsoleSpanExporter())
provider.add_span_processor(processor)
trace.set_tracer_provider(provider)
tracer = trace.get_tracer(__name__)

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from api_gateway.error_handlers import register_error_handlers
from api_gateway.logging_config import setup_logging, logging_middleware
from api_gateway.game_routes import router as game_router
from api_gateway.routes.core_routes import router as core_router
from api_gateway.routes.metrics_routes import router as metrics_router
from api_gateway.websocket_hub import websocket_endpoint, start_reaper

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
log_level = os.getenv("LOG_LEVEL", "INFO")
use_json_logging = os.getenv("JSON_LOGGING", "false").lower() == "true"
setup_logging(log_level=log_level, use_json=use_json_logging)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="LLMFed API",
    description="""
# LLMFed - Federated Learning Management System

An AI-powered wrestling federation simulator featuring autonomous LLM agents.

## Features

* **Multi-Agent AI System**: Six distinct agent roles
* **Tick-Based Simulation**: Discrete time-step processing
* **LLM Integration**: Support for multiple providers
* **Dynamic Storytelling**: Emergent narratives
* **Security**: JWT auth, rate limiting, CORS
* **Monitoring**: Built-in performance tracking

## Authentication

Most endpoints require JWT authentication. Get your token from `/auth/token`.

## Rate Limiting

- Root endpoint: 100 requests/minute
- Agent creation: 10 requests/minute
- Other endpoints: Configurable per endpoint
    """,
    version="0.2.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {"name": "health", "description": "Health check endpoints"},
        {"name": "federations", "description": "Federation management operations"},
        {"name": "agents", "description": "Agent management operations"},
        {"name": "engine", "description": "Simulation engine control"},
        {"name": "monitoring", "description": "Performance monitoring"},
    ],
)

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

ALLOWED_ORIGINS = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:3000,http://localhost:8091",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["*"],
    expose_headers=[
        "X-RateLimit-Limit",
        "X-RateLimit-Remaining",
        "X-RateLimit-Reset",
        "X-Request-ID",
    ],
)

ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS)

app.middleware("http")(logging_middleware)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Add security headers to all responses."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = (
        "max-age=31536000; includeSubDomains"
    )
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    return response


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------
register_error_handlers(app)


# ---------------------------------------------------------------------------
# Startup / shutdown
# ---------------------------------------------------------------------------
@app.on_event("startup")
async def _on_startup():
    start_reaper()

    # Setup Redis Cache
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    try:
        redis = aioredis.from_url(redis_url, encoding="utf8", decode_responses=True)
        FastAPICache.init(RedisBackend(redis), prefix="fastapi-cache")
    except Exception as e:
        logger.warning(f"Failed to connect to redis, caching disabled: {e}")


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(game_router)
app.include_router(core_router)
app.include_router(metrics_router)


# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------
@app.websocket("/ws/{world_id}")
async def ws_world_feed(websocket, world_id: str):
    await websocket_endpoint(websocket, world_id)


# ---------------------------------------------------------------------------
# Root (rate-limited)
# ---------------------------------------------------------------------------
@app.get("/", summary="Root endpoint", tags=["health"])
@limiter.limit("100/minute")
def read_root(request: Request):
    return {"message": "Welcome to the LLMFed API"}


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    logger.info("Starting LLMFed API server...")
    uvicorn.run("api_gateway.main:app", host="0.0.0.0", port=8091, reload=True)
