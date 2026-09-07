from fastapi_cache.decorator import cache
from sqlalchemy.future import select

"""
Core API routes extracted from main.py.

Handles agents, federations, engine control, scheduler, and monitoring
endpoints that were previously defined inline in the FastAPI app module.
"""

import logging
import os
from typing import List

from dataclasses import asdict
from fastapi import APIRouter, HTTPException, Depends, Query, Request
from api_gateway.dependencies import get_engine_dependency
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from models.entities import (
    Agent,
    AgentCreateData,
    AgentUpdateData,
    Federation,
    FederationCreateData,
    FederationUpdateData,
    AgentActionResponse,
    PrompterHintRequest,
)
from models.db_models import EngineRequestDB, NarrativeLogDB
from agent_service import crud
from agent_service.database import get_db

from core_engine.prompt_builder import PromptBuilder
from api_gateway.logging_config import performance_monitor

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Agent Management
# ---------------------------------------------------------------------------


@router.post(
    "/agents",
    summary="Create Agent",
    response_model=Agent,
    status_code=201,
    tags=["agents"],
)
async def create_agent_endpoint(
    request: Request, agent_data: AgentCreateData, db: AsyncSession = Depends(get_db)
):
    """Creates a new LLM agent in the database."""
    logger.info(f"Received request to create agent for user: {agent_data.user_id}")
    try:
        from models.entities import AgentConfig

        AgentConfig(**agent_data.llm_config)
    except Exception as e:
        logger.error(f"LLM Config validation error: {e}")
        raise HTTPException(status_code=422, detail=f"Invalid llm_config format: {e}")

    try:
        db_agent = await crud.create_agent(db=db, agent_data=agent_data)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return db_agent


@router.get(
    "/agents/{agent_id}",
    summary="Get Agent by ID",
    response_model=Agent,
    tags=["agents"],
)
async def get_agent_endpoint(agent_id: str, db: AsyncSession = Depends(get_db)):
    """Retrieves details for a specific agent by their ID."""
    db_agent = await crud.get_agent_by_id(db=db, agent_id=agent_id)
    if db_agent is None:
        raise HTTPException(
            status_code=404, detail=f"Agent with ID '{agent_id}' not found."
        )
    return db_agent


@router.patch(
    "/agents/{agent_id}", summary="Update Agent", response_model=Agent, tags=["agents"]
)
async def update_agent_endpoint(
    agent_id: str, update_data: AgentUpdateData, db: AsyncSession = Depends(get_db)
):
    """Updates specific fields of an existing agent."""
    if update_data.llm_config is not None:
        try:
            from models.entities import AgentConfig

            AgentConfig(**update_data.llm_config)
        except Exception as e:
            raise HTTPException(
                status_code=422, detail=f"Invalid llm_config format: {e}"
            )

    try:
        updated_agent = await crud.update_agent(
            db=db, agent_id=agent_id, update_data=update_data
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if updated_agent is None:
        raise HTTPException(
            status_code=404, detail=f"Agent with ID '{agent_id}' not found."
        )
    return updated_agent


@router.delete(
    "/agents/{agent_id}", summary="Delete Agent", status_code=204, tags=["agents"]
)
async def delete_agent_endpoint(agent_id: str, db: AsyncSession = Depends(get_db)):
    """Deletes an agent from the database."""
    existing_agent = await crud.get_agent_by_id(db=db, agent_id=agent_id)
    if not existing_agent:
        raise HTTPException(
            status_code=404, detail=f"Agent with ID '{agent_id}' not found."
        )
    await crud.delete_agent(db=db, agent_id=agent_id)
    return None


# ---------------------------------------------------------------------------
# Federation Management
# ---------------------------------------------------------------------------


@router.get(
    "/federations",
    summary="List All Federations",
    response_model=List[Federation],
    tags=["federations"],
)
@cache(expire=60)
async def list_federations_endpoint(
    skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)
):
    """Retrieves a list of all federations, with optional pagination."""
    return await crud.get_federations(db=db, skip=skip, limit=limit)


@router.post(
    "/federations",
    summary="Create Federation",
    response_model=Federation,
    status_code=201,
    tags=["federations"],
)
async def create_federation_endpoint(
    fed_data: FederationCreateData, db: AsyncSession = Depends(get_db)
):
    """Creates a new Wrestling Federation."""
    try:
        db_federation = await crud.create_federation(db=db, fed_data=fed_data)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return db_federation


@router.get(
    "/federations/{federation_id}",
    summary="Get Federation by ID",
    response_model=Federation,
    tags=["federations"],
)
async def get_federation_endpoint(
    federation_id: str, db: AsyncSession = Depends(get_db)
):
    """Retrieves details for a specific federation by its ID."""
    db_federation = await crud.get_federation_by_id(db=db, federation_id=federation_id)
    if db_federation is None:
        raise HTTPException(
            status_code=404, detail=f"Federation with ID '{federation_id}' not found."
        )
    return db_federation


@router.get(
    "/federations/{federation_id}/agents",
    summary="List Agents in Federation",
    response_model=List[Agent],
    tags=["federations"],
)
def list_agents_in_federation_endpoint(
    federation_id: str, db: AsyncSession = Depends(get_db)
):
    """Retrieves all agents belonging to a specific federation."""
    db_federation = await crud.get_federation_by_id(db=db, federation_id=federation_id)
    if db_federation is None:
        raise HTTPException(
            status_code=404, detail=f"Federation with ID '{federation_id}' not found."
        )
    return await crud.get_agents_by_federation_id(db=db, federation_id=federation_id)


@router.patch(
    "/federations/{federation_id}",
    summary="Update Federation",
    response_model=Federation,
    tags=["federations"],
)
async def update_federation_endpoint(
    federation_id: str,
    update_data: FederationUpdateData,
    db: AsyncSession = Depends(get_db),
):
    """Updates specific fields of an existing federation."""
    try:
        updated_federation = await crud.update_federation(
            db=db, federation_id=federation_id, update_data=update_data
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if updated_federation is None:
        raise HTTPException(
            status_code=404, detail=f"Federation with ID '{federation_id}' not found."
        )
    return updated_federation


@router.delete(
    "/federations/{federation_id}",
    summary="Delete Federation",
    status_code=204,
    tags=["federations"],
)
async def delete_federation_endpoint(
    federation_id: str, db: AsyncSession = Depends(get_db)
):
    """Deletes a federation. Requires the federation to be empty of agents."""
    existing = await crud.get_federation_by_id(db=db, federation_id=federation_id)
    if not existing:
        raise HTTPException(
            status_code=404, detail=f"Federation with ID '{federation_id}' not found."
        )

    deleted = await crud.delete_federation(db=db, federation_id=federation_id)
    if not deleted:
        agents = await crud.get_agents_by_federation_id(db, federation_id)
        if agents:
            raise HTTPException(
                status_code=409,
                detail=f"Federation {federation_id} cannot be deleted because it still contains agents.",
            )
        raise HTTPException(
            status_code=500, detail="Failed to delete federation from database."
        )
    return None


# ---------------------------------------------------------------------------
# Agent Interaction
# ---------------------------------------------------------------------------


@router.post(
    "/agents/{agent_id}/actions",
    summary="Submit Agent Action",
    status_code=202,
    tags=["agents"],
)
async def submit_agent_action(
    agent_id: str,
    action_response: AgentActionResponse,
    db: AsyncSession = Depends(get_db),
):
    """Endpoint for an agent to submit its chosen action in response to an event."""
    db_agent = await crud.get_agent_by_id(db=db, agent_id=agent_id)
    if not db_agent:
        raise HTTPException(
            status_code=404, detail=f"Agent with ID '{agent_id}' not found."
        )

    if action_response.target_agent_id:
        db_target = await crud.get_agent_by_id(
            db=db, agent_id=action_response.target_agent_id
        )
        if not db_target:
            raise HTTPException(
                status_code=404,
                detail=f"Target agent with ID '{action_response.target_agent_id}' not found.",
            )

    return {
        "message": "Action received and accepted for processing.",
        "event_id": action_response.event_id,
        "chosen_action": action_response.chosen_action_id,
    }


@router.post(
    "/agents/{agent_id}/subscribe", summary="Subscribe Agent to Events", tags=["agents"]
)
async def subscribe_agent(
    agent_id: str, webhook_url: str = Query(...), db: AsyncSession = Depends(get_db)
):
    db_agent = await crud.get_agent_by_id(db=db, agent_id=agent_id)
    if not db_agent:
        raise HTTPException(
            status_code=404, detail=f"Agent with ID '{agent_id}' not found."
        )
    return {
        "message": f"Subscription request for agent {agent_id} to URL: {webhook_url} (DB update TBD)"
    }


@router.post(
    "/federations/{federation_id}/subscribe",
    summary="Subscribe to Federation Events",
    tags=["federations"],
)
async def subscribe_federation(
    federation_id: str,
    webhook_url: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    db_federation = await crud.get_federation_by_id(db=db, federation_id=federation_id)
    if not db_federation:
        raise HTTPException(
            status_code=404, detail=f"Federation with ID '{federation_id}' not found."
        )
    return {
        "message": f"Subscription request for federation {federation_id} to URL: {webhook_url} (DB update TBD)"
    }


# ---------------------------------------------------------------------------
# Engine Control
# ---------------------------------------------------------------------------


@router.post("/engine/advance", summary="Advance Simulation Ticks", tags=["engine"])
async def advance_engine(
    n_ticks: int = Query(1, ge=1, description="Number of ticks to advance"),
    engine=Depends(get_engine_dependency),
):
    """Advance the core engine by n_ticks ticks."""
    try:
        results = await engine.run_ticks(n_ticks)
        return [asdict(r) for r in results]
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to advance engine: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/engine/requests", summary="List Engine Requests", tags=["engine"])
async def list_engine_requests(limit: int = 10, db: AsyncSession = Depends(get_db)):
    """Show persisted engine requests."""
    requests = (
        await db.execute(select(EngineRequestDB))
        .order_by(EngineRequestDB.due_tick.desc())
        .limit(limit)
        .scalars()
        .all()
    )
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


@router.get("/engine/narrative", summary="List Narrative Logs", tags=["engine"])
async def list_narrative_logs(
    limit: int = Query(100, ge=1, le=1000), db: AsyncSession = Depends(get_db)
):
    """Retrieve recent narrative log entries."""
    logs = (
        await db.execute(select(NarrativeLogDB))
        .order_by(NarrativeLogDB.created_at.desc())
        .limit(limit)
        .scalars()
        .all()
    )
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


@router.get("/engine/debug", summary="Engine Debug Info", tags=["engine"])
async def engine_debug():
    """Return engine and database status. Only available in debug mode."""
    debug_enabled = os.getenv("DEBUG_MODE", "false").lower() == "true"
    if not debug_enabled:
        raise HTTPException(status_code=404, detail="Endpoint not found")

    from agent_service.database import engine as db_engine
    from sqlalchemy import inspect

    eng = engine
    inspector = inspect(db_engine)
    return {
        "tables": inspector.get_table_names(),
        "engine_state": {
            "current_tick": eng.state.current_tick,
            "pending_requests": len(eng.get_pending_requests()),
        },
    }


@router.post("/prompter/hints", summary="Prompter Hints", tags=["engine"])
async def prompter_hints(request: PrompterHintRequest):
    """Accepts promoter hints, stores them, and builds LLM prompt."""
    eng = engine
    eng.set_hints(request.hints)
    prompt = PromptBuilder.build_prompt(request.context, request.hints)
    return prompt


# ---------------------------------------------------------------------------
# Monitoring & Health
# ---------------------------------------------------------------------------


@router.get("/health", tags=["health"])
async def health_check():
    """Enhanced health check endpoint."""
    from datetime import datetime, timezone

    return {
        "status": "ok",
        "version": "0.2.0",
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "database": "connected",
        "engine_initialized": True,
        "services": {"api": "up", "database": "connected", "engine": "initialized"},
    }


@router.get("/metrics", tags=["monitoring"], summary="Performance Metrics")
async def get_performance_metrics():
    """Get performance metrics for API endpoints."""
    from datetime import datetime, timezone

    return {
        "endpoints": performance_monitor.get_metrics(),
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }


@router.post("/metrics/reset", tags=["monitoring"], summary="Reset Metrics")
async def reset_performance_metrics():
    """Reset performance metrics."""
    performance_monitor.reset_metrics()
    return {"message": "Metrics reset successfully"}


@router.get(
    "/api/tags", summary="List available LLM models from proxy", tags=["engine"]
)
async def list_proxy_models():
    """Fetch model IDs from the local LLM proxy."""
    base = os.getenv("OPENAI_API_BASE", "http://127.0.0.1:11434/v1")
    url = f"{base.rstrip('/')}/models"
    try:
        import httpx

        resp = httpx.get(url)
        resp.raise_for_status()
        return [m.get("id") for m in resp.json().get("data", [])]
    except Exception as e:
        logger.error(f"Error fetching models from {url}: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching models: {e}")


# ---------------------------------------------------------------------------
# Auto-Scheduler
# ---------------------------------------------------------------------------


class SchedulerConfig(BaseModel):
    interval_seconds: float = 60.0


@router.get("/scheduler/status", summary="Get auto-scheduler status", tags=["engine"])
async def scheduler_status():
    from game_service.auto_scheduler import scheduler as auto_scheduler

    return auto_scheduler.status()


@router.post("/scheduler/start", summary="Start auto-scheduler", tags=["engine"])
async def scheduler_start(config: SchedulerConfig = SchedulerConfig()):
    from game_service.auto_scheduler import scheduler as auto_scheduler

    await auto_scheduler.start(interval_seconds=config.interval_seconds)
    return auto_scheduler.status()


@router.post("/scheduler/stop", summary="Stop auto-scheduler", tags=["engine"])
async def scheduler_stop():
    from game_service.auto_scheduler import scheduler as auto_scheduler

    await auto_scheduler.stop()
    return auto_scheduler.status()


@router.post("/scheduler/interval", summary="Change tick interval", tags=["engine"])
async def scheduler_set_interval(config: SchedulerConfig):
    from game_service.auto_scheduler import scheduler as auto_scheduler

    auto_scheduler.set_interval(config.interval_seconds)
    return auto_scheduler.status()


@router.post("/scheduler/pause/{world_id}", summary="Pause a world", tags=["engine"])
async def scheduler_pause_world(world_id: str):
    from game_service.auto_scheduler import scheduler as auto_scheduler

    auto_scheduler.pause_world(world_id)
    return {"paused": world_id}


@router.post("/scheduler/resume/{world_id}", summary="Resume a world", tags=["engine"])
async def scheduler_resume_world(world_id: str):
    from game_service.auto_scheduler import scheduler as auto_scheduler

    auto_scheduler.resume_world(world_id)
    return {"resumed": world_id}


# ---------------------------------------------------------------------------
# Public shows (no auth required)
# ---------------------------------------------------------------------------


@router.get(
    "/worlds/{world_id}/shows", summary="List all shows in a world", tags=["engine"]
)
async def list_world_shows(
    world_id: str,
    limit: int = Query(50, ge=1, le=200),
    completed_only: bool = False,
    db: AsyncSession = Depends(get_db),
):
    """List all shows across all federations in a world."""
    from models.game_models import ShowDB, GameFederationDB

    query = db.query(ShowDB).filter(ShowDB.world_id == world_id)
    if completed_only:
        query = query.filter(ShowDB.is_completed == True)  # noqa: E712
    shows = query.order_by(ShowDB.game_date.desc()).limit(limit).scalars().all()

    results = []
    for show in shows:
        fed = (
            db.query(GameFederationDB)
            .filter(GameFederationDB.id == show.federation_id)
            .first()
        )
        results.append(
            {
                "id": show.id,
                "name": show.name,
                "show_type": show.show_type,
                "venue": show.venue,
                "capacity": show.capacity,
                "attendance": show.attendance,
                "game_date": show.game_date,
                "is_completed": show.is_completed,
                "overall_rating": show.overall_rating,
                "tv_rating": show.tv_rating,
                "gate_revenue": show.gate_revenue,
                "ppv_buys": show.ppv_buys,
                "federation_id": show.federation_id,
                "federation_name": fed.name if fed else "Unknown",
            }
        )
    return results
