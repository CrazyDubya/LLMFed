# Repository Guidelines

## Project Structure & Module Organization

- `api_gateway/` – FastAPI REST API, endpoints, middleware, error handlers.
- `core_engine/` – Tick-based simulation engine, scheduler, dispatcher, rulebook, heat system, LLM client, prompt builder.
- `agent_service/` – CRUD for agents and federations, database session management.
- `llm_abstraction/` – Multi-provider LLM interface (OpenAI, Ollama, custom).
- `models/` – Pydantic entities and SQLAlchemy DB models.
- `frontend/` – Static single-page UI (`index.html`); serve with any static file server.
- `docs/` – Long-form documentation (usage guide, analysis, roadmap, codebase, security, etc.).
- `scripts/` – Demo and helper scripts (e.g. `demo.py`, `demo_multi.py`).
- `tests/` – Pytest suite (validation, security, engine, CRUD, LLM, heat, etc.).
- `config.py` – Environment-based config (database URL, API host/port, etc.).

## Build, Test, and Development Commands

Run from the repository root. Prefer an editable install so imports resolve from any working directory:

```bash
pip install -e .
# or: pip install -r requirements.txt  (then run from repo root)
```

**Backend (FastAPI)**

```bash
uvicorn api_gateway.main:app --host 0.0.0.0 --port 8091 --reload
```

Or with `uv`:

```bash
uv run uvicorn api_gateway.main:app --host 0.0.0.0 --port 8091 --reload
```

**Database init**

```bash
python -c "from agent_service.database import init_db; init_db()"
```

**Frontend**

Static only. From `frontend/`:

```bash
python -m http.server 8080
```

Then open http://localhost:8080 (or use any static server).

**Demo** (from repo root)

```bash
python scripts/demo.py
```

**Tests**

```bash
python -m pytest tests/ -v
```

## Coding Style & Naming Conventions

- Python: 4-space indentation, type hints preferred. Snake_case for modules and functions. Keep FastAPI routers lean; put helpers in `api_gateway/` or relevant packages.
- Commit messages: concise summary; emoji optional (e.g. `🎉 Release: ...`).

## Testing Guidelines

- Backend: hit critical endpoints (e.g. `/health`, `/agents`, `/engine/advance`) via curl or the frontend. Run strategy/engine logic via API or scripts before merge.
- Frontend: manual verification (create agents, advance engine, check narrative). No automated frontend test suite yet; document manual checks in PRs.

## Commit & Pull Request Guidelines

- Commits: focused; describe feature and scope (e.g. `🚀 UI: council presets + streaming fixes`).
- PRs: summary, screenshots for UI changes, reproduction steps. Note backend or dependency changes (e.g. `pip install -e .`, `uv sync`). Update DEVLOG.md for notable changes between commits.

## Architectural Guidelines for Future Agents

When building features or refactoring the LLMFed codebase, adhere to the following architectural principles:

1. **Strict Dependency Injection:**
   - Avoid global singletons (e.g., `get_engine()`, `get_llm()`).
   - Use FastAPI's `Depends()` for all service, repository, and database dependencies in route handlers.
   - Inject dependencies into class constructors rather than importing global instances.

2. **Asynchronous First:**
   - New endpoints, database operations, and network calls (especially LLM requests) must be fully asynchronous.
   - Use `async def` for FastAPI routes.
   - Use `sqlalchemy.ext.asyncio` for database queries.
   - Use asynchronous HTTP clients (e.g., `httpx` or `aiohttp`) for external API integrations.

3. **Separation of Concerns & Event Sourcing:**
   - The Core Engine should not interact directly with SQLAlchemy models or manage database commits.
   - The Engine should yield pure domain events or state changes.
   - A distinct Repository layer should subscribe to these events and handle persistence asynchronously.

4. **Strict Typing and Validation:**
   - Use Pydantic models for all data crossing boundaries (e.g., Engine to LLM, API to Engine).
   - Do not pass raw `dict` objects. Define explicit `ActionRequest` and `ActionResponse` models.

5. **Robust Error Handling:**
   - Do not catch generic `Exception`.
   - Use the custom exception hierarchy in `core_engine/exceptions.py` (e.g., `LLMNetworkError`, `GameLogicError`, `LLMFormatError`).
   - Map domain exceptions to appropriate HTTP status codes in the FastAPI exception handlers.

6. **Observability and Performance:**
   - Avoid custom performance tracking dictionaries. Instead, integrate and use OpenTelemetry for metrics and tracing.
   - Utilize Redis (via `fastapi-cache2`) for caching read-heavy or frequently generated static data (like prompts or static configurations).

7. **Prompt Engineering:**
   - Use Jinja2 templates for constructing LLM prompts instead of Python string formatting. Keep prompt logic declarative and separate from business logic.
