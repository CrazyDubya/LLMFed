"""Shared pytest fixtures for the legacy agent/engine subsystem.

Most test modules manage their own isolated in-memory SQLite engine and
never touch ``agent_service.database``. The handful of tests that exercise
``core_engine.engine`` / ``agent_service.crud`` directly go through the
real (file-based, async) engine configured in ``agent_service.database``,
so its tables need to exist there once per test session.
"""

import pytest_asyncio

from agent_service.database import engine as agent_db_engine
from models.db_models import Base as AgentBase


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _create_agent_service_tables():
    async with agent_db_engine.begin() as conn:
        await conn.run_sync(AgentBase.metadata.create_all)
