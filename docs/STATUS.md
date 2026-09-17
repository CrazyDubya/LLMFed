# LLMFed Documentation and Project Status

**Status date:** 2026-09-17

This is the current source of truth for project status. Older review reports and implementation summaries remain useful historical context, but their metrics, file lists, estimates, and completion claims should not be treated as current unless they are confirmed here or in the code.

## What is currently present

- Python 3.10+ backend packaged through `pyproject.toml`.
- FastAPI API gateway with separate route modules, WebSocket wiring, CORS, trusted-host middleware, security headers, rate limiting, error handling, logging, metrics, and OpenAPI metadata.
- SQLAlchemy models and services for the current wrestling-world domain, including users, players, worlds, federations, wrestlers, contracts, championships, shows, storylines, and narrative history.
- Tick-based simulation and wrestling lifecycle services.
- JWT and API-key authentication utilities, role checks, password hashing helpers, and production secret validation.
- Provider-backed LLM abstraction with OpenAI/Ollama support, retries, fallback actions, JSON parsing, and token-budget tracking.
- CLI commands, demo scripts, a legacy static frontend, and a separate `web-ui/` application.
- Pytest coverage for engine behavior, services, CLI behavior, validation, security, and lifecycle features.

## Claim adjudication

This table resolves the recurring claims made by the reviews and proposals. “Done” means the capability is visible in the current source tree; it does not mean it is production-hardened. “Verified” requires a passing automated or manual check.

| Area | Current finding | Evidence/status |
|---|---|---|
| Core engine | **Done, legacy path retained** | `core_engine/engine.py` and engine tests provide tick processing, prompts, action validation, persistence, and fallback behavior. The module-level engine instance remains a compatibility path. |
| World simulation | **Done** | `game_service/`, `models/game_models.py`, lifecycle services, world ticker, booking, promos, and storylines are present and covered by focused tests. |
| Database models | **Done; migration chain executes with schema drift** | Alembic has a two-revision chain and clean SQLite upgrade/downgrade passes. The initial revision predates current ORM changes, and the second revision targets an optional legacy table, so ORM/migration parity still needs review before production use. |
| Authentication | **Implemented; focused integration coverage added** | `/game/auth/register`, `/login`, `/refresh`, `/me`, and API-key routes use async database access. JWT subjects are revalidated against active users, refresh tokens are returned by register/login, and focused route tests cover the main token/API-key lifecycle. Broader protected-route authorization coverage remains. |
| Input validation | **Implemented** | `api_gateway/validation.py` and validation tests cover names, IDs, LLM settings, pagination, and enhanced request models. |
| Error handling | **Implemented, quality review pending** | Central handlers and typed API errors exist; route-level exception consistency still needs verification. |
| CORS/security headers/host checks | **Implemented** | Middleware is configured in `api_gateway/main.py`; integration tests cover some headers/CORS behavior. Production values must still be configured explicitly. |
| Rate limiting | **Implemented, coverage limited** | `slowapi` is configured and tested for registration, but behavior under sustained load is not established. |
| WebSockets | **Implemented, not release-verified** | `websocket_hub.py` provides world connections, heartbeat handling, cleanup, and broadcast helpers. Client/server contract and authenticated subscriptions need integration tests. |
| LLM abstraction | **Implemented for OpenAI/Ollama** | `llm_abstraction/provider.py` provides async providers, compatibility facades, fallback actions, JSON parsing, retries, and budgets. Claims about Anthropic/Gemini or streaming should not be treated as current without matching implementation/tests. |
| Async architecture | **Partial** | Async database and LLM code exist, but legacy synchronous compatibility paths and mixed session/query usage remain. Do not claim a fully async system yet. |
| Observability | **Partial** | Structured logging, request IDs, in-memory metrics, and OpenTelemetry setup exist. External metric export, durable dashboards, and alerting are future work. |
| Caching | **Partial/optional** | Redis and `fastapi-cache2` are wired as optional startup infrastructure. Cache policy, cache coverage, and degraded-mode monitoring are not fully documented or tested. |
| Frontends | **`web-ui/` selected as the supported candidate; release verification pending** | `frontend/` is legacy static UI. `web-ui/` is the current React/Vite client with auth and game routes; its production build/deployment and backend API hosting contract still need verification. |
| API documentation | **Partially stale** | Generated OpenAPI is current at runtime; several Markdown examples still describe the older unprefixed API surface. |
| CI/CD and deployment | **Not established in repository docs** | No single verified CI/deployment workflow is documented as the release path. |
| Commercial projections | **Unvalidated assumptions** | `COMMERCIAL_VIABILITY.md` is useful for hypotheses, but user counts, pricing, costs, and revenue projections are not measured results. |
| Persona system | **Design direction, implementation scope mixed** | `WRESTLER_PERSONAS_ANALYSIS.md` describes intended systems; only the portions represented in current models/services should be considered implemented. |

## What is actually done

The current repository has a substantial working foundation: world/domain models, persistence, authentication routes and helpers, validation, security middleware, tick/world simulation, storyline/promo/lifecycle services, WebSocket infrastructure, CLI tooling, OpenAI/Ollama LLM support, and an executable Alembic chain. The migration chain still needs schema-parity review. These are implementation facts, not a claim that the complete product is release-ready.

## What is partially done or needs verification

- Expand auth integration coverage across every protected game route and RBAC boundary.
- Reconcile the existing Alembic chain with current ORM metadata and add migrations for schema drift.
- Verify WebSocket authentication, subscription semantics, reconnect behavior, and frontend consumption.
- Reconcile remaining async database usage and remove or isolate legacy synchronous paths.
- Confirm which LLM providers and response formats are officially supported.
- Replace stale Markdown API examples with examples generated from the current OpenAPI contract.
- Verify `web-ui/` as the supported frontend and document its build, proxy, and deployment path.

## What is not done yet

- A migration-parity check plus a release-grade CI workflow covering tests, linting, typing, dependency checks, and migrations.
- A complete production deployment/runbook with backups, rollback, observability, and secret/configuration requirements.
- External metrics export, dashboards, and alerting.
- Full end-to-end browser/API coverage for the primary player journey.
- Validated commercial traction, pricing, unit economics, or revenue forecasts.

## Future product work

These are product ideas rather than current defects: richer narrative continuity, expanded booking/tournament systems, fan interaction, broadcasting/media features, cross-federation play, mobile clients, social integrations, and advanced AI directing. They should only be scheduled after the P0 release blockers above are verified.

## Known limitations and risks

These are confirmed documentation-level concerns or areas requiring verification; they are not claims that every item is currently broken.

1. **Documentation drift:** Several reports describe an older repository shape, older line counts, legacy `/agents` and `/federations` endpoints, or features as missing that now exist. Use this file, the source tree, and generated OpenAPI schema instead of historical numbers.
2. **Authentication surface:** Registration, login, refresh, current-user, and API-key routes are present under `/game/auth/*` and use async database access. Focused lifecycle tests pass, but every protected route and RBAC boundary still needs end-to-end coverage before calling the API production-ready; the legacy router remains a separate surface.
3. **Configuration safety:** The default JWT secret is intentionally suitable only for development. Production deployments must set `ENV=production`, `JWT_SECRET_KEY`, `CORS_ORIGINS`, and `ALLOWED_HOSTS` explicitly.
4. **Redis is optional at startup:** Cache initialization logs a warning and continues when Redis is unavailable. Production deployments should decide whether that degraded mode is acceptable and monitor it.
5. **Legacy compatibility paths remain:** The engine and LLM layers still expose singleton-style compatibility accessors. New code should prefer injected dependencies; removing the compatibility paths requires a coordinated migration.
6. **Two frontend surfaces exist:** `frontend/` is the legacy static UI, while `web-ui/` is the supported candidate and newer Vite/React UI. Its deployment path and API contract still need explicit release verification.
7. **Operational completeness:** Deployment configuration, CI enforcement, migrations, metrics export, and end-to-end API/UI verification need a single documented workflow.
8. **LLM provider behavior:** Local Ollama availability, provider selection, response-shape validation, and cost/budget behavior should be tested in the environments where the application is deployed.

## Active backlog

Prioritize these in order; do not copy this list into separate roadmap documents.

### P0 — release blockers

- Verify all authentication endpoints and route protections with integration tests.
- Keep the full test suite reproducible in a clean environment and resolve any future import, dependency, or migration failures.
- Verify and document `web-ui/` as the supported frontend, including its backend proxy/deployment contract.
- Document production deployment, required environment variables, database migration, backups, and rollback procedures.

### P1 — reliability and maintainability

- Replace remaining compatibility singletons with dependency injection where practical.
- Add API end-to-end tests for auth, world creation, federation/roster flows, engine advancement, and WebSocket behavior.
- Add a repeatable CI workflow for tests, linting, type checking, and dependency/security checks.
- Export metrics and traces to an external backend rather than relying only on in-memory metrics and console tracing.
- Require future schema changes to include migrations and verify the current chain against ORM metadata.

### P2 — product improvements

- Improve narrative continuity and storyline tooling.
- Expand scheduling, booking, fan interaction, and broadcast experiences after the core workflow is stable.
- Add load/performance tests before introducing caching, queues, or horizontal scaling.
- Consolidate duplicate or superseded documentation after implementation work lands.

## Verification snapshot

Latest focused verification run on 2026-09-17:

```text
uv run --extra dev pytest tests/test_auth_routes.py tests/test_security.py tests/test_prompt_builder.py tests/test_async_llm.py -q
24 passed, 1 skipped, 3 warnings
```

The added authentication integration tests cover registration, login, `/me`, API-key issuance/revocation, refresh-token issuance, and inactive-user rejection for access and refresh tokens. The migration check currently verifies the clean upgrade/downgrade path; legacy-table compatibility and full ORM parity remain explicitly untested release work.

Additional checks:

```text
uv run python -m compileall -q api_gateway game_service models
pass
database migration upgrade head + downgrade base on clean SQLite
pass
```

The full suite now reports **432 passed, 5 skipped, 4 warnings**. The legacy compatibility defects found during this pass were resolved: CRUD no longer passes fields absent from the legacy ORM schema, agent roles are validated at the API boundary, the LLM abstraction exposes the compatibility methods required by `AsyncLLM`, the prompt builder returns the documented structured payload, federation deletion protects non-empty federations, and legacy list routes no longer require an uninitialized Redis cache.

The skipped tests are existing environment/provider compatibility skips. Warnings are from Starlette/AnyIO and FastAPI's deprecated `on_event` startup API. A clean test suite does not by itself establish production readiness; auth route coverage, migration parity, frontend deployment, and operational runbooks remain backlog items.

## Documentation rules

- Add current behavior and setup instructions to `README.md`, `docs/USAGE_GUIDE.md`, or `docs/ARCHITECTURE.md`.
- Record implementation history in `DEVLOG.md`, not in a new permanent “completed” report.
- Date and label audits as historical snapshots.
- Do not publish line counts, coverage percentages, test totals, quality scores, or “production ready” claims without rerunning the measurement.
- Keep one active backlog: this file. Historical proposals may describe ideas, but must link here for current priorities.

## Document map

### Current entry points

- [README](../README.md): short overview and quick start.
- [Usage guide](USAGE_GUIDE.md): legacy workflow guide; endpoint examples require reconciliation.
- [Architecture](ARCHITECTURE.md): target domain architecture and design direction.
- [Codebase reference](codebase.md): implementation-oriented reference with known historical drift.
- [API examples](API_USAGE_EXAMPLES.md): legacy API examples; verify against OpenAPI.
- [Legacy frontend guide](../frontend/README.md): static UI reference only.
- [React frontend guide](../web-ui/README.md): supported frontend candidate, build and local proxy notes; production hosting remains to be verified.

### Historical or aspirational material

- [Enhancement proposal](ENHANCEMENT_PROPOSAL.md): long-term product ideas; not an active sprint plan.
- [Wrestler personas analysis](WRESTLER_PERSONAS_ANALYSIS.md): design proposal, not a complete feature inventory.
- [Commercial viability](COMMERCIAL_VIABILITY.md): dated business assumptions, not a forecast.
- [Refactoring plan](../REFACTOR_PLAN.md): detailed technical refactor analysis; reconcile tasks with this status before starting work.
- [Independent review](../INDEPENDENT_REVIEW.md): exploratory historical recommendations.
- [Codebase template](codebase_template.md): obsolete documentation template.
- [Historical audits](COMPREHENSIVE_CODE_REVIEW.md), [multi-perspective analysis](MULTI_PERSPECTIVE_ANALYSIS.md), and [PR assessment](FINAL_PR_ASSESSMENT.md): dated snapshots, not current measurements.
- [P0](P0_IMPLEMENTATION_SUMMARY.md), [P1](P1_IMPLEMENTATION_SUMMARY.md), [P2](P2_IMPLEMENTATION_SUMMARY.md), and [security implementation](SECURITY_IMPLEMENTATION.md): implementation records, not live checklists.
