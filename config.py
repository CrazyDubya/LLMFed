import os
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

# Use environment variable if set, otherwise default to SQLite
# For PostgreSQL, it might look like: "postgresql://user:password@host:port/dbname"
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./llmfed.db")

def get_database_url():
    """Gets the database URL from environment variable or returns a default."""
    return DATABASE_URL

def get_api_host():
    """Gets the API host from environment variable or returns a default."""
    return os.getenv("API_HOST", "0.0.0.0")

def get_api_port():
    """Gets the API port from environment variable or returns a default."""
    return int(os.getenv("API_PORT", "8091"))

def get_max_agents_per_federation():
    """Gets the max agents per federation from environment variable or returns a default."""
    return int(os.getenv("MAX_AGENTS_PER_FEDERATION", "20"))

def get_default_tier():
    """Gets the default tier from environment variable or returns a default."""
    return os.getenv("DEFAULT_TIER", "local")
