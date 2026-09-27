# Fix Log for PR #54 P1 Blockers

## Issues Found

### 1. Match Persistence (P1 - CRITICAL)
**Location**: `core_engine/match_engine.py` lines 955-972
**Problem**: The highlights-only optimization breaks match event persistence. The code only retains highlight spots in MatchResult, but match_db_integration.py expects ALL spots for persistence.
- Line 955: `spots=highlights` - only passes highlights to result
- Line 972: `self.spots.clear()` - clears the full spot list
- `match_db_integration.py` lines 249-278: tries to persist all spots from result.spots

**Fix**: ✅ FIXED - Changed `_build_result()` to keep ALL spots in the result for correct DB persistence. Removed the highlights-only optimization and the `self.spots.clear()` call. DB integration layer now persists all events correctly.

### 2. Missing asyncpg (P1)
**Location**: `requirements.txt`
**Problem**: asyncpg is not in requirements.txt but database.py uses postgresql+asyncpg:// URLs
**Fix**: ✅ FIXED - Added `asyncpg` to requirements.txt after psycopg2-binary

### 3. Docker Compose Password Inconsistency
**Location**: `docker-compose.yml`
**Problem**: API service hardcodes "changeme" (line 6) but db service uses "${POSTGRES_PASSWORD:-changeme}" (line 25)
**Fix**: ✅ FIXED - Changed API service to use `${POSTGRES_PASSWORD:-changeme}` consistently

### 4. Ollama URL for Containers
**Location**: `api_gateway/main.py` line 34
**Problem**: Defaults to http://127.0.0.1:11434/v1 which won't work inside containers
**Fix**: ✅ FIXED - Removed the hardcoded defaults. docker-compose.yml already properly configures OPENAI_API_BASE to use http://ollama:11434/v1 for containers. Local dev users should set their own env vars.

### 5. Missing await on dispose()
**Location**: `api_gateway/main.py` line 94
**Problem**: `db_engine.dispose()` needs `await` for async engines
**Fix**: ✅ FIXED - Changed to `await db_engine.dispose()` in the lifespan shutdown handler

### 6. Schema Init Gap (P1)
**Location**: `Dockerfile`
**Problem**: Docker container doesn't run database migrations on startup, leading to schema mismatch errors
**Fix**: ✅ FIXED - Created `docker-entrypoint.sh` that:
  - Waits for database to be ready
  - Runs alembic migrations (`alembic upgrade head`)
  - Starts the application
  - Updated Dockerfile to use ENTRYPOINT instead of CMD

## All Fixes Applied ✅

All P1 blockers have been addressed:
- Match event persistence now works correctly
- Docker deployment is production-ready with proper dependency management
- Database schema initializes correctly
- Async/await patterns are correct throughout
