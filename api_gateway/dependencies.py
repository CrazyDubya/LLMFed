from fastapi import Request
from agent_service.database import get_db

def get_engine_dependency(request: Request):
    """
    Dependency to get the core engine from the application state instead of
    a global singleton.
    """
    return request.app.state.engine

def get_llm_dependency(request: Request):
    """
    Dependency to get the LLM abstraction from the application state.
    """
    return request.app.state.llm
