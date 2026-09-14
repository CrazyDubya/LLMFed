"""
LLM-Efficient Codebase Indexing System

A system designed to index codebases in a way that optimizes for LLM understanding,
not just traditional code search.

Key components:
- StructuralIndex: AST-based symbol and signature extraction
- RelationalIndex: Call graph and dependency relationships
- SessionManager: Tracks LLM's accumulated understanding
- Retriever: Phase-aware query processing
- Materializer: Adaptive output formatting
"""

from .models import Entity, EntityKind, Query, QueryType, SessionState
from .structural import StructuralIndex
from .relational import RelationalIndex
from .session import SessionManager
from .retriever import Retriever
from .materializer import Materializer
from .index import CodebaseIndex

__version__ = "0.1.0"

__all__ = [
    "Entity",
    "EntityKind",
    "Query",
    "QueryType",
    "SessionState",
    "StructuralIndex",
    "RelationalIndex",
    "SessionManager",
    "Retriever",
    "Materializer",
    "CodebaseIndex",
]
