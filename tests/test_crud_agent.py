import pytest
from agent_service.database import SessionLocal, init_db
from agent_service.crud import create_agent, get_agent_by_id, update_agent, delete_agent, get_agents, get_agents_by_federation_id
from models.entities import AgentCreateData, AgentUpdateData

@ pytest.fixture(scope="module")
def db():
    init_db()
    db = SessionLocal()
    yield db
    db.close()


def test_create_get_update_delete_agent(db):
    # Create agent
    agent_data = AgentCreateData(
        user_id="user1",
        name="Test Agent",
        role="role1",
        gimmick_description="desc",
        llm_config={},
        webhook_url="http://example.com",
        federation_id="fed1"
    )
    agent = create_agent(db, agent_data)
    assert agent is not None
    # Get agent
    got = get_agent_by_id(db, agent.agent_id)
    assert got.agent_id == agent.agent_id
    # Update agent
    update_data = AgentUpdateData(name="NewName")
    updated = update_agent(db, agent.agent_id, update_data)
    assert updated.name == "NewName"
    # List agents and by federation
    agents = get_agents(db)
    assert any(a.agent_id == agent.agent_id for a in agents)
    fed_agents = get_agents_by_federation_id(db, "fed1")
    assert any(a.agent_id == agent.agent_id for a in fed_agents)
    # Delete agent
    assert delete_agent(db, agent.agent_id) is True
    assert get_agent_by_id(db, agent.agent_id) is None
