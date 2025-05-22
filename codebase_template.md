# Codebase Documentation: LLMFed

This document provides an overview of the codebase structure, components, and functionalities of the LLMFed project.

## Project Structure Overview

```
/Users/pup/LLMFed/
├── api_gateway/          # FastAPI server for API endpoints
│   └── main.py
├── core_engine/          # Simulation engine core logic
│   ├── engine.py
│   ├── dispatcher.py
│   ├── rulebook.py
│   ├── heat.py
│   ├── prompt_builder.py
│   └── llm_client.py
├── agent_service/        # DB setup and CRUD operations
│   ├── database.py
│   └── crud.py
├── models/               # Pydantic schemas and SQLAlchemy models
│   ├── db_models.py
│   └── entities.py
├── config.py             # Configuration (DATABASE_URL, etc.)
├── demo.py               # Single-tick demo script
├── demo_multi.py         # Multi-agent, multi-role demo script
└── codebase.md           # Project documentation
```

## File Descriptions

### `/Users/pup/LLMFed/api_gateway/main.py`

*   **Purpose:** Defines the FastAPI app, endpoint routes for agents, federations, and engine control.
*   **Key Functions:**
    *   `create_agent_endpoint`, `get_agent_by_id`, `update_agent`, `delete_agent`
    *   `/engine/advance`, `/engine/requests`, `/engine/debug`, `/health`
*   **Dependencies:**
    *   Standard Libraries: `fastapi`, `uvicorn`.
    *   Local Modules: Imports from `core_engine` (for engine control), `agent_service` (for CRUD operations), `models` (for Pydantic schemas).

### `/Users/pup/LLMFed/core_engine/engine.py`

*   **Purpose:** Core simulation engine; manages game state, tick scheduling, and persistence of engine requests.
*   **Key Classes/Functions:**
    *   `Engine`, `run_ticks`, `get_pending_requests`, `AppliedAction`, `TickResult`, `GameState`, `TickScheduler`
*   **Dependencies:**
    *   Standard Libraries: `datetime`, `logging`.
    *   Local Modules: Imports from `dispatcher` (for action selection), `rulebook` (for rule validation), `models` (for game state representation).
*   **GameState** extended with `heat` and `momentum`; `snapshot()` returns `{current_tick, heat, momentum}`.
*   **Multi-role scheduling**: `Engine.role_order = ["promoter","participant","referee","crowd","announcer","backstage"]`.
*   **run_ticks** loops each tick over roles then agents of that role, building `EventContext(role=…)` and collecting `TickResult(agent_id, role, …)`.
*   After **crowd** responses, adjusts `GameState.heat` by `heat_adjustment`.

### `/Users/pup/LLMFed/core_engine/dispatcher.py`

*   **Purpose:** Stub LLMDispatcher that selects actions for agents (random choice placeholder).
*   **Key Functions:**
    *   `select_action`
*   **Dependencies:**
    *   Standard Libraries: `random`.
    *   Local Modules: None.

### `/Users/pup/LLMFed/core_engine/rulebook.py`

*   **Purpose:** Static rules for validating actions and converting them to `AppliedAction`.
*   **Key Functions:**
    *   `validate_action`, `convert_to_applied_action`
*   **Dependencies:**
    *   Standard Libraries: None.
    *   Local Modules: None.

### `/Users/pup/LLMFed/core_engine/heat.py`

*   **Purpose:** Functions and logic to calculate and manage “heat” (audience excitement) within matches, segments, wrestlers, and feuds.
*   **Key Functions:**
    *   `calculate_match_heat(match: dict) -> int`
    *   `calculate_segment_heat(segment: dict) -> int`
    *   `update_wrestler_heat(wrestler, heat_change: int) -> int`
    *   `update_feud_heat(feud: dict, heat_change: int) -> int`
*   **Dependencies:**
    *   Standard Libraries: None.
    *   Local Modules: None.

### `/Users/pup/LLMFed/core_engine/prompt_builder.py`

*   **Purpose:** Constructs JSON payloads combining event context—including available actions, game state (gimmick, heat, momentum), match context, and promoter hints.
*   **Key Functions:** `build_prompt`
*   **Dependencies:** `models.entities`, `typing`

### `/Users/pup/LLMFed/core_engine/llm_client.py`

*   **Purpose:** Client wrapper for LLM API calls with local proxy support and fallback stub mode.
*   **Key Functions:** `send_prompt`
*   **Dependencies:** `httpx`, `openai` (optional), `json`, `logging`

### `/Users/pup/LLMFed/agent_service/database.py`

*   **Purpose:** SQLAlchemy database setup; provides `SessionLocal` and `init_db` for SQLite backend.
*   **Key Functions:** `init_db`, `SessionLocal`
*   **Dependencies:** `sqlalchemy`

### `/Users/pup/LLMFed/agent_service/crud.py`

*   **Purpose:** CRUD operations for agents and federations in the database.
*   **Key Functions:** `create_agent`, `get_agents`, `get_agent_by_id`, `update_agent`, `delete_agent`
*   **Dependencies:** `models.db_models`, `database.SessionLocal`

### `/Users/pup/LLMFed/models/db_models.py`

*   **Purpose:** SQLAlchemy ORM models defining database tables for agents, federations, engine requests, and narrative logs.
*   **Key Classes:** `AgentDB`, `FederationDB`, `EngineRequestDB`, `NarrativeLogDB`
*   **Dependencies:** `sqlalchemy`, `Base`

### `/Users/pup/LLMFed/models/entities.py`

*   **Purpose:** Pydantic schemas for API requests/responses and engine data models.
*   **Key Classes:** `User`, `AgentConfig`, `Agent`, `Federation`, `PossibleAction`, `EventContext`, `AgentActionResponse`, role-specific response models.
*   **Dependencies:** `pydantic`, `typing`, `uuid`, `datetime`

### `/Users/pup/LLMFed/config.py`

*   **Purpose:** Load environment-based configuration (`DATABASE_URL`, `OPENAI_MODEL`, `OPENAI_API_BASE`).
*   **Key Functions:** attribute definitions from `os.getenv`
*   **Dependencies:** `os`

### `/Users/pup/LLMFed/demo.py`

*   **Purpose:** Run a single engine tick and print results for manual testing.
*   **Key Functions:** invokes `engine_instance.run_ticks(1)`
*   **Dependencies:** `core_engine.engine`, `json`

### `/Users/pup/LLMFed/demo_multi.py`

*   **Purpose:** Multi-agent, multi-role simulation demo; reads `OPENAI_MODEL` and `OPENAI_API_BASE` for LLM integration.
*   **Key Functions:** sets up environment, runs `run_ticks` with multiple ticks
*   **Dependencies:** `os`, `core_engine.engine`

### `/Users/pup/LLMFed/codebase.md`

*   **Purpose:** Project documentation and development roadmap.
*   **Contents:** Overview, module descriptions, testing guide, deployment instructions.
