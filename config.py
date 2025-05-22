import os

# Use environment variable if set, otherwise default to SQLite
# For PostgreSQL, it might look like: "postgresql://user:password@host:port/dbname"
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./llmfed.db")
