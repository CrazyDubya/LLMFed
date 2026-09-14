"""
Data models for the LLM-efficient codebase indexing system.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set


class EntityKind(Enum):
    """Types of code entities."""
    MODULE = "module"
    CLASS = "class"
    FUNCTION = "function"
    METHOD = "method"
    VARIABLE = "variable"
    CONSTANT = "constant"


class QueryType(Enum):
    """Types of queries the system can handle."""
    PATTERN_SEARCH = "pattern_search"    # "Find all X"
    RELATIONSHIP = "relationship"         # "What calls X"
    IMPACT = "impact"                      # "What breaks if X changes"
    CONCEPT = "concept"                    # "Authentication code"
    DEFINITION = "definition"              # "Where is X defined"
    EXPLANATION = "explanation"            # "How does X work"
    NAVIGATION = "navigation"              # "What should I look at"
    GESTALT = "gestalt"                    # "How does this codebase work"


class Phase(Enum):
    """Phases of LLM understanding."""
    INITIAL_UNDERSTANDING = "initial"
    TASK_ORIENTED = "task"


class HypothesisStatus(Enum):
    """Status of a hypothesis."""
    ACTIVE = "active"
    CONFIRMED = "confirmed"
    ELIMINATED = "eliminated"


@dataclass
class Entity:
    """Represents a code entity (function, class, module, etc.)."""
    id: str
    kind: EntityKind
    name: str
    qualified_name: str
    file_path: str
    line_start: int
    line_end: int

    # Structural info
    signature: Optional[str] = None
    docstring: Optional[str] = None
    source: Optional[str] = None

    # Relational info (populated by RelationalIndex)
    calls: List[str] = field(default_factory=list)
    called_by: List[str] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)
    contains: List[str] = field(default_factory=list)
    contained_by: Optional[str] = None

    # Semantic info (populated lazily)
    explanation: Optional[str] = None
    concepts: List[str] = field(default_factory=list)

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        if isinstance(other, Entity):
            return self.id == other.id
        return False


@dataclass
class FileInfo:
    """Information about a source file."""
    path: str
    relative_path: str
    language: str
    line_count: int
    entities: List[str] = field(default_factory=list)  # Entity IDs
    imports: List[str] = field(default_factory=list)
    is_core: bool = False


@dataclass
class FileSeenInfo:
    """Tracks when and how a file was seen in a session."""
    path: str
    detail_level: int  # 0-4
    timestamp: datetime
    in_context_of: Optional[str] = None


@dataclass
class Hypothesis:
    """A hypothesis being tracked during investigation."""
    id: str
    description: str
    status: HypothesisStatus
    related_entities: List[str] = field(default_factory=list)
    evidence_for: List[str] = field(default_factory=list)
    evidence_against: List[str] = field(default_factory=list)
    confidence: float = 0.5


@dataclass
class Conclusion:
    """A conclusion reached during investigation."""
    description: str
    timestamp: datetime
    related_entities: List[str] = field(default_factory=list)


@dataclass
class SessionState:
    """State maintained across a conversation session."""
    # Phase tracking
    phase: Phase = Phase.INITIAL_UNDERSTANDING
    understanding_level: float = 0.0

    # Knowledge tracking
    files_seen: Dict[str, FileSeenInfo] = field(default_factory=dict)
    entities_seen: Dict[str, int] = field(default_factory=dict)  # entity_id -> detail_level
    conclusions: List[Conclusion] = field(default_factory=list)

    # Task tracking
    current_task: Optional[str] = None
    hypotheses: List[Hypothesis] = field(default_factory=list)
    dead_ends: Set[str] = field(default_factory=set)

    # Navigation tracking
    exploration_path: List[str] = field(default_factory=list)


@dataclass
class Query:
    """A parsed query with extracted information."""
    raw_text: str
    query_type: QueryType
    extracted_entities: List[str] = field(default_factory=list)
    extracted_patterns: List[str] = field(default_factory=list)
    direction: Optional[str] = None  # "callers" or "callees" for relationship queries


@dataclass
class ResultItem:
    """A single result item from retrieval."""
    entity: Entity
    relevance: float
    detail_level: int
    content: str
    match_reason: str


@dataclass
class RetrievalResult:
    """Result of a retrieval operation."""
    items: List[ResultItem]
    strategy: str  # "gestalt" or "surgical"
    query_interpretation: str
    suggestions: List[str] = field(default_factory=list)

    @property
    def total_tokens(self) -> int:
        """Estimate total tokens in result."""
        return sum(len(item.content.split()) * 1.3 for item in self.items)
