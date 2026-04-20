import logging
import uuid
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from models.db_models import AgentDB, FederationDB
from models.entities import Agent, AgentCreateData, AgentUpdateData, Federation, FederationCreateData, FederationUpdateData

logger = logging.getLogger(__name__)

async def get_federations(db: AsyncSession, skip: int = 0, limit: int = 100) -> List[Federation]:
    result = await db.execute(select(FederationDB).offset(skip).limit(limit))
    return [Federation.model_validate(f) for f in result.scalars().all()]

async def create_federation(db: AsyncSession, fed_data: FederationCreateData) -> Federation:
    db_fed = FederationDB(
        federation_id=str(uuid.uuid4()),
        name=fed_data.name,
        description=fed_data.description,
        tier=fed_data.tier,
        owner_user_id=fed_data.owner_user_id,
        is_active=fed_data.is_active,
        max_agents=fed_data.max_agents
    )
    db.add(db_fed)
    await db.commit()
    await db.refresh(db_fed)
    return Federation.model_validate(db_fed)

async def get_federation_by_id(db: AsyncSession, federation_id: str) -> Optional[Federation]:
    result = await db.execute(select(FederationDB).filter(FederationDB.federation_id == federation_id))
    db_fed = result.scalars().first()
    return Federation.model_validate(db_fed) if db_fed else None

async def update_federation(db: AsyncSession, federation_id: str, update_data: FederationUpdateData) -> Optional[Federation]:
    result = await db.execute(select(FederationDB).filter(FederationDB.federation_id == federation_id))
    db_fed = result.scalars().first()
    if not db_fed:
        return None
    for k, v in update_data.model_dump(exclude_unset=True).items():
        setattr(db_fed, k, v)
    await db.commit()
    await db.refresh(db_fed)
    return Federation.model_validate(db_fed)

async def delete_federation(db: AsyncSession, federation_id: str) -> bool:
    result = await db.execute(select(FederationDB).filter(FederationDB.federation_id == federation_id))
    db_fed = result.scalars().first()
    if not db_fed:
        return False
    await db.delete(db_fed)
    await db.commit()
    return True

async def get_agents(db: AsyncSession, skip: int = 0, limit: int = 100) -> List[Agent]:
    result = await db.execute(select(AgentDB).offset(skip).limit(limit))
    return [Agent.model_validate(a) for a in result.scalars().all()]

async def create_agent(db: AsyncSession, agent_data: AgentCreateData) -> Agent:
    db_agent = AgentDB(
        agent_id=str(uuid.uuid4()),
        user_id=agent_data.user_id,
        name=agent_data.name,
        role=agent_data.role,
        gimmick_description=agent_data.gimmick_description,
        federation_id=agent_data.federation_id,
        llm_config=agent_data.llm_config,
        webhook_url=agent_data.webhook_url,
        current_heat=agent_data.current_heat,
        momentum=agent_data.momentum
    )
    db.add(db_agent)
    await db.commit()
    await db.refresh(db_agent)
    return Agent.model_validate(db_agent)

async def get_agent_by_id(db: AsyncSession, agent_id: str) -> Optional[Agent]:
    result = await db.execute(select(AgentDB).filter(AgentDB.agent_id == agent_id))
    db_agent = result.scalars().first()
    return Agent.model_validate(db_agent) if db_agent else None

async def get_agents_by_federation_id(db: AsyncSession, federation_id: str) -> List[Agent]:
    result = await db.execute(select(AgentDB).filter(AgentDB.federation_id == federation_id))
    return [Agent.model_validate(a) for a in result.scalars().all()]

async def update_agent(db: AsyncSession, agent_id: str, update_data: AgentUpdateData) -> Optional[Agent]:
    result = await db.execute(select(AgentDB).filter(AgentDB.agent_id == agent_id))
    db_agent = result.scalars().first()
    if not db_agent:
        return None
    for k, v in update_data.model_dump(exclude_unset=True).items():
        setattr(db_agent, k, v)
    await db.commit()
    await db.refresh(db_agent)
    return Agent.model_validate(db_agent)

async def delete_agent(db: AsyncSession, agent_id: str) -> bool:
    result = await db.execute(select(AgentDB).filter(AgentDB.agent_id == agent_id))
    db_agent = result.scalars().first()
    if not db_agent:
        return False
    await db.delete(db_agent)
    await db.commit()
    return True
