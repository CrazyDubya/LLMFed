"""Shared pytest fixtures for the legacy agent/engine subsystem.

Most test modules manage their own isolated in-memory SQLite engine and
never touch ``agent_service.database``. The handful of tests that exercise
``core_engine.engine`` / ``agent_service.crud`` directly go through the
real (async) engine configured in ``agent_service.database``, so its
tables need to exist there once per test session.

``agent_service/database.py`` reads DATABASE_URL at import time, defaulting
to ``sqlite+aiosqlite:///./llmfed.db`` — the same file a local dev server
would use — when it isn't set. Point it at a throwaway file before that
module (or anything importing it) is first loaded, so running the suite
locally can never create tables in or commit rows to real application
data. This only takes effect if DATABASE_URL isn't already set (CI sets
its own), and the file is removed again at the end of the session.
"""

import os
import pathlib

_TEST_DB_PATH = pathlib.Path(__file__).parent / ".test_agent_service.db"
os.environ.setdefault("DATABASE_URL", f"sqlite+aiosqlite:///{_TEST_DB_PATH}")

import pytest_asyncio

from agent_service.database import engine as agent_db_engine
from models.db_models import Base as AgentBase


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _create_agent_service_tables():
    async with agent_db_engine.begin() as conn:
        await conn.run_sync(AgentBase.metadata.create_all)
    yield
    await agent_db_engine.dispose()
    _TEST_DB_PATH.unlink(missing_ok=True)
