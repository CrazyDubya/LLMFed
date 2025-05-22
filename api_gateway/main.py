import os
# Configure local Ollama before any imports to enforce using long-gemma
os.environ.setdefault("OPENAI_MODEL", "long-gemma")
os.environ.setdefault("OPENAI_API_BASE", "http://127.0.0.1:11434/v1")

from fastapi import FastAPI, HTTPException, Depends, Query
from dataclasses import asdict
import logging
import traceback
from typing import Optional, List
import uuid
from pydantic import BaseModel
from sqlalchemy.orm import Session

# Import models
try:
    from models.entities import Agent, AgentCreateData, AgentUpdateData, Federation, FederationCreateData, FederationUpdateData, EventContext, AgentActionResponse, PrompterHintRequest
    from models.db_models import AgentDB, FederationDB, EngineRequestDB, NarrativeLogDB
except ImportError:
    import sys, os
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.append(project_root)
    from models.entities import Agent, AgentCreateData, AgentUpdateData, Federation, FederationCreateData, FederationUpdateData, EventContext, AgentActionResponse, PrompterHintRequest
    from models.db_models import AgentDB, FederationDB, EngineRequestDB, NarrativeLogDB

# Import database stuff and CRUD functions
try:
    from agent_service import crud
    from agent_service.database import get_db, SessionLocal, engine
except ImportError as e:
    import sys, os
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    from agent_service import crud
    from agent_service.database import get_db, SessionLocal, engine
    logging.warning(f"Had to adjust path for agent_service import: {e}")

# Engine import
try:
    from core_engine.engine import engine_instance
    from core_engine.prompt_builder import PromptBuilder
    from core_engine.llm_client import LLMClient
except ImportError:
    # If package path issues, adjust
    import sys, os
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.append(project_root)
    from core_engine.engine import engine_instance
    from core_engine.prompt_builder import PromptBuilder
    from core_engine.llm_client import LLMClient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="LLMFed API",
    description="API for managing and interacting with LLM Wrestling Agents and Federations.",
    version="0.1.0"
)

@app.get("/", summary="Root endpoint", description="Provides a simple welcome message.")
def read_root():
    logger.info("Root endpoint accessed.")
    return {"message": "Welcome to the LLMFed API"}

# --- Agent Management Endpoints ---

@app.post("/agents", summary="Create Agent", response_model=Agent, status_code=201)
def create_agent_endpoint(agent_data: AgentCreateData, db: Session = Depends(get_db)):
    """Creates a new LLM agent in the database."""
    logger.info(f"Received request to create agent for user: {agent_data.user_id}")

    # --- Basic Validation (Add more robust checks later) ---
    # Real user validation would go here
    # --------------------------------------------------------

    # Call CRUD function to create agent in DB
    # Validate the llm_config structure first
    try:
        from models.entities import AgentConfig # Import for validation
        AgentConfig(**agent_data.llm_config) # Validate dict structure
    except Exception as e:
        logger.error(f"LLM Config validation error: {e}")
        raise HTTPException(status_code=422, detail=f"Invalid llm_config format: {e}")

    # Pass the original agent_data (which includes the llm_config dict)
    db_agent = crud.create_agent(db=db, agent_data=agent_data)

    if db_agent is None:
        logger.error(f"Failed to create agent '{agent_data.name}' in database.")
        raise HTTPException(status_code=500, detail="Failed to create agent in database.")

    logger.info(f"Agent '{db_agent.name}' ({db_agent.agent_id}) created successfully via CRUD.")

    return db_agent

@app.get("/agents/{agent_id}", summary="Get Agent by ID", response_model=Agent)
def get_agent_endpoint(agent_id: str, db: Session = Depends(get_db)):
    """Retrieves details for a specific agent by their ID from the database."""
    logger.info(f"Received request to get agent with ID: {agent_id}")

    db_agent = crud.get_agent_by_id(db=db, agent_id=agent_id)

    if db_agent is None:
        logger.warning(f"Agent with ID '{agent_id}' not found in DB.")
        raise HTTPException(status_code=404, detail=f"Agent with ID '{agent_id}' not found.")

    logger.info(f"Agent '{db_agent.name}' ({agent_id}) found in DB and returned.")
    return db_agent

@app.patch("/agents/{agent_id}", summary="Update Agent", response_model=Agent)
def update_agent_endpoint(agent_id: str, update_data: AgentUpdateData, db: Session = Depends(get_db)):
    """Updates specific fields of an existing agent."""
    logger.info(f"Received request to update agent ID: {agent_id} with data: {update_data.dict(exclude_unset=True)}")

    # Validation for llm_config if provided
    if update_data.llm_config is not None:
        try:
            from models.entities import AgentConfig # Import for validation
            AgentConfig(**update_data.llm_config) # Validate dict structure
        except Exception as e:
            logger.error(f"LLM Config validation error during update: {e}")
            raise HTTPException(status_code=422, detail=f"Invalid llm_config format: {e}")

    updated_agent = crud.update_agent(db=db, agent_id=agent_id, update_data=update_data)
    if updated_agent is None:
        # crud.update_agent returns None if agent not found or on DB error
        # Check if agent exists first for clearer 404 vs 500
        existing_agent = crud.get_agent_by_id(db=db, agent_id=agent_id)
        if not existing_agent:
             raise HTTPException(status_code=404, detail=f"Agent with ID '{agent_id}' not found.")
        else:
            raise HTTPException(status_code=500, detail="Failed to update agent in database.")

    logger.info(f"Agent '{updated_agent.name}' ({agent_id}) updated successfully.")
    return updated_agent

@app.delete("/agents/{agent_id}", summary="Delete Agent", status_code=204) # 204 No Content on success
def delete_agent_endpoint(agent_id: str, db: Session = Depends(get_db)):
    """Deletes an agent from the database."""
    logger.info(f"Received request to delete agent ID: {agent_id}")

    # Add user ownership check here in a real app before deleting

    deleted = crud.delete_agent(db=db, agent_id=agent_id)
    if not deleted:
        # crud.delete_agent returns False if agent not found or on DB error
        # Check if agent exists first for clearer 404 vs 500
        existing_agent = crud.get_agent_by_id(db=db, agent_id=agent_id)
        if not existing_agent:
            raise HTTPException(status_code=404, detail=f"Agent with ID '{agent_id}' not found.")
        else:
             # Agent check passed in CRUD, must be other DB error
             raise HTTPException(status_code=500, detail="Failed to delete agent from database.")

    logger.info(f"Agent {agent_id} deleted successfully.")
    # No response body needed for 204
    return None

# --- Federation Management Endpoints ---

@app.get("/federations", summary="List All Federations", response_model=List[Federation])
def list_federations_endpoint(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Retrieves a list of all federations, with optional pagination."""
    logger.info(f"Received request to list all federations (skip={skip}, limit={limit})")
    federations = crud.get_federations(db=db, skip=skip, limit=limit)
    logger.info(f"Returning {len(federations)} federations.")
    # FastAPI maps List[FederationDB] to List[Federation]
    return federations

@app.post("/federations", summary="Create Federation", response_model=Federation, status_code=201)
def create_federation_endpoint(fed_data: FederationCreateData, db: Session = Depends(get_db)):
    """Creates a new Wrestling Federation."""
    logger.info(f"Received request to create federation: {fed_data.name}")
    # Basic validation (e.g., check if user exists)
    # Real user validation would go here

    db_federation = crud.create_federation(db=db, fed_data=fed_data)
    if db_federation is None:
        logger.error(f"Failed to create federation '{fed_data.name}' in database.")
        raise HTTPException(status_code=500, detail="Failed to create federation in database.")

    logger.info(f"Federation '{db_federation.name}' ({db_federation.federation_id}) created successfully.")
    # FastAPI will map FederationDB to Federation Pydantic model
    return db_federation

@app.get("/federations/{federation_id}", summary="Get Federation by ID", response_model=Federation)
def get_federation_endpoint(federation_id: str, db: Session = Depends(get_db)):
    """Retrieves details for a specific federation by its ID."""
    logger.info(f"Received request to get federation with ID: {federation_id}")
    db_federation = crud.get_federation_by_id(db=db, federation_id=federation_id)

    if db_federation is None:
        logger.warning(f"Federation with ID '{federation_id}' not found.")
        raise HTTPException(status_code=404, detail=f"Federation with ID '{federation_id}' not found.")

    logger.info(f"Federation '{db_federation.name}' ({federation_id}) found and returned.")
    return db_federation

@app.get("/federations/{federation_id}/agents", summary="List Agents in Federation", response_model=List[Agent])
def list_agents_in_federation_endpoint(federation_id: str, db: Session = Depends(get_db)):
    """Retrieves a list of all agents belonging to a specific federation."""
    logger.info(f"Received request to list agents for federation ID: {federation_id}")

    # First, check if the federation exists
    db_federation = crud.get_federation_by_id(db=db, federation_id=federation_id)
    if db_federation is None:
        logger.warning(f"Federation with ID '{federation_id}' not found when trying to list agents.")
        raise HTTPException(status_code=404, detail=f"Federation with ID '{federation_id}' not found.")

    agents_in_federation = crud.get_agents_by_federation_id(db=db, federation_id=federation_id)
    # FastAPI will map the list of AgentDB objects to a list of Agent Pydantic models
    logger.info(f"Returning {len(agents_in_federation)} agents for federation {federation_id}.")
    return agents_in_federation

@app.patch("/federations/{federation_id}", summary="Update Federation", response_model=Federation)
def update_federation_endpoint(federation_id: str, update_data: FederationUpdateData, db: Session = Depends(get_db)):
    """Updates specific fields of an existing federation (e.g., name, description)."""
    logger.info(f"Received request to update federation ID: {federation_id} with data: {update_data.dict(exclude_unset=True)}")

    # Add ownership check here in a real app

    updated_federation = crud.update_federation(db=db, federation_id=federation_id, update_data=update_data)
    if updated_federation is None:
        # Check if federation exists for 404 vs 500
        existing_federation = crud.get_federation_by_id(db=db, federation_id=federation_id)
        if not existing_federation:
             raise HTTPException(status_code=404, detail=f"Federation with ID '{federation_id}' not found.")
        else:
            raise HTTPException(status_code=500, detail="Failed to update federation in database.")

    logger.info(f"Federation '{updated_federation.name}' ({federation_id}) updated successfully.")
    return updated_federation

@app.delete("/federations/{federation_id}", summary="Delete Federation", status_code=204)
def delete_federation_endpoint(federation_id: str, db: Session = Depends(get_db)):
    """Deletes a federation. Requires the federation to be empty of agents."""
    logger.info(f"Received request to delete federation ID: {federation_id}")

    # **SECURITY NOTE**: Add ownership check here in a real app

    # Check if federation exists before attempting delete
    existing_federation = crud.get_federation_by_id(db=db, federation_id=federation_id)
    if not existing_federation:
        raise HTTPException(status_code=404, detail=f"Federation with ID '{federation_id}' not found.")

    # Attempt deletion (crud function includes check for agents)
    deleted = crud.delete_federation(db=db, federation_id=federation_id)
    if not deleted:
        # If not deleted, it's either because it had agents or a DB error occurred.
        # The crud log will indicate if agents were present.
        # We check again for agents to provide a specific error message.
        agents_in_fed = crud.get_agents_by_federation_id(db, federation_id)
        if agents_in_fed:
            logger.warning(f"Deletion of federation {federation_id} failed because it contains agents.")
            raise HTTPException(status_code=409, # Conflict
                                detail=f"Federation {federation_id} cannot be deleted because it still contains agents.")
        else:
             # Agent check passed in CRUD, must be other DB error
             raise HTTPException(status_code=500, detail="Failed to delete federation from database.")

    logger.info(f"Federation {federation_id} deleted successfully.")
    # No response body needed for 204
    return None

# --- Agent Interaction Endpoint ---

@app.post("/agents/{agent_id}/actions", summary="Submit Agent Action", status_code=202) # 202 Accepted
def submit_agent_action(agent_id: str, action_response: AgentActionResponse, db: Session = Depends(get_db)):
    """Endpoint for an agent to submit its chosen action in response to an event."""
    logger.info(f"Received action from agent {agent_id} for event {action_response.event_id}")
    logger.debug(f"Action details: {action_response.dict()}")

    # --- Validation ---
    # 1. Check if agent exists
    db_agent = crud.get_agent_by_id(db=db, agent_id=agent_id)
    if not db_agent:
        logger.warning(f"Action submission failed: Agent {agent_id} not found.")
        raise HTTPException(status_code=404, detail=f"Agent with ID '{agent_id}' not found.")

    # 2. Check if the event_id is valid/expected (requires tracking active events - TO DO)
    #    For now, just log it.
    logger.info(f"Agent {agent_id} ({db_agent.name}) submitted action '{action_response.chosen_action_id}' for event '{action_response.event_id}'")

    # 3. Basic validation of target_agent_id if required (existence check)
    if action_response.target_agent_id:
        db_target_agent = crud.get_agent_by_id(db=db, agent_id=action_response.target_agent_id)
        if not db_target_agent:
             logger.warning(f"Action submission failed: Target agent {action_response.target_agent_id} not found.")
             raise HTTPException(status_code=404, detail=f"Target agent with ID '{action_response.target_agent_id}' not found.")

    # --- TODO: Game Logic Processing ---
    # - Fetch the actual event context based on action_response.event_id
    # - Validate that chosen_action_id was one of the available_actions in that context
    # - Validate target_agent_id was provided if action required it
    # - Update game state based on the action
    # - Potentially queue up next event context for involved agents

    logger.info(f"Action from agent {agent_id} accepted for processing.")

    # Return simple acknowledgement for now
    return {"message": "Action received and accepted for processing.", "event_id": action_response.event_id, "chosen_action": action_response.chosen_action_id}

# --- Engine Control Endpoints ---

@app.post("/engine/advance", summary="Advance Simulation Ticks")
def advance_engine(
    n_ticks: int = Query(1, ge=1, description="Number of ticks to advance")
):
    """Advance the core engine by `n_ticks` ticks and return the TickResult list."""
    try:
        results = engine_instance.run_ticks(n_ticks)
        return [asdict(r) for r in results]
    except Exception as e:
        tb = traceback.format_exc()
        logger.error(f"Failed to advance engine: {e}\n{tb}")
        raise HTTPException(status_code=500, detail={"error": str(e), "trace": tb})

@app.get("/engine/requests", summary="List Engine Requests")
def list_engine_requests(limit: int = 10, db: Session = Depends(get_db)):
    """Debug endpoint to show persisted engine requests."""
    try:
        requests = db.query(EngineRequestDB).order_by(EngineRequestDB.due_tick.desc()).limit(limit).all()
        return [
            {
                "request_id": r.request_id,
                "agent_id": r.agent_id,
                "due_tick": r.due_tick,
                "status": r.status,
                "created_at": r.created_at.isoformat(),
            }
            for r in requests
        ]
    except Exception as e:
        logger.error(f"Failed to fetch engine requests: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/engine/narrative", summary="List Narrative Logs")
def list_narrative_logs(limit: int = Query(100, ge=1, le=1000), db: Session = Depends(get_db)):
    """Retrieve recent narrative log entries for plays-by-play."""
    try:
        logs = db.query(NarrativeLogDB).order_by(NarrativeLogDB.created_at.desc()).limit(limit).all()
        return [
            {
                "id": log.id,
                "tick_id": log.tick_id,
                "time_index": log.time_index,
                "agent_id": log.agent_id,
                "role": log.role,
                "description": log.description,
                "created_at": log.created_at.isoformat(),
            }
            for log in logs
        ]
    except Exception as e:
        logger.error(f"Failed to fetch narrative logs: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/engine/debug", summary="Engine Debug Info")
def engine_debug():
    """Return engine and database status."""
    from agent_service.database import engine
    from models.db_models import Base
    from sqlalchemy import inspect
    from core_engine.engine import engine_instance
    
    inspector = inspect(engine)
    return {
        "tables": inspector.get_table_names(),
        "engine_state": {
            "current_tick": engine_instance.state.current_tick,
            "pending_requests": len(engine_instance.get_pending_requests())
        }
    }

# --- Federation Interaction & Subscription Placeholders ---

@app.post("/agents/{agent_id}/subscribe", summary="Subscribe Agent to Events", description="(Placeholder) Agent registers a webhook for event notifications.")
def subscribe_agent(agent_id: str, webhook_url: str = Query(..., description="Webhook URL for event notifications"), db: Session = Depends(get_db)):
    logger.info(f"Placeholder endpoint /agents/{agent_id}/subscribe POST accessed for URL: {webhook_url}")
    db_agent = crud.get_agent_by_id(db=db, agent_id=agent_id)
    if not db_agent:
         logger.warning(f"Subscription attempt for non-existent agent: {agent_id}")
         raise HTTPException(status_code=404, detail=f"Agent with ID '{agent_id}' not found.")

    logger.info(f"Webhook URL for agent {agent_id} would be updated to {webhook_url} (DB update TBD).")
    return {"message": f"Subscription request for agent {agent_id} to URL: {webhook_url} (DB update TBD)"}

@app.post("/federations/{federation_id}/subscribe", summary="Subscribe to Federation Events", description="(Placeholder) Agent subscribes to events.")
def subscribe_federation(federation_id: str, webhook_url: str = Query(..., description="Webhook URL for event notifications"), db: Session = Depends(get_db)):
    logger.info(f"Placeholder endpoint /federations/{federation_id}/subscribe POST accessed for URL: {webhook_url}")
    db_federation = crud.get_federation_by_id(db=db, federation_id=federation_id)
    if not db_federation:
         logger.warning(f"Subscription attempt for non-existent federation: {federation_id}")
         raise HTTPException(status_code=404, detail=f"Federation with ID '{federation_id}' not found.")

    logger.info(f"Webhook URL for federation {federation_id} would be updated to {webhook_url} (DB update TBD).")
    return {"message": f"Subscription request for federation {federation_id} to URL: {webhook_url} (DB update TBD)"}

@app.post("/prompter/hints", summary="Prompter Hints")
def prompter_hints(request: PrompterHintRequest):
    """Accepts promoter hints, stores them, and builds LLM prompt."""
    engine_instance.set_hints(request.hints)
    prompt = PromptBuilder.build_prompt(request.context, request.hints)
    return prompt

@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "database": "connected",
        "engine_initialized": True
    }

@app.get("/api/tags", summary="List available LLM models from proxy")
def list_proxy_models():
    """Fetch and return model IDs from the local LLM proxy via OpenAI-compatible /models endpoint."""
    base = os.getenv("OPENAI_API_BASE", "http://127.0.0.1:11434/v1")
    url = f"{base.rstrip('/')}/models"
    try:
        import httpx
        resp = httpx.get(url)
        resp.raise_for_status()
        return [m.get("id") for m in resp.json().get("data", [])]
    except Exception as e:
        logging.error(f"Error fetching models from {url}: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching models: {e}")

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting LLMFed API server...")
    # Switch to a different port, e.g., 8091
    uvicorn.run("main:app", host="0.0.0.0", port=8091, reload=True)
