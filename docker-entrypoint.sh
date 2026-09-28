#!/bin/bash
set -e

# Wait for database to be ready
echo "Waiting for database..."
while ! python -c "
import asyncio
import sys
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def check_db():
    try:
        engine = create_async_engine('$DATABASE_URL', echo=False)
        async with engine.connect() as conn:
            await conn.execute(text('SELECT 1'))
        await engine.dispose()
        return True
    except Exception:
        return False

if not asyncio.run(check_db()):
    sys.exit(1)
" 2>/dev/null; do
  echo "Database not ready, waiting..."
  sleep 2
done

echo "Database is ready!"

# Run alembic migrations
echo "Running database migrations..."
alembic upgrade head

# Start the application
echo "Starting application..."
exec uvicorn api_gateway.main:app --host 0.0.0.0 --port 8091
