"""CRUD operations for agents and federations.

Each function validates its parameters (Rule 2), checks return values (Rule 4),
and uses explicit field whitelists for updates instead of blind setattr (Rule 9).
"""
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
import logging
import uuid

from models.entities import (
    VALID_ROLES,
    AgentCreateData,
    AgentUpdateData,
    FederationCreateData,
    FederationUpdateData,
)
from models.db_models import AgentDB, FederationDB

logger = logging.getLogger(__name__)

# Whitelists for update operations (Rule 9 — no blind setattr)
_AGENT_UPDATE_FIELDS = frozenset({"name", "role", "gimmick_description", "llm_config", "federation_id"})
_FEDERATION_UPDATE_FIELDS = frozenset({"name", "description", "tier"})

# --- Agent CRUD ---


def get_agent_by_id(db: Session, agent_id: str) -> AgentDB | None:
    """Fetches an agent by its ID from the database."""
    if not agent_id:
        raise ValueError("agent_id must be a non-empty string")
    try:
        return db.query(AgentDB).filter(AgentDB.agent_id == agent_id).first()
    except SQLAlchemyError as e:
        logger.error(f"Database error fetching agent {agent_id}: {e}")
        return None


def create_agent(db: Session, agent_data: AgentCreateData) -> AgentDB | None:
    """Creates a new agent in the database."""
    if agent_data.role not in VALID_ROLES:
        raise ValueError(f"Invalid role '{agent_data.role}', must be one of {VALID_ROLES}")

    agent_id = str(uuid.uuid4())

    db_agent = AgentDB(
        agent_id=agent_id,
        user_id=agent_data.user_id,
        name=agent_data.name,
        role=agent_data.role,
        gimmick_description=agent_data.gimmick_description,
        llm_config=agent_data.llm_config,
        federation_id=agent_data.federation_id,
        current_heat=agent_data.current_heat,
        momentum=agent_data.momentum,
    )

    try:
        db.add(db_agent)
        db.commit()
        db.refresh(db_agent)
        logger.info(f"Agent '{db_agent.name}' ({db_agent.agent_id}) created.")
        return db_agent
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error creating agent '{agent_data.name}': {e}")
        return None


def get_agents(db: Session, skip: int = 0, limit: int = 100) -> list[AgentDB]:
    """Fetches multiple agents with pagination."""
    try:
        return db.query(AgentDB).offset(skip).limit(limit).all()
    except SQLAlchemyError as e:
        logger.error(f"Database error fetching agents: {e}")
        return []


def update_agent(db: Session, agent_id: str, update_data: AgentUpdateData) -> AgentDB | None:
    """Updates an agent in the database with provided data.

    Only fields in _AGENT_UPDATE_FIELDS are applied (Rule 9).
    """
    db_agent = get_agent_by_id(db, agent_id)
    if not db_agent:
        logger.warning(f"Update failed: Agent {agent_id} not found.")
        return None

    update_dict = update_data.model_dump(exclude_unset=True)

    if "role" in update_dict and update_dict["role"] not in VALID_ROLES:
        raise ValueError(f"Invalid role '{update_dict['role']}', must be one of {VALID_ROLES}")

    for key, value in update_dict.items():
        if key not in _AGENT_UPDATE_FIELDS:
            logger.warning(f"Ignoring unexpected update field '{key}' for agent {agent_id}")
            continue
        setattr(db_agent, key, value)

    try:
        db.add(db_agent)
        db.commit()
        db.refresh(db_agent)
        logger.info(f"Agent {agent_id} updated successfully.")
        return db_agent
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error updating agent {agent_id}: {e}")
        return None


def delete_agent(db: Session, agent_id: str) -> bool:
    """Deletes an agent from the database."""
    db_agent = get_agent_by_id(db, agent_id)
    if not db_agent:
        logger.warning(f"Delete failed: Agent {agent_id} not found.")
        return False

    try:
        db.delete(db_agent)
        db.commit()
        logger.info(f"Agent {agent_id} deleted successfully.")
        return True
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error deleting agent {agent_id}: {e}")
        return False


def get_agents_by_federation_id(db: Session, federation_id: str) -> list[AgentDB]:
    """Fetches all agents belonging to a specific federation."""
    try:
        return db.query(AgentDB).filter(AgentDB.federation_id == federation_id).all()
    except SQLAlchemyError as e:
        logger.error(f"Database error fetching agents for federation {federation_id}: {e}")
        return []


# --- Federation CRUD ---


def get_federation_by_id(db: Session, federation_id: str) -> FederationDB | None:
    """Fetches a federation by its ID from the database."""
    if not federation_id:
        raise ValueError("federation_id must be a non-empty string")
    try:
        return db.query(FederationDB).filter(FederationDB.federation_id == federation_id).first()
    except SQLAlchemyError as e:
        logger.error(f"Database error fetching federation {federation_id}: {e}")
        return None


def create_federation(db: Session, fed_data: FederationCreateData) -> FederationDB | None:
    """Creates a new federation in the database."""
    federation_id = str(uuid.uuid4())

    db_federation = FederationDB(
        federation_id=federation_id,
        name=fed_data.name,
        description=fed_data.description,
        tier=fed_data.tier,
        owner_user_id=fed_data.owner_user_id,
    )

    try:
        db.add(db_federation)
        db.commit()
        db.refresh(db_federation)
        logger.info(f"Federation '{db_federation.name}' ({db_federation.federation_id}) created.")
        return db_federation
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error creating federation '{fed_data.name}': {e}")
        return None


def get_federations(db: Session, skip: int = 0, limit: int = 100) -> list[FederationDB]:
    """Fetches all federations with pagination."""
    try:
        return db.query(FederationDB).offset(skip).limit(limit).all()
    except SQLAlchemyError as e:
        logger.error(f"Database error fetching all federations: {e}")
        return []


def update_federation(db: Session, federation_id: str, update_data: FederationUpdateData) -> FederationDB | None:
    """Updates a federation in the database.

    Only fields in _FEDERATION_UPDATE_FIELDS are applied (Rule 9).
    """
    db_federation = get_federation_by_id(db, federation_id)
    if not db_federation:
        logger.warning(f"Update failed: Federation {federation_id} not found.")
        return None

    update_dict = update_data.model_dump(exclude_unset=True)

    for key, value in update_dict.items():
        if key not in _FEDERATION_UPDATE_FIELDS:
            logger.warning(f"Ignoring unexpected update field '{key}' for federation {federation_id}")
            continue
        setattr(db_federation, key, value)

    try:
        db.add(db_federation)
        db.commit()
        db.refresh(db_federation)
        logger.info(f"Federation {federation_id} updated successfully.")
        return db_federation
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error updating federation {federation_id}: {e}")
        return None


def delete_federation(db: Session, federation_id: str) -> bool:
    """Deletes a federation from the database.

    Refuses to delete if the federation still contains agents.
    """
    db_federation = get_federation_by_id(db, federation_id)
    if not db_federation:
        logger.warning(f"Delete failed: Federation {federation_id} not found.")
        return False

    agents_in_fed = get_agents_by_federation_id(db, federation_id)
    if agents_in_fed:
        logger.warning(f"Cannot delete federation {federation_id}: still has {len(agents_in_fed)} agents.")
        return False

    try:
        db.delete(db_federation)
        db.commit()
        logger.info(f"Federation {federation_id} deleted successfully.")
        return True
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error deleting federation {federation_id}: {e}")
        return False
