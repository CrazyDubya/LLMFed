from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
import os
import logging

# Import DATABASE_URL from config
# Need to adjust path relative to this file's location
import sys
# Assuming this file is in agent_service, go up one level for config.py
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

try:
    from config import DATABASE_URL
    # Import Base from db_models
    from models.db_models import Base
except ImportError as e:
    print(f"Error importing config or models: {e}")
    print("Ensure config.py and models/db_models.py exist and paths are correct.")
    # Provide default values or raise error
    DATABASE_URL = "sqlite:///./llmfed_fallback.db" # Fallback
    Base = declarative_base() # Fallback Base

# Create engine
# For SQLite, connect_args are needed for FastAPI compatibility
engine_args = {}
if DATABASE_URL.startswith("sqlite"):
    engine_args["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, **engine_args)

# Create session local class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Dependency to get DB session (for FastAPI)
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Function to create database tables
def init_db():
    """Initialize database tables with retry logic."""
    from models.db_models import Base
    logger = logging.getLogger(__name__)
    logger.info(f"Initializing database at {DATABASE_URL}...")
    import time
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            Base.metadata.create_all(bind=engine)
            logger.info(f"Database tables verified: {list(Base.metadata.tables.keys())}")
            return
        except Exception as e:
            logger.warning(f"Attempt {attempt + 1} failed: {str(e)}")
            if attempt == max_retries - 1:
                raise
            time.sleep(1)

init_db()
