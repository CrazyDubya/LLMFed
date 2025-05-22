# Codebase Documentation: LLMFed API

This document provides an overview of the codebase structure, components, and functionalities of the LLMFed API project.

## Project Structure Overview

```
/Users/pup/LLMFed/
├── .DS_Store             # macOS metadata file
├── README.md             # Project overview and setup instructions
├── __pycache__/          # Python bytecode cache
├── agent_service/        # Handles agent/federation CRUD and business logic
│   ├── __init__.py
│   ├── __pycache__/
│   ├── crud.py
│   ├── database.py
│   └── models.py         # (Seems potentially redundant with top-level /models)
├── api_gateway/          # FastAPI application, endpoint definitions
│   ├── __init__.py
│   ├── __pycache__/
│   └── main.py
├── codebase.md           # This documentation file
├── codebase_template.md  # Original template file
├── config.py             # Configuration settings (currently database URL)
├── core_engine/          # Placeholder for core simulation logic
│   ├── __init__.py
│   ├── engine.py
│   ├── dispatcher.py
│   ├── rulebook.py
│   └── heat.py
├── llm_abstraction/      # Placeholder for LLM interaction layer
│   └── __init__.py
├── llmfed.db             # SQLite database file
├── models/               # Data models (Pydantic entities, SQLAlchemy DB models)
│   ├── __init__.py
│   ├── __pycache__/
│   ├── db_models.py
│   └── entities.py
└── requirements.txt      # Project dependencies
```

## File Descriptions

### `/Users/pup/LLMFed/api_gateway/main.py`

*   **Purpose:** Defines the FastAPI application, sets up middleware (like CORS), establishes database connections (via `Depends(get_db)`), and declares all the API endpoints for managing agents, federations, and handling agent actions.
*   **Key Functions/Classes:**
    *   `app`: The FastAPI application instance.
    *   `get_db()`: Dependency function to provide database sessions to endpoints.
    *   Endpoint Functions (e.g., `create_agent_endpoint`, `get_agent_endpoint`, `update_agent_endpoint`, `delete_agent_endpoint`, `list_agents_in_federation_endpoint`, `create_federation_endpoint`, `get_federation_endpoint`, `list_federations_endpoint`, `update_federation_endpoint`, `delete_federation_endpoint`, `submit_agent_action`).
*   **Dependencies:**
    *   External Libraries: `fastapi`, `uvicorn`, `sqlalchemy.orm.Session`.
    *   Local Modules: `agent_service.crud`, `agent_service.database` (specifically `get_db`), `models.entities` (Pydantic models), `models.db_models`.

### `/Users/pup/LLMFed/models/entities.py`

*   **Purpose:** Defines the Pydantic models used for data validation, serialization, and defining the structure of API request bodies and response payloads. These models represent the application-level view of the data.
*   **Key Functions/Classes:**
    *   `AgentConfig`: Nested model for LLM configuration within an Agent.
    *   `AgentCreateData`: Model for creating a new agent (input).
    *   `AgentUpdateData`: Model for partially updating an agent (input, allows optional fields).
    *   `Agent`: Model representing a full agent record (output).
    *   `FederationCreateData`: Model for creating a new federation (input).
    *   `FederationUpdateData`: Model for partially updating a federation (input).
    *   `Federation`: Model representing a full federation record (output).
    *   `PossibleAction`: Nested model representing a potential action an agent can take within an `EventContext`.
    *   `EventContext`: Model representing the situation/context provided TO an agent.
    *   `AgentActionResponse`: Model representing the action/response submitted BY an agent.
*   **Dependencies:**
    *   External Libraries: `pydantic`, `uuid`, `datetime`, `typing` (`List`, `Optional`, `Dict`, `Any`).
    *   Local Modules: None.

### `/Users/pup/LLMFed/models/db_models.py`

*   **Purpose:** Defines the SQLAlchemy models that map directly to database tables (specifically `agents` and `federations`). These models define the table structure, column types, relationships, and constraints for data persistence.
*   **Key Functions/Classes:**
    *   `Base`: Declarative base class for SQLAlchemy models.
    *   `AgentDB`: SQLAlchemy model for the `agents` table. Defines columns like `agent_id`, `user_id`, `name`, `role`, `llm_config` (JSON), `federation_id` (ForeignKey), etc., and establishes a relationship with `FederationDB`.
    *   `FederationDB`: SQLAlchemy model for the `federations` table. Defines columns like `federation_id`, `name`, `description`, `tier`, `owner_user_id`, etc., and establishes a one-to-many relationship back to `AgentDB`.
*   **Dependencies:**
    *   External Libraries: `sqlalchemy` (Column, String, Integer, DateTime, JSON, ForeignKey), `sqlalchemy.orm` (relationship, declarative_base), `datetime`.
    *   Local Modules: None (although `agent_service.database` imports `Base` for table creation).

### `/Users/pup/LLMFed/agent_service/crud.py`

*   **Purpose:** Contains the functions that implement the Create, Read, Update, and Delete (CRUD) operations for both Agents and Federations. This layer interacts directly with the database via SQLAlchemy sessions and models.
*   **Key Functions/Classes:**
    *   `create_agent`: Creates a new agent record in the DB.
    *   `get_agent_by_id`: Retrieves a single agent by its ID.
    *   `get_agents`: Retrieves a list of agents (with pagination).
    *   `update_agent`: Updates fields of an existing agent.
    *   `delete_agent`: Deletes an agent record.
    *   `get_agents_by_federation_id`: Retrieves all agents belonging to a specific federation.
    *   `create_federation`: Creates a new federation record.
    *   `get_federation_by_id`: Retrieves a single federation by its ID.
    *   `get_federations`: Retrieves a list of federations (with pagination).
    *   `update_federation`: Updates fields of an existing federation.
    *   `delete_federation`: Deletes a federation record (includes check for associated agents).
*   **Dependencies:**
    *   External Libraries: `sqlalchemy.orm.Session`, `sqlalchemy.exc.SQLAlchemyError`, `logging`, `uuid`, `datetime`, `json`.
    *   Local Modules: `models.db_models` (AgentDB, FederationDB), `models.entities` (AgentCreateData, AgentUpdateData, FederationCreateData, FederationUpdateData).

### `/Users/pup/LLMFed/agent_service/database.py`

*   **Purpose:** Handles the setup and configuration of the database connection using SQLAlchemy. It defines the database engine, the session maker, and provides a dependency function (`get_db`) for FastAPI endpoints to obtain a database session. It also includes a function to initialize the database by creating tables based on the defined SQLAlchemy models.
*   **Key Functions/Classes:**
    *   `DATABASE_URL`: Configuration string for the database connection (reads from env variable or defaults to SQLite).
    *   `engine`: The SQLAlchemy engine instance connected to the database.
    *   `SessionLocal`: A factory for creating new database session objects.
    *   `init_db()`: Function to create all database tables defined by models inheriting from `Base`.
    *   `get_db()`: A generator function used as a FastAPI dependency to provide a database session to endpoint functions, ensuring the session is closed afterwards.
*   **Dependencies:**
    *   External Libraries: `sqlalchemy` (create_engine), `sqlalchemy.orm` (sessionmaker, Session), `os`, `logging`.
    *   Local Modules: `models.db_models` (Base - imported implicitly via `crud` potentially, or needed explicitly for `init_db`).

### `/Users/pup/LLMFed/config.py`

*   **Purpose:** Centralizes configuration settings for the application. Currently, it primarily defines how to retrieve the database connection URL.
*   **Key Functions/Classes:**
    *   `get_database_url()`: Function that reads the `DATABASE_URL` environment variable or provides a default SQLite connection string.
*   **Dependencies:**
    *   External Libraries: `os`.
    *   Local Modules: None.

### `/Users/pup/LLMFed/core_engine/`

*   **Purpose:** Contains the core simulation engine logic for the wrestling federation, advancing match state, integrating LLM prompts, and managing game state heat.
*   **Key Files/Functions:**
    *   `engine.py`: Implements `Engine.run_ticks()` for tick-driven simulation, integrates `LLMClient`, `PromptBuilder`, and `RuleBook.validate`.
    *   `dispatcher.py`: Defines `LLMDispatcher` stub for placeholder action selection.
    *   `rulebook.py`: Static class `RuleBook` with `validate()` method to enforce simulation rules and return `AppliedAction`.
    *   `heat.py`: Functions for calculating and updating audience excitement (`calculate_match_heat`, `calculate_segment_heat`, `update_wrestler_heat`, `update_feud_heat`).
*   **Dependencies:**
    *   External Libraries: `uuid`, `logging`, `random`, `sqlalchemy`.
    *   Local Modules: `core_engine.llm_client`, `core_engine.prompt_builder`, `agent_service.crud`.

### `/Users/pup/LLMFed/llm_abstraction/`

*   **Purpose:** Intended placeholder directory for code related to interacting with different Large Language Models (LLMs), potentially providing a unified interface for the rest of the application. Currently contains only `__init__.py`.
*   **Dependencies:** N/A (Placeholder).

### `/Users/pup/LLMFed/llmfed.db`

*   **Purpose:** The actual SQLite database file where all agent and federation data is stored persistently. This file is managed by SQLAlchemy.
*   **Dependencies:** N/A (Data file).

### `/Users/pup/LLMFed/README.md`

*   **Purpose:** Provides a high-level overview of the LLMFed project, instructions for setting up the development environment, running the application, and potentially basic usage examples or API endpoint summaries.
*   **Key Contents:** (Based on typical README structure)
    *   Project Title/Description.
    *   Installation instructions (e.g., cloning, setting up virtual environment, `pip install -r requirements.txt`).
    *   Running the server (e.g., `uvicorn api_gateway.main:app --reload --port 8091`).
    *   Database setup/initialization notes.
    *   Basic API usage examples (e.g., using `curl`).
*   **Dependencies:** N/A (Informational file).

### `/Users/pup/LLMFed/requirements.txt`

*   **Purpose:** Lists the external Python packages required to run the LLMFed project, along with their specific versions (if specified). This file is used by `pip` to install dependencies.
*   **Key Contents:**
    *   `fastapi`: Web framework for building APIs.
    *   `uvicorn[standard]`: ASGI server to run FastAPI.
    *   `SQLAlchemy`: ORM toolkit for database interaction.
    *   `psycopg2-binary`: PostgreSQL database adapter (even though currently using SQLite, it's listed).
    *   `pydantic`: Data validation and settings management.
*   **Dependencies:** N/A (This file *defines* dependencies).

*(More files to be populated)*

---

## Game Engine (Design Blueprint)

### Guiding Principles
1. **Separation of concerns** – simulation, narrative, and LLM orchestration live in distinct layers.
2. **Tick-driven loop** – the engine advances in discrete ticks (configurable granularity).
3. **Async-friendly** – agent/LLM calls are queued; the engine resumes on response or timeout.
4. **Human override** – promoter guidance can be injected at any layer.

### Layer Overview
| Layer | Tick Frequency | Responsibilities |
|-------|----------------|-------------------|
| **State Core** | Every tick | Ground-truth data (`GameState`, `MatchState`). |
| **Simulation** | Every tick | Apply `AgentAction` → `AppliedAction` → state diff. |
| **Narrative** | Optional | Produce play-by-play or summaries. |
| **LLM Orchestrator** | When awaiting input | Build prompts, dispatch requests, validate replies. |
| **Scheduler** | Every tick | Decide whose turn / which mode (tick, rewrite, promo). |
| **I/O Queue** | N/A | Persist events, expose `/ticks` endpoint, store pending requests. |

### Core Pydantic Objects
```python
class TickResult(BaseModel):
    tick_id: str
    time_index: int
    applied_actions: list[AppliedAction]
    state_snapshot: dict[str, Any]

class EngineRequest(BaseModel):
    request_id: str
    agent_id: str
    due_tick: int
    context: EventContext  # from models.entities
```

### Event Flow per Tick
```
TickScheduler → LLMDispatcher (prompt, POST /agents/{id}/actions)
      ↑                                        ↓
StateCore ← SimulationLayer ← validated action
         ↓
    TickResult pushed to /ticks
```

### Narrative Modes
1. **Tick-by-Tick** – engine narrates small chunks.
2. **Rolling Rewrite** – competing LLMs rewrite segments; promoter picks winner.
3. **Full Rewrite** – agent submits full match script; engine enforces constraints.

### Planned FastAPI Endpoints
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/matches/{match_id}/ticks` | Stream/paginate `TickResult`s. |
| POST | `/engine/advance` | Run N ticks (admin). |
| POST | `/prompter/hints` | Promoter injects guidance blob. |

---

## Development Checklists

### Incremental Build
- [x] Create `core_engine/engine.py` skeleton
  - [x] `GameState` dataclass
  - [x] `TickScheduler` (simple round-robin)
  - [x] `run_ticks()` no-op loop
- [x] Wire FastAPI `/engine/advance` → `engine.run_ticks(1)`
- [x] Implement `RuleBook.validate()` → `AppliedAction`
- [x] Stub `LLMDispatcher` (random choice)
- [x] Produce first `TickResult` JSON
- [x] Add DB / queue persistence for `EngineRequest`

### Prompt-Building
- [x] Character sheet (gimmick, heat, momentum)
- [x] Available actions (from dispatcher)
- [x] Match context (opponent, stip, current spot)
- [x] Scheduler guidance (tick vs rewrite mode)
- [x] Promoter notes injection
- [x] JSON schema reminder for `AgentActionResponse`

### Documentation & Testing
- [x] Expand `codebase.md` as new modules appear
- [x] Unit tests: `RuleBook`, `TickScheduler`
- [x] Integration test: advance 10 ticks with stub LLM

---
