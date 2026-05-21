import os
import sys
import logging
import traceback
import uuid
from typing import Optional, List

# Configure local Ollama before any imports to enforce using long-gemma
os.environ.setdefault("OPENAI_MODEL", "long-gemma")
os.environ.setdefault("OPENAI_API_BASE", "http://127.0.0.1:11434/v1")

# Ensure project root is on sys.path for all internal imports
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from fastapi import FastAPI, HTTPException, Depends, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from dataclasses import asdict
from pydantic import BaseModel
from sqlalchemy.orm import Session
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from models.entities import Agent, AgentCreateData, AgentUpdateData, Federation, FederationCreateData, FederationUpdateData, EventContext, AgentActionResponse, PrompterHintRequest
from models.db_models import AgentDB, FederationDB, EngineRequestDB, NarrativeLogDB, WorldAnchorDB
from agent_service import crud
from agent_service.database import get_db, SessionLocal, engine
from core_engine.engine import engine_instance
from core_engine.prompt_builder import PromptBuilder
from core_engine.llm_client import LLMClient
from api_gateway.error_handlers import register_error_handlers, ResourceNotFoundError
from api_gateway.validation import ValidationError
from api_gateway.logging_config import setup_logging, logging_middleware, performance_monitor

# Configure logging
log_level = os.getenv("LOG_LEVEL", "INFO")
use_json_logging = os.getenv("JSON_LOGGING", "false").lower() == "true"
setup_logging(log_level=log_level, use_json=use_json_logging)

logger = logging.getLogger(__name__)

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="LLMFed API",
    description="""
# LLMFed - Federated Learning Management System

An AI-powered wrestling federation simulator featuring autonomous LLM agents.

## Features

* 🤖 **Multi-Agent AI System**: Six distinct agent roles
* ⚡ **Tick-Based Simulation**: Discrete time-step processing
* 🧠 **LLM Integration**: Support for multiple providers
* 🎯 **Dynamic Storytelling**: Emergent narratives
* 🔒 **Security**: JWT auth, rate limiting, CORS
* 📊 **Monitoring**: Built-in performance tracking

## Authentication

Most endpoints require JWT authentication. Get your token from `/auth/token` endpoint.

## Rate Limiting

- Root endpoint: 100 requests/minute
- Agent creation: 10 requests/minute
- Other endpoints: Configurable per endpoint

## Documentation

For complete usage examples, see the [API Usage Examples](https://github.com/CrazyDubya/LLMFed/blob/main/API_USAGE_EXAMPLES.md).
    """,
    version="0.2.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {"name": "health", "description": "Health check endpoints"},
        {"name": "federations", "description": "Federation management operations"},
        {"name": "agents", "description": "Agent management operations"},
        {"name": "engine", "description": "Simulation engine control"},
        {"name": "simulation", "description": "End-to-end federation simulation"},
        {"name": "wrestling", "description": "Titles, storylines, wrestling domain"},
        {"name": "monitoring", "description": "Performance monitoring"}
    ]
)

# Add rate limiter to app state
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Configure CORS
ALLOWED_ORIGINS = os.getenv(
    "CORS_ORIGINS", 
    "http://localhost:3000,http://localhost:8091"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["*"],
    expose_headers=["X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset", "X-Request-ID"],
)

# Add trusted host middleware (prevent host header attacks)
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS)

# Add logging middleware
app.middleware("http")(logging_middleware)


# Security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Add security headers to all responses."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    return response

# Register error handlers
register_error_handlers(app)

@app.get("/", summary="Root endpoint", description="Provides a simple welcome message.", tags=["health"])
@limiter.limit("100/minute")
def read_root(request: Request):
    logger.info("Root endpoint accessed.")
    return {"message": "Welcome to the LLMFed API"}

# --- Agent Management Endpoints ---

@app.post("/agents", summary="Create Agent", response_model=Agent, status_code=201)
@limiter.limit("10/minute")
def create_agent_endpoint(request: Request, agent_data: AgentCreateData, db: Session = Depends(get_db)):
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
    try:
        db_agent = crud.create_agent(db=db, agent_data=agent_data)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

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
    logger.info(f"Received request to update agent ID: {agent_id} with data: {update_data.model_dump(exclude_unset=True)}")

    # Validation for llm_config if provided
    if update_data.llm_config is not None:
        try:
            from models.entities import AgentConfig # Import for validation
            AgentConfig(**update_data.llm_config) # Validate dict structure
        except Exception as e:
            logger.error(f"LLM Config validation error during update: {e}")
            raise HTTPException(status_code=422, detail=f"Invalid llm_config format: {e}")

    try:
        updated_agent = crud.update_agent(db=db, agent_id=agent_id, update_data=update_data)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
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

    try:
        db_federation = crud.create_federation(db=db, fed_data=fed_data)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
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

@app.get("/federations/{federation_id}/world_anchor", tags=["wrestling"], summary="Get World Anchor (4-Year Spine)")
def get_world_anchor(federation_id: str, db: Session = Depends(get_db)):
    """Get federation's world anchor (marquee show 2 years out). Returns default if not set."""
    from models.world_anchor import WorldAnchor, build_default_anchor
    from datetime import datetime
    row = db.query(WorldAnchorDB).filter(WorldAnchorDB.federation_id == federation_id).first()
    if not row:
        anchor = build_default_anchor(federation_id)
        return {
            "federation_id": federation_id,
            "world_start_date": anchor.world_start_date.isoformat(),
            "anchor_event_name": anchor.anchor_event_name,
            "anchor_date": anchor.get_anchor_date().isoformat(),
            "world_end_date": anchor.get_world_end_date().isoformat(),
            "source": "default",
        }
    ws = row.world_start_date.date() if hasattr(row.world_start_date, "date") else row.world_start_date
    ad = row.anchor_date.date() if row.anchor_date and hasattr(row.anchor_date, "date") else row.anchor_date
    anchor = WorldAnchor(federation_id=row.federation_id, world_start_date=ws, anchor_event_name=row.anchor_event_name, anchor_date=ad)
    return {
        "federation_id": federation_id,
        "world_start_date": anchor.world_start_date.isoformat(),
        "anchor_event_name": anchor.anchor_event_name,
        "anchor_date": anchor.get_anchor_date().isoformat(),
        "world_end_date": anchor.get_world_end_date().isoformat(),
        "source": "stored",
    }


class WorldAnchorSet(BaseModel):
    world_start_date: str  # YYYY-MM-DD
    anchor_event_name: str = "Grandstand"

@app.post("/federations/{federation_id}/world_anchor", tags=["wrestling"], summary="Set World Anchor")
def set_world_anchor(federation_id: str, body: WorldAnchorSet, db: Session = Depends(get_db)):
    """Set federation's world anchor (marquee show will be world_start + 2 years)."""
    from datetime import datetime
    from models.world_anchor import _default_anchor_date
    if crud.get_federation_by_id(db, federation_id) is None:
        raise HTTPException(status_code=404, detail="Federation not found")
    try:
        world_start = datetime.fromisoformat(body.world_start_date.replace("Z", "+00:00")).date() if "T" in body.world_start_date else datetime.strptime(body.world_start_date, "%Y-%m-%d").date()
    except Exception:
        world_start = datetime.strptime(body.world_start_date, "%Y-%m-%d").date()
    anchor_date = _default_anchor_date(world_start)
    row = db.query(WorldAnchorDB).filter(WorldAnchorDB.federation_id == federation_id).first()
    if row:
        row.world_start_date = datetime.combine(world_start, datetime.min.time())
        row.anchor_event_name = body.anchor_event_name
        row.anchor_date = datetime.combine(anchor_date, datetime.min.time())
    else:
        db.add(WorldAnchorDB(
            federation_id=federation_id,
            world_start_date=datetime.combine(world_start, datetime.min.time()),
            anchor_event_name=body.anchor_event_name,
            anchor_date=datetime.combine(anchor_date, datetime.min.time()),
        ))
    db.commit()
    return {"federation_id": federation_id, "anchor_event_name": body.anchor_event_name, "anchor_date": anchor_date.isoformat()}


@app.get("/federations/{federation_id}/anchor_card", tags=["simulation"], summary="Build Anchor Card")
def get_anchor_card(federation_id: str, db: Session = Depends(get_db)):
    """Build one coherent FullCard for the marquee show at anchor date (roster, tenure mix, titles, storylines)."""
    from models.world_anchor import WorldAnchor, build_default_anchor
    from agent_service.anchor_crud import get_conceptual_card
    from simulation.anchor_card_builder import build_anchor_card
    row = db.query(WorldAnchorDB).filter(WorldAnchorDB.federation_id == federation_id).first()
    if row:
        ws = row.world_start_date.date() if hasattr(row.world_start_date, "date") else row.world_start_date
        ad = row.anchor_date.date() if row.anchor_date and hasattr(row.anchor_date, "date") else row.anchor_date
        anchor = WorldAnchor(federation_id=federation_id, world_start_date=ws, anchor_event_name=row.anchor_event_name, anchor_date=ad)
    else:
        anchor = build_default_anchor(federation_id)
    conceptual = get_conceptual_card(db, federation_id)
    full = build_anchor_card(db, federation_id, anchor, conceptual)
    return {
        "card_id": full.card_id,
        "name": full.name,
        "card_date": anchor.get_anchor_date().isoformat(),
        "card_type": "marquee_year",
        "phase": anchor.phase_for(anchor.get_anchor_date()).value,
        "segments": [{"order": s.order, "type": s.segment_type.value, "match_id": s.match_id} for s in full.segments],
        "matches": [{"match_id": m.get("match_id"), "participant_ids": m.get("participant_ids", [])} for m in full.matches],
    }


class ConceptualCardSet(BaseModel):
    main_event_target: Optional[dict] = None
    title_matches_target: Optional[list] = None
    planned_storyline_payoffs: Optional[list] = None

@app.post("/federations/{federation_id}/conceptual_card", tags=["simulation"], summary="Set Conceptual Card Target")
def set_conceptual_card_endpoint(federation_id: str, body: ConceptualCardSet, db: Session = Depends(get_db)):
    """Set the conceptual/target card for the marquee show (plan, not run state)."""
    from agent_service.anchor_crud import set_conceptual_card
    if crud.get_federation_by_id(db, federation_id) is None:
        raise HTTPException(status_code=404, detail="Federation not found")
    ok = set_conceptual_card(
        db, federation_id,
        main_event_target=body.main_event_target,
        title_matches_target=body.title_matches_target,
        planned_storyline_payoffs=body.planned_storyline_payoffs,
    )
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to set conceptual card")
    return {"federation_id": federation_id, "message": "Conceptual card target set"}

@app.get("/federations/{federation_id}/conceptual_card", tags=["simulation"], summary="Get Conceptual Card Target")
def get_conceptual_card_endpoint(federation_id: str, db: Session = Depends(get_db)):
    """Get the conceptual/target card for the marquee show."""
    from agent_service.anchor_crud import get_conceptual_card
    conceptual = get_conceptual_card(db, federation_id)
    if conceptual is None:
        return {"federation_id": federation_id, "main_event_target": None, "title_matches_target": [], "planned_storyline_payoffs": []}
    return conceptual


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
    logger.info(f"Received request to update federation ID: {federation_id} with data: {update_data.model_dump(exclude_unset=True)}")

    # Add ownership check here in a real app

    try:
        updated_federation = crud.update_federation(db=db, federation_id=federation_id, update_data=update_data)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
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
    logger.debug(f"Action details: {action_response.model_dump()}")

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
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
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
    """Return engine and database status. Only available in debug mode."""
    # Check if debug mode is enabled via environment variable
    debug_enabled = os.getenv("DEBUG_MODE", "false").lower() == "true"
    
    if not debug_enabled:
        raise HTTPException(
            status_code=404,
            detail="Endpoint not found"
        )
    
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

# --- Wrestling (Titles, Storylines) ---

class TitleCreateData(BaseModel):
    federation_id: str
    name: str
    tier: str = "mid_card"
    prestige: int = 50

class StorylineCreateData(BaseModel):
    federation_id: str
    title: str
    participant_ids: Optional[List[str]] = None
    storyline_type: str = "feud"
    heat: int = 50

@app.get("/titles", tags=["wrestling"], summary="List Titles")
def list_titles(
    federation_id: Optional[str] = Query(None, description="Filter by federation"),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    """List titles, optionally filtered by federation."""
    try:
        from agent_service.wrestling_crud import get_titles
        titles = get_titles(db, federation_id=federation_id, skip=skip, limit=limit)
        return [
            {"title_id": t.title_id, "federation_id": t.federation_id, "name": t.name, "tier": t.tier, "prestige": t.prestige}
            for t in titles
        ]
    except Exception as e:
        logger.error(f"Failed to list titles: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/titles", tags=["wrestling"], summary="Create Title")
def create_title(data: TitleCreateData, db: Session = Depends(get_db)):
    """Create a new championship title."""
    try:
        from agent_service.wrestling_crud import create_title as crud_create_title
        title = crud_create_title(db, data.federation_id, data.name, data.tier, data.prestige)
        if not title:
            raise HTTPException(status_code=500, detail="Failed to create title")
        return {"title_id": title.title_id, "name": title.name, "tier": title.tier}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create title: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/titles/{title_id}", tags=["wrestling"], summary="Get Title")
def get_title(title_id: str, db: Session = Depends(get_db)):
    """Get title by ID."""
    try:
        from agent_service.wrestling_crud import get_title_by_id, get_current_champion
        title = get_title_by_id(db, title_id)
        if not title:
            raise HTTPException(status_code=404, detail="Title not found")
        champion_id = get_current_champion(db, title_id)
        return {
            "title_id": title.title_id,
            "federation_id": title.federation_id,
            "name": title.name,
            "tier": title.tier,
            "prestige": title.prestige,
            "current_champion_id": champion_id,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get title: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/titles/{title_id}/champion", tags=["wrestling"], summary="Get Current Champion")
def get_title_champion(title_id: str, db: Session = Depends(get_db)):
    """Get current champion (agent_id) for a title."""
    try:
        from agent_service.wrestling_crud import get_title_by_id, get_current_champion
        title = get_title_by_id(db, title_id)
        if not title:
            raise HTTPException(status_code=404, detail="Title not found")
        champion_id = get_current_champion(db, title_id)
        return {"title_id": title_id, "champion_id": champion_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get champion: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/storylines", tags=["wrestling"], summary="List Storylines")
def list_storylines(
    federation_id: Optional[str] = Query(None, description="Filter by federation"),
    status: Optional[str] = Query(None, description="Filter by status (active, resolved, dropped)"),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    """List storylines."""
    try:
        from agent_service.wrestling_crud import get_storylines
        storylines = get_storylines(db, federation_id=federation_id, status=status, skip=skip, limit=limit)
        return [
            {"storyline_id": s.storyline_id, "federation_id": s.federation_id, "title": s.title, "status": s.status, "heat": s.heat, "participant_ids": s.participant_ids}
            for s in storylines
        ]
    except Exception as e:
        logger.error(f"Failed to list storylines: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/storylines", tags=["wrestling"], summary="Create Storyline")
def create_storyline(data: StorylineCreateData, db: Session = Depends(get_db)):
    """Create a new storyline."""
    try:
        from agent_service.wrestling_crud import create_storyline as crud_create_storyline
        story = crud_create_storyline(
            db, data.federation_id, data.title,
            participant_ids=data.participant_ids,
            storyline_type=data.storyline_type,
            heat=data.heat,
        )
        if not story:
            raise HTTPException(status_code=500, detail="Failed to create storyline")
        return {"storyline_id": story.storyline_id, "title": story.title, "status": story.status}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create storyline: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/storylines/{storyline_id}", tags=["wrestling"], summary="Get Storyline")
def get_storyline(storyline_id: str, db: Session = Depends(get_db)):
    """Get storyline by ID."""
    try:
        from agent_service.wrestling_crud import get_storyline_by_id
        story = get_storyline_by_id(db, storyline_id)
        if not story:
            raise HTTPException(status_code=404, detail="Storyline not found")
        return {
            "storyline_id": story.storyline_id,
            "federation_id": story.federation_id,
            "title": story.title,
            "storyline_type": story.storyline_type,
            "participant_ids": story.participant_ids,
            "status": story.status,
            "heat": story.heat,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get storyline: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- Simulation (End-to-End) ---

@app.post("/simulation/run", tags=["simulation"], summary="Run End-to-End Simulation")
def run_simulation(
    max_ticks_per_match: int = Query(50, ge=1, le=500, description="Max ticks per match"),
    hints: Optional[dict] = None,
):
    """Run a demo card end-to-end: pre_match → match → post_match for each match. Updates records."""
    try:
        from simulation.orchestrator import SimulationOrchestrator, build_demo_card
        card = build_demo_card("demo-fed")
        orch = SimulationOrchestrator()
        results = orch.run_card(card, "demo-fed", max_ticks_per_match, hints or {})
        total_ticks = sum(len(r) for r in results)
        return {
            "message": "Simulation completed",
            "card": card.name,
            "matches": len(results),
            "total_tick_results": total_ticks,
        }
    except Exception as e:
        tb = traceback.format_exc()
        logger.error(f"Simulation failed: {e}\n{tb}")
        raise HTTPException(status_code=500, detail={"error": str(e), "trace": tb})


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

@app.get("/health", tags=["health"])
def health_check():
    """Enhanced health check endpoint."""
    from datetime import datetime, timezone
    return {
        "status": "ok",
        "version": "0.2.0",
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "database": "connected",
        "engine_initialized": True,
        "services": {
            "api": "up",
            "database": "connected",
            "engine": "initialized"
        }
    }

@app.get("/metrics", tags=["monitoring"], summary="Performance Metrics")
def get_performance_metrics():
    """
    Get performance metrics for API endpoints.
    
    Returns statistics about request counts, durations, and error rates.
    """
    from datetime import datetime, timezone
    metrics = performance_monitor.get_metrics()
    return {
        "endpoints": metrics,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    }

@app.post("/metrics/reset", tags=["monitoring"], summary="Reset Metrics")
def reset_performance_metrics():
    """
    Reset performance metrics.
    
    Clears all collected metrics. Useful for starting fresh monitoring periods.
    """
    performance_monitor.reset_metrics()
    return {"message": "Metrics reset successfully"}

# --- WebSocket (Phase 1.2) ---

@app.websocket("/live/federation/{federation_id}")
async def websocket_federation_live(websocket: WebSocket, federation_id: str):
    """WebSocket for federation live events."""
    from api_gateway.websocket import broadcaster
    await broadcaster.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await broadcaster.disconnect(websocket)


# --- Match Scheduler (Phase 2.2) ---

class ScheduleWeeklyRequest(BaseModel):
    federation_id: str
    name: str = "Weekly Show"
    card_type: str = "major_tv"
    title_id: Optional[str] = None

@app.post("/scheduling/weekly", tags=["simulation"], summary="Schedule Weekly Show")
def schedule_weekly_show(req: ScheduleWeeklyRequest):
    """Generate a match card for a weekly show (MatchScheduler)."""
    try:
        from core_engine.scheduling.match_scheduler import MatchScheduler
        from models.card_structure import CardType
        from simulation.card_builder import build_full_card
        ct = getattr(CardType, req.card_type.upper().replace("-", "_"), CardType.MAJOR_TV)
        sched = MatchScheduler()
        card = sched.schedule_weekly_show(federation_id=req.federation_id, name=req.name, card_type=ct, title_id=req.title_id)
        full = build_full_card(card, ct)
        return {
            "card_id": card.card_id,
            "name": card.name,
            "matches": [{"match_id": m.match_id, "participant_ids": m.participant_ids} for m in card.matches],
            "segments": len(full.segments),
        }
    except Exception as e:
        logger.error("Schedule failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# --- Agent Stats (Phase 3.3) ---

@app.get("/agents/{agent_id}/stats", tags=["wrestling"], summary="Get Agent Stats")
def get_agent_stats(agent_id: str, federation_id: Optional[str] = Query(None), db: Session = Depends(get_db)):
    """Get wrestler stats (wins, losses, win rate)."""
    try:
        from models.db_models import WrestlerStatsDB
        q = db.query(WrestlerStatsDB).filter(WrestlerStatsDB.agent_id == agent_id)
        if federation_id:
            q = q.filter(WrestlerStatsDB.federation_id == federation_id)
        row = q.first()
        if not row:
            return {"agent_id": agent_id, "wins": 0, "losses": 0, "total_matches": 0, "win_rate": 0.0}
        total = (row.total_matches or 0)
        wins = (row.wins or 0)
        return {
            "agent_id": agent_id,
            "wins": wins,
            "losses": row.losses or 0,
            "draws": row.draws or 0,
            "total_matches": total,
            "win_rate": round(wins / total, 2) if total > 0 else 0.0,
        }
    except Exception as e:
        logger.error("Get agent stats failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


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
