# LLMFed Reliability Refactoring Plan

## Part 1: Analysis — Current Code vs. The 10 Rules

### What's Good About the Code As It Is

1. **Modular separation of concerns** — The codebase is split into `core_engine/`, `api_gateway/`, `agent_service/`, `llm_abstraction/`, and `models/`. This is sound architecture. Each directory owns a single domain.

2. **Pydantic for validation** — Using Pydantic models for request/response contracts means input validation exists at API boundaries. The `models/entities.py` models with `Field(ge=, le=)` constraints provide some runtime assertion behavior (Rule 2).

3. **Error handler centralization** — `api_gateway/error_handlers.py` registers typed exception handlers (`APIError`, `ValidationError`, `SQLAlchemyError`, etc.) for consistent error responses. Return values from the DB layer are checked in endpoint code (Rule 4).

4. **Database session management** — The `get_db()` generator with `try/finally` ensures sessions are closed. CRUD functions catch `SQLAlchemyError` and call `db.rollback()` (Rule 8 — cleanup paths exist).

5. **Small utility modules** — `heat.py` (38 lines), `rulebook.py` (24 lines), `dispatcher.py` (28 lines), `prompt_builder.py` (50 lines) each do one thing. These already satisfy Rule 1 (short functions, single responsibility).

6. **LLM fallback chain** — `LLMClient.send_prompt()` and `LLMAbstraction._initialize_provider()` both implement fallback logic so the system degrades gracefully instead of crashing.

---

### What's Bad About the Code As It Is (by Rule)

#### Rule 1 — Keep functions short (~60 lines max, one thing per function)

| Violation | File:Line | Lines | Problem |
|-----------|-----------|-------|---------|
| `Engine.run_ticks()` | `core_engine/engine.py:152-245` | **93 lines** | Does 8+ things: iterates ticks, iterates roles, iterates agents, builds context, builds prompt, calls LLM, parses response, validates via rulebook, applies game-state mutations, persists to DB, checks for match-ending conditions, assembles results. This is the single worst function in the codebase. |
| `LLMClient.send_prompt()` | `core_engine/llm_client.py:41-104` | **64 lines** | Three distinct code paths (local proxy, OpenAI primary, dispatcher fallback) jammed into one method with nested try/except blocks. |
| `api_gateway/main.py` (file-level) | `api_gateway/main.py:1-575` | **575 lines** | All routes, middleware setup, config, and imports in one file. Not a single function issue per se, but the file itself violates the spirit of "one thing" — it's the entire API surface. |

#### Rule 2 — Assert liberally (pre/post-conditions, guards)

| Violation | Location | Problem |
|-----------|----------|---------|
| No parameter validation on `Engine.__init__()` | `engine.py:97` | No check that `init_db()` actually succeeded. |
| `run_ticks(n)` accepts any int | `engine.py:152` | `max(1, n)` silently clamps negative/zero to 1. The caller has no idea their input was ignored. Should assert `n >= 1` or raise. |
| `_parse_action_data()` swallows validation failures | `engine.py:145-147` | On `ValidationError`, logs and falls through to a generic noop extraction. The caller never knows validation failed — silent corruption. |
| `create_agent` in CRUD doesn't validate `role` | `crud.py:49` | The role string is passed straight to the DB with no check that it's one of the 6 valid roles. |
| `update_agent` applies arbitrary keys via `setattr` | `crud.py:107-108` | `for key, value in update_dict.items(): setattr(db_agent, key, value)` — no whitelist check. A Pydantic model with extra fields could write to any attribute on the ORM object. |
| `PromptBuilder.build_prompt()` | `prompt_builder.py:19` | No validation that `context.role` is a known role. Falls through to `AgentActionResponse` silently. |
| `LLMClient.send_prompt()` | `llm_client.py:41` | No validation that `prompt` is a non-empty dict. |

#### Rule 3 — Minimize variable scope

| Violation | Location | Problem |
|-----------|----------|---------|
| `engine_instance` singleton at module level | `engine.py:261` | Global mutable state. The Engine holds `GameState`, `promoter_hints`, and a DB session factory. Anyone importing the module mutates the same state. |
| `_default_llm` global | `provider.py:328` | Mutable module-level singleton with no thread safety. |
| `run_ticks()` local `db` | `engine.py:155` | The session lives for the entire method. Each agent-in-role iteration commits inside this long-lived session. Should be scoped tighter. |
| `crud.py` top-level `sys.path.append` | `crud.py:12` | Mutates global `sys.path` at import time as a side effect. |
| `main.py` triple `try/except ImportError` blocks | `main.py:21-56` | Each block mutates `sys.path` as a side effect with `project_root` recomputed 3 times. |

#### Rule 4 — Check all return values and validate all inputs

| Violation | Location | Problem |
|-----------|----------|---------|
| `init_db()` called in `Engine.__init__()` | `engine.py:104` | Return value (None) not checked. If init_db fails silently (which it shouldn't given retry + raise), the engine proceeds with no tables. |
| `db.commit()` unchecked inside `run_ticks()` | `engine.py:205, 231` | Two `db.commit()` calls inside the loop with no error handling. If either fails, the `finally: db.close()` will execute but partial state remains in the Engine object. |
| `json.loads(content)` in `LLMClient` | `llm_client.py:69, 84, 97` | Three separate `json.loads()` calls that can throw `json.JSONDecodeError`. Only the first (local proxy path) is wrapped in a try/except; the OpenAI path at line 84 is not. |
| CRUD functions return `None` on both "not found" and "DB error" | `crud.py` passim | The caller cannot distinguish "doesn't exist" from "database crashed." The API layer has to do a second query to differentiate (see `main.py:228`). |
| `action_data.get("heat_adjustment")` | `engine.py:221` | Reads from the raw LLM dict, not the validated model. If the LLM returns a string, `isinstance(adj, int)` silently skips it — no log, no error. |

#### Rule 5 — Compile clean; analyze clean (type safety, warnings)

| Violation | Location | Problem |
|-----------|----------|---------|
| `update_data.dict(exclude_unset=True)` | `main.py:213, 318` / `crud.py:101, 214` | Pydantic v2 deprecation: `.dict()` should be `.model_dump()`. These emit deprecation warnings now and will break on Pydantic v3. |
| Duplicate import `import sys, os` | `main.py:25, 36, 52` | Imported inside except blocks, shadowing the module-level `import os` on line 1 and 64. |
| Duplicate `import os` | `main.py:1, 64` | Direct duplicate. |
| `from typing import Dict, Any` imported twice | `prompt_builder.py:1, 13` | Exact duplicate import. |
| `AgentCreateData` missing fields used in CRUD | `entities.py:80-88` vs `crud.py:64-68` | CRUD accesses `agent_data.webhook_url`, `agent_data.current_heat`, `agent_data.momentum` — none of which exist on the Pydantic model. This will raise `AttributeError` at runtime. |
| `FederationCreateData` missing fields used in CRUD | `entities.py:117-123` vs `crud.py:179-180` | CRUD accesses `fed_data.max_agents`, `fed_data.is_active` — not defined on the Pydantic model. Same bug. |
| `AppliedAction` not imported in `rulebook.py` | `rulebook.py:17` | Uses `AppliedAction` in the return type annotation but imports it inside the function body. The type annotation references an undefined name at module load. |

#### Rule 6 — Prefer simple control flow

| Violation | Location | Problem |
|-----------|----------|---------|
| `run_ticks()` triple-nested loop | `engine.py:157-242` | `for _ in range(n)` → `for role in self.role_order` → `for agent_db in [filtered list]`. 3 levels deep with business logic, DB calls, and error handling all inside the innermost level. |
| `LLMClient.send_prompt()` branching | `llm_client.py:41-104` | `if force_remote` → try/except → try/except → try/except, then `if OPENAI_AVAILABLE` → try → nested `if "model_not_found"` → try. The control flow is a decision tree with 5+ leaves. |
| `main.py` import error handling | `main.py:21-56` | Three identical `try/except ImportError` blocks with path manipulation. This is conditional-import spaghetti. |

#### Rule 7 — Give every loop a reason to terminate (defensive bounds)

| Violation | Location | Problem |
|-----------|----------|---------|
| `run_ticks(n)` has no upper bound on `n` | `engine.py:152` | A caller can pass `n=1_000_000`. The loop will run until complete or until the machine runs out of resources. No defensive cap. |
| `init_db()` retry loop | `database.py:53` | `max_retries = 3` with `time.sleep(1)` — this is fine, but the sleep is unbounded if someone changes the constant. The bound is adequate for now. |
| `PerformanceMonitor.metrics` dict grows without bound | `logging_config.py:193` | Each unique `(method, path)` combo gets an entry. If path-parameter endpoints are hit with many distinct IDs, this dict will grow forever. No eviction policy. |

#### Rule 8 — Own your memory (clear cleanup paths)

| Violation | Location | Problem |
|-----------|----------|---------|
| `run_ticks()` DB session | `engine.py:155-245` | The `finally: db.close()` is correct, but if the early `return results` on line 234 fires, the session is still closed — good. However, there's no rollback on exception. If `db.commit()` on line 205 succeeds but `db.commit()` on line 231 fails, you have a half-committed tick. |
| `get_pending_requests()` | `engine.py:249-255` | Opens a new session, queries, closes. But the returned ORM objects are detached from the session after close. Accessing lazy-loaded relationships on them will crash. |
| `engine_instance` at module level | `engine.py:261` | Module-level singleton that calls `init_db()` at import time. This means importing the module has side effects (creates DB tables). |
| `database.py` calls `init_db()` at module level | `database.py:64` | Same issue — importing `agent_service.database` creates tables. Double initialization when both modules are imported. |

#### Rule 9 — Keep metaprogramming transparent

| Violation | Location | Problem |
|-----------|----------|---------|
| `setattr(db_agent, key, value)` in a loop | `crud.py:107-108` | Dynamic attribute assignment from a dict. A reader can't tell which attributes get set without tracing the Pydantic model's field list. |
| `schema_map.get()` with dynamic model selection | `prompt_builder.py:24-32` | Maps role strings to Pydantic model classes, then calls `.model_json_schema()`. The indirection is manageable but undocumented. |
| `SimpleNamespace` as a fake agent | `engine.py:163` | When no agents exist, a `SimpleNamespace` duck-types as an agent. This is fragile — if any downstream code calls a method on it or checks `isinstance`, it breaks silently. |

#### Rule 10 — Minimize indirection

| Violation | Location | Problem |
|-----------|----------|---------|
| Two LLM client abstractions | `core_engine/llm_client.py` + `llm_abstraction/provider.py` | Two completely separate LLM integration layers that don't reference each other. `LLMClient` is used by the engine; `LLMAbstraction` is a parallel unused (or underused) abstraction. A reader has to figure out which one is live. |
| `RuleBook.validate()` imports `AppliedAction` at call time | `rulebook.py:19` | Circular-import dodge. The function's return type is only knowable by reading the function body. |
| `LLMDispatcher` instantiated in two places | `engine.py:100`, `llm_client.py:102` | The engine creates one at init; the LLM client creates a new one on every fallback. Which one's state matters? |
| CRUD `None` return → API double-query pattern | `main.py:228-232` | Because CRUD returns None for both "not found" and "error," every update/delete endpoint queries twice to disambiguate. |

---

## Part 2: What Gets Better After Refactoring

1. **`run_ticks()` becomes readable and testable.** Breaking it into `_process_tick()`, `_process_agent_in_role()`, `_apply_game_effects()`, and `_persist_tick_result()` means each function is ~15-25 lines, does one thing, and can be unit-tested in isolation.

2. **Silent failures become loud failures.** Adding guard clauses (`if n < 1: raise ValueError`) and asserting post-conditions (`assert applied_action.action_id`) means bugs surface at their origin, not three layers downstream.

3. **The CRUD ambiguity disappears.** Returning typed results (a dataclass or raising specific exceptions for "not found" vs "DB error") eliminates the double-query pattern in API endpoints.

4. **One LLM abstraction instead of two.** Consolidating `llm_client.py` and `llm_abstraction/provider.py` into a single clean interface removes dead code and eliminates the "which one is real?" confusion.

5. **Import-time side effects vanish.** Moving `init_db()` out of module-level code and into an explicit startup function means importing a module doesn't mutate global state or create database tables.

6. **The `setattr` loop gets a whitelist.** Explicit allowed-field lists in CRUD updates prevent accidental attribute injection.

7. **DB sessions scope tightly.** Using per-operation sessions (or at least per-tick sessions) with proper rollback on any failure prevents half-committed states.

8. **`PerformanceMonitor` gets bounded.** Adding a max-entries cap or LRU eviction prevents unbounded memory growth.

9. **Type warnings vanish.** Replacing `.dict()` with `.model_dump()`, fixing duplicate imports, and adding missing fields to Pydantic models cleans up all static analysis warnings.

10. **Loop bounds become explicit.** `run_ticks()` gets a `MAX_TICKS_PER_CALL = 1000` cap. Every loop has a documented termination reason.

---

## Part 3: What Gets Worse After Refactoring

1. **More files, more function signatures to learn.** Breaking `run_ticks()` into 4-5 smaller functions means more indirection for a reader tracing a single tick's lifecycle. The tradeoff is that each piece is simpler, but the call graph is wider.

2. **Stricter validation may break existing callers.** If the API currently accepts malformed input silently (e.g., a `role` not in the valid set), adding assertions will return 400/422 errors to clients that were previously "working." This is net-positive but may require coordinated client updates.

3. **Consolidating LLM abstractions requires choosing one.** If any code depends on `llm_abstraction/provider.py`'s interface, the migration requires updating those call sites. The transition period has two valid interfaces briefly.

4. **Test coverage must grow.** Each new smaller function needs its own test cases. The current test suite (1,218 lines) will need expansion. This is pure cost with no user-visible feature benefit.

5. **The CRUD return-type change is a breaking internal API change.** Every endpoint that checks `if result is None` needs updating to catch specific exceptions instead.

---

## Part 4: Refactoring Plan — Step by Step

### Phase 1: Fix Bugs and Type Warnings (Rule 5)
*These are correctness issues, not style preferences.*

- [ ] **1.1** Add missing fields to `AgentCreateData`: `webhook_url`, `current_heat`, `momentum`
- [ ] **1.2** Add missing fields to `FederationCreateData`: `max_agents`, `is_active`
- [ ] **1.3** Replace all `.dict()` calls with `.model_dump()` (4 occurrences)
- [ ] **1.4** Remove duplicate `import os` in `main.py` (line 64)
- [ ] **1.5** Remove duplicate `from typing import Dict, Any` in `prompt_builder.py` (line 13)
- [ ] **1.6** Fix `json.loads()` in `LLMClient.send_prompt()` OpenAI path (line 84) — wrap in try/except
- [ ] **1.7** Eliminate triple `try/except ImportError` in `main.py` — use a single proper path setup

### Phase 2: Add Guards and Assertions (Rule 2, Rule 4)

- [ ] **2.1** `run_ticks(n)`: Replace `max(1, n)` with `if n < 1: raise ValueError("n must be >= 1")`
- [ ] **2.2** `_parse_action_data()`: On `ValidationError`, log at WARNING and include the role + agent_id for traceability
- [ ] **2.3** CRUD `update_agent` / `update_federation`: Add explicit allowed-field whitelist instead of blind `setattr` loop
- [ ] **2.4** `PromptBuilder.build_prompt()`: Assert `context.role in VALID_ROLES` at entry
- [ ] **2.5** `LLMClient.send_prompt()`: Assert `prompt` is a non-empty dict at entry
- [ ] **2.6** Add validation that `create_agent` role is one of the 6 valid roles

### Phase 3: Break Up Long Functions (Rule 1, Rule 6)

- [ ] **3.1** Extract `Engine._build_agent_context(agent_db, tick_index, role)` → returns `EventContext`
- [ ] **3.2** Extract `Engine._call_llm_for_agent(context, agent_id)` → returns `dict` (action data)
- [ ] **3.3** Extract `Engine._apply_game_effects(role, action_id, meta, applied_action)` → mutates `self.state`
- [ ] **3.4** Extract `Engine._persist_tick(db, request, context, agent_id, role, description, tick_id, tick_index)` → DB writes
- [ ] **3.5** Rewrite `run_ticks()` as a thin orchestrator calling the above 4 methods
- [ ] **3.6** Split `LLMClient.send_prompt()` into `_send_via_local_proxy()`, `_send_via_openai()`, `_fallback_stub()`
- [ ] **3.7** Split `api_gateway/main.py` into route modules: `routes/agents.py`, `routes/federations.py`, `routes/engine.py`, `routes/health.py`

### Phase 4: Scope and Lifetime Fixes (Rule 3, Rule 8)

- [ ] **4.1** Remove module-level `engine_instance` singleton. Provide a factory function `create_engine()` instead. Wire it into FastAPI's dependency injection via `app.state`.
- [ ] **4.2** Remove module-level `init_db()` call from `database.py:64`. Make it an explicit startup step in the app's lifespan handler.
- [ ] **4.3** In `run_ticks()`, scope DB session per-tick (not per-call). Wrap each tick in its own `try/except` with rollback.
- [ ] **4.4** Remove `_default_llm` global singleton from `provider.py`. Use dependency injection or explicit construction.
- [ ] **4.5** Eliminate `sys.path.append()` calls in `crud.py` and `database.py`. Fix the package structure with proper `__init__.py` files and a `pyproject.toml` or setup script.

### Phase 5: Eliminate Redundancy and Indirection (Rule 10)

- [ ] **5.1** Consolidate `core_engine/llm_client.py` and `llm_abstraction/provider.py` into a single LLM interface. Keep `LLMAbstraction` as the canonical client; retire `LLMClient`.
- [ ] **5.2** Move `AppliedAction` out of `engine.py` into `models/` to break the circular import in `rulebook.py`.
- [ ] **5.3** Replace `SimpleNamespace` fake agent with a proper `DefaultAgent` dataclass or just skip processing when no agents exist.
- [ ] **5.4** Unify CRUD error signaling: raise `NotFoundError` / `DatabaseError` instead of returning `None`/`False`. Remove double-query pattern from API endpoints.
- [ ] **5.5** Remove the second `LLMDispatcher()` instantiation in `llm_client.py:102` — use the one from `Engine`.

### Phase 6: Loop Safety and Bounds (Rule 7)

- [ ] **6.1** Add `MAX_TICKS_PER_CALL = 1000` constant; assert `n <= MAX_TICKS_PER_CALL` in `run_ticks()`
- [ ] **6.2** Add `MAX_ENDPOINTS = 10_000` cap to `PerformanceMonitor.metrics`. When exceeded, stop recording new endpoints (or evict oldest).
- [ ] **6.3** Document termination reasoning for each loop (inline comments on the `for` line)

### Phase 7: Tests and Verification

- [ ] **7.1** Add unit tests for each extracted method from Phase 3
- [ ] **7.2** Add tests that verify guard clauses raise on bad input (Phase 2)
- [ ] **7.3** Add tests for CRUD exception-raising behavior (Phase 5.4)
- [ ] **7.4** Run full test suite, fix any regressions
- [ ] **7.5** Run a linter (ruff/flake8) and type checker (mypy) to verify Rule 5 compliance
