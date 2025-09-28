from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
import logging
from datetime import datetime
import uuid

# Import Pydantic models for data structure validation/typing hints
# Adjust path as necessary
import sys
import os
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)
try:
    from models.entities import AgentCreateData, Agent, AgentUpdateData, FederationCreateData, Federation, FederationUpdateData # Pydantic models
    from models.db_models import AgentDB, FederationDB # SQLAlchemy model
except ImportError as e:
    print(f"Error importing models in crud.py: {e}")
    # Define dummy classes if import fails to avoid runtime errors in basic functions
    class AgentCreateData: pass
    class Agent: pass
    class AgentDB: pass
    class AgentUpdateData: pass
    class FederationCreateData: pass
    class Federation: pass
    class FederationDB: pass
    class FederationUpdateData: pass

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO) # Ensure logger is configured

# --- Agent CRUD --- 

def get_agent_by_id(db: Session, agent_id: str) -> AgentDB | None:
    """Fetches an agent by its ID from the database."""
    logger.info(f"Querying database for agent_id: {agent_id}")
    try:
        agent = db.query(AgentDB).filter(AgentDB.agent_id == agent_id).first()
        if agent:
            logger.info(f"Agent found: {agent.name} ({agent.agent_id})")
        else:
            logger.info(f"Agent with id {agent_id} not found in DB.")
        return agent
    except SQLAlchemyError as e:
        logger.error(f"Database error fetching agent {agent_id}: {e}")
        # Depending on desired behavior, you might raise the exception
        # or return None after logging.
        return None

def create_agent(db: Session, agent_data: AgentCreateData) -> AgentDB | None:
    """Creates a new agent in the database."""
    logger.info(f"Attempting to create agent '{agent_data.name}' for user {agent_data.user_id}")
    # Generate server-side fields
    agent_id = str(uuid.uuid4())
    api_key = f"llmfed_{uuid.uuid4()}"

    # Create SQLAlchemy DB model instance
    db_agent = AgentDB(
        agent_id=agent_id,
        user_id=agent_data.user_id,
        name=agent_data.name,
        role=agent_data.role,
        gimmick_description=agent_data.gimmick_description,
        llm_config=agent_data.llm_config, # Store dict directly
        api_key=api_key,
        webhook_url=agent_data.webhook_url,
        federation_id=agent_data.federation_id, # Assign federation_id from input
        current_heat=agent_data.current_heat,
        momentum=agent_data.momentum
    )

    try:
        db.add(db_agent)
        db.commit()
        db.refresh(db_agent) # Refresh to get DB-generated defaults if any
        logger.info(f"Agent '{db_agent.name}' ({db_agent.agent_id}) created successfully in DB.")
        return db_agent
    except SQLAlchemyError as e:
        db.rollback() # Rollback in case of error
        logger.error(f"Database error creating agent '{agent_data.name}': {e}")
        return None

# Placeholder for other CRUD operations
def get_agents(db: Session, skip: int = 0, limit: int = 100) -> list[AgentDB]:
    """Fetches multiple agents with pagination."""
    logger.info(f"Querying for agents with skip={skip}, limit={limit}")
    try:
        return db.query(AgentDB).offset(skip).limit(limit).all()
    except SQLAlchemyError as e:
        logger.error(f"Database error fetching agents: {e}")
        return []

def update_agent(db: Session, agent_id: str, update_data: AgentUpdateData) -> AgentDB | None:
    """Updates an agent in the database with provided data."""
    logger.info(f"Attempting to update agent {agent_id}")
    db_agent = get_agent_by_id(db, agent_id)
    if not db_agent:
        logger.warning(f"Update failed: Agent {agent_id} not found.")
        return None

    # Convert Pydantic model to dict, excluding unset fields
    update_dict = update_data.dict(exclude_unset=True)

    # Special handling for llm_config if needed (e.g., merging)
    # For now, direct replacement if provided

    logger.info(f"Applying updates: {update_dict}")
    for key, value in update_dict.items():
        setattr(db_agent, key, value)

    try:
        db.add(db_agent) # Add the modified object to the session
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
    logger.info(f"Attempting to delete agent {agent_id}")
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
    logger.info(f"Querying database for agents in federation_id: {federation_id}")
    try:
        agents = db.query(AgentDB).filter(AgentDB.federation_id == federation_id).all()
        logger.info(f"Found {len(agents)} agents in federation {federation_id}.")
        return agents
    except SQLAlchemyError as e:
        logger.error(f"Database error fetching agents for federation {federation_id}: {e}")
        return []

# --- Federation CRUD ---

def get_federation_by_id(db: Session, federation_id: str) -> FederationDB | None:
    """Fetches a federation by its ID from the database."""
    logger.info(f"Querying database for federation_id: {federation_id}")
    try:
        federation = db.query(FederationDB).filter(FederationDB.federation_id == federation_id).first()
        if federation:
            logger.info(f"Federation found: {federation.name} ({federation.federation_id})")
        else:
            logger.info(f"Federation with id {federation_id} not found in DB.")
        return federation
    except SQLAlchemyError as e:
        logger.error(f"Database error fetching federation {federation_id}: {e}")
        return None

def create_federation(db: Session, fed_data: FederationCreateData) -> FederationDB | None:
    """Creates a new federation in the database."""
    logger.info(f"Attempting to create federation '{fed_data.name}' for user {fed_data.owner_user_id}")
    # Generate server-side fields
    federation_id = str(uuid.uuid4())

    # Create SQLAlchemy DB model instance
    db_federation = FederationDB(
        federation_id=federation_id,
        name=fed_data.name,
        description=fed_data.description,
        tier=fed_data.tier,
        owner_user_id=fed_data.owner_user_id,
        max_agents=fed_data.max_agents,
        is_active=fed_data.is_active
    )

    try:
        db.add(db_federation)
        db.commit()
        db.refresh(db_federation)
        logger.info(f"Federation '{db_federation.name}' ({db_federation.federation_id}) created successfully.")
        return db_federation
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error creating federation '{fed_data.name}': {e}")
        return None

def get_federations(db: Session, skip: int = 0, limit: int = 100) -> list[FederationDB]:
    """Fetches all federations with pagination."""
    logger.info(f"Querying database for all federations (skip={skip}, limit={limit})")
    try:
        federations = db.query(FederationDB).offset(skip).limit(limit).all()
        logger.info(f"Found {len(federations)} federations.")
        return federations
    except SQLAlchemyError as e:
        logger.error(f"Database error fetching all federations: {e}")
        return []

def update_federation(db: Session, federation_id: str, update_data: FederationUpdateData) -> FederationDB | None:
    """Updates a federation in the database with provided data."""
    logger.info(f"Attempting to update federation {federation_id}")
    db_federation = get_federation_by_id(db, federation_id)
    if not db_federation:
        logger.warning(f"Update failed: Federation {federation_id} not found.")
        return None

    # Convert Pydantic model to dict, excluding unset fields
    update_dict = update_data.dict(exclude_unset=True)

    logger.info(f"Applying updates to federation: {update_dict}")
    for key, value in update_dict.items():
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
    WARNING: This is a hard delete. Consider soft delete or cascading logic.
    Also needs strict ownership/permission checks.
    """
    logger.info(f"Attempting to delete federation {federation_id}")
    db_federation = get_federation_by_id(db, federation_id)
    if not db_federation:
        logger.warning(f"Delete failed: Federation {federation_id} not found.")
        return False

    # **SECURITY NOTE**: Add checks here: Is the requesting user the owner?
    # Also, decide on agent handling: orphan agents? delete agents? prevent delete if agents exist?
    # For now, we proceed with caution.
    agents_in_fed = get_agents_by_federation_id(db, federation_id)
    if agents_in_fed:
        logger.warning(f"Attempted to delete federation {federation_id} which still has {len(agents_in_fed)} agents. Aborting deletion.")
        # Option 1: Prevent deletion (safest for now)
        return False
        # Option 2: Orphan agents (set agent.federation_id to None)
        # Option 3: Delete agents (requires careful consideration)

    try:
        db.delete(db_federation)
        db.commit()
        logger.info(f"Federation {federation_id} deleted successfully.")
        return True
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error deleting federation {federation_id}: {e}")
        return False
