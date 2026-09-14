import pytest
import pytest_asyncio
from agent_service.database import AsyncSessionLocal, init_db
from agent_service.crud import create_agent, get_agent_by_id, update_agent, delete_agent, get_agents, get_agents_by_federation_id
from models.entities import AgentCreateData, AgentUpdateData


@pytest_asyncio.fixture
async def db():
    await init_db()
    async with AsyncSessionLocal() as session:
        yield session


@pytest.mark.asyncio
async def test_create_get_update_delete_agent(db):
    # Create agent
    agent_data = AgentCreateData(
        user_id="user1",
        name="Test Agent",
        role="participant",
        gimmick_description="desc",
        llm_config={},
        federation_id="fed1"
    )
    agent = await create_agent(db, agent_data)
    assert agent is not None
    # Get agent
    got = await get_agent_by_id(db, agent.agent_id)
    assert got.agent_id == agent.agent_id
    # Update agent
    update_data = AgentUpdateData(name="NewName")
    updated = await update_agent(db, agent.agent_id, update_data)
    assert updated.name == "NewName"
    # List agents and by federation
    agents = await get_agents(db)
    assert any(a.agent_id == agent.agent_id for a in agents)
    fed_agents = await get_agents_by_federation_id(db, "fed1")
    assert any(a.agent_id == agent.agent_id for a in fed_agents)
    # Delete agent
    assert await delete_agent(db, agent.agent_id) is True
    assert await get_agent_by_id(db, agent.agent_id) is None
