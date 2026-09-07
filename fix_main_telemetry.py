filepath = "api_gateway/main.py"
with open(filepath, "r") as f:
    content = f.read()

imports = """
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
"""

if "FastAPICache" not in content:
    content = content.replace(
        "from fastapi import FastAPI, Request",
        imports + "\nfrom fastapi import FastAPI, Request",
    )

startup = """
    # Setup Redis Cache
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    try:
        redis = aioredis.from_url(redis_url, encoding="utf8", decode_responses=True)
        FastAPICache.init(RedisBackend(redis), prefix="fastapi-cache")
    except Exception as e:
        logger.warning(f"Failed to connect to redis, caching disabled: {e}")
"""

if "FastAPICache.init" not in content:
    content = content.replace(
        "async def _on_startup():\n    start_reaper()",
        f"async def _on_startup():\n    start_reaper()\n{startup}",
    )

with open(filepath, "w") as f:
    f.write(content)
