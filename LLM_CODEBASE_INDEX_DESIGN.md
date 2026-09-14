# LLM-Efficient Codebase Indexing: Design Document

**Version**: 1.0
**Date**: January 2025
**Status**: Proposal

---

## Executive Summary

This document presents a design for indexing codebases in a way that optimizes for Large Language Model (LLM) efficiency. Unlike traditional code search systems optimized for human developers, this system is designed around how LLMs actually process and understand code.

**Key insight**: LLM-efficient indexing is fundamentally about *cognitive support*, not just retrieval. The system should model the LLM's understanding phase, accumulated knowledge, and task context—not just match queries to code.

**Core findings from empirical testing**:
1. Two distinct phases require different strategies: initial understanding (gestalt) vs. task-oriented work (surgical)
2. Relational queries (call graphs) outperform semantic search for most tasks
3. Session state tracking is essential, not optional
4. LLM-generated explanations dramatically outperform pattern-based concept extraction

---

## Table of Contents

1. [Problem Statement](#1-problem-statement)
2. [Design Goals](#2-design-goals)
3. [Architecture Overview](#3-architecture-overview)
4. [Component Design](#4-component-design)
5. [Data Models](#5-data-models)
6. [Query Processing](#6-query-processing)
7. [Implementation Phases](#7-implementation-phases)
8. [Empirical Validation](#8-empirical-validation)
9. [Open Questions](#9-open-questions)
10. [Appendices](#10-appendices)

---

## 1. Problem Statement

### 1.1 The Fundamental Challenge

LLMs working with code face a **retrieval-understanding tradeoff**:

| Problem | Consequence |
|---------|-------------|
| Too little context | LLM makes changes that break unseen code |
| Too much context | Wastes tokens, dilutes attention, slower, expensive |
| Wrong context | Worse than either extreme |

### 1.2 Why Traditional Indexing Falls Short

Traditional code search systems are optimized for human developers who:
- Have persistent memory across sessions
- Can quickly scan and filter results visually
- Build mental models incrementally over months/years
- Know what they're looking for before searching

LLMs have fundamentally different characteristics:
- Limited context window (memory resets each session)
- Process everything in context (can't "skim")
- Must build understanding from scratch each session
- Often need to discover what's relevant, not just find known items

### 1.3 The Four Efficiency Dimensions

We identified four distinct aspects of "efficiency" for LLM code understanding:

| Dimension | Definition | Metric |
|-----------|------------|--------|
| **A. Token Efficiency** | Minimize tokens needed for sufficient context | Tokens per successful task |
| **B. Retrieval Accuracy** | Maximize probability of retrieving right code | Precision, recall, MRR |
| **C. Cognitive Efficiency** | Structure info for effective LLM reasoning | Task success rate |
| **D. Navigational Efficiency** | Enable efficient exploration | Hops to target |

**Key finding**: These dimensions are not always aligned. Optimizing for one may hurt another. The system must balance them dynamically based on context.

---

## 2. Design Goals

### 2.1 Primary Goals

1. **Phase-Aware Retrieval**: Recognize and optimize for two distinct phases:
   - Initial understanding: Provide gestalt/overview efficiently
   - Task-oriented work: Enable surgical precision

2. **Session Intelligence**: Track and leverage accumulated understanding:
   - What the LLM has seen
   - What conclusions it has drawn
   - What hypotheses it's testing
   - What dead ends it has identified

3. **Relational-First Navigation**: Prioritize structural relationships:
   - Call graphs over semantic similarity
   - Dependency relationships over keyword matching
   - Type hierarchies over text search

4. **Adaptive Materialization**: Present information at appropriate detail:
   - Token budget awareness
   - Relevance-weighted detail levels
   - Seen-item compression

### 2.2 Non-Goals

- Replacing IDE functionality for human developers
- Real-time collaborative editing support
- Supporting non-code assets (images, binaries)
- Cross-repository search (single codebase focus)

### 2.3 Success Criteria

| Metric | Target |
|--------|--------|
| Initial understanding tokens | <10,000 for medium codebase |
| Task completion accuracy | >90% for well-defined tasks |
| Redundant retrieval rate | <10% (files re-fetched unnecessarily) |
| Navigation hops to target | <3 for most queries |

---

## 3. Architecture Overview

### 3.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           USER / LLM INTERFACE                          │
│                                                                         │
│  Queries: "How does authentication work?"                               │
│           "Find all places that modify user sessions"                   │
│           "What would break if I change this function?"                 │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           SESSION MANAGER                               │
│                                                                         │
│  Tracks: Files seen, detail levels, conclusions, hypotheses, dead ends  │
│  Influences: Retrieval strategy, detail level, relevance boosting       │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        PHASE-AWARE RETRIEVER                            │
│                                                                         │
│  ┌─────────────────────────┐    ┌─────────────────────────┐            │
│  │  INITIAL UNDERSTANDING  │    │    TASK-ORIENTED        │            │
│  │                         │    │                         │            │
│  │  • README + docs        │    │  • Pattern grep         │            │
│  │  • Core files           │    │  • Call graph queries   │            │
│  │  • Architecture summary │    │  • Precise navigation   │            │
│  │                         │    │                         │            │
│  │  Goal: Gestalt          │    │  Goal: Surgical         │            │
│  └─────────────────────────┘    └─────────────────────────┘            │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           INDEX LAYERS                                  │
│                                                                         │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐       │
│  │  RELATIONAL │ │ STRUCTURAL  │ │  SEMANTIC   │ │   CURATED   │       │
│  │             │ │             │ │             │ │             │       │
│  │ Call graph  │ │ AST/symbols │ │ Explanations│ │ README      │       │
│  │ Deps graph  │ │ Signatures  │ │ Concepts    │ │ Core files  │       │
│  │ Type hier   │ │ Types       │ │ Embeddings  │ │ Architecture│       │
│  │             │ │             │ │             │ │             │       │
│  │ PRIMARY     │ │ FOUNDATION  │ │ FALLBACK    │ │ BOOTSTRAP   │       │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘       │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                       ADAPTIVE MATERIALIZER                             │
│                                                                         │
│  Levels: L0 (name) → L1 (signature) → L2 (summary) → L3 (context) → L4 │
│                                                                         │
│  Selection based on: token budget, seen status, task relevance          │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
                            OUTPUT TO LLM
```

### 3.2 Data Flow

```
1. Query arrives
       │
       ▼
2. Session Manager enriches with context
   - What phase are we in?
   - What's already known?
   - What's the current focus?
       │
       ▼
3. Phase-Aware Retriever selects strategy
   - Initial → Gestalt retrieval
   - Task → Surgical retrieval
       │
       ▼
4. Index Layers queried (in priority order)
   - Relational first (for task work)
   - Structural for precision
   - Semantic as fallback
   - Curated for bootstrap
       │
       ▼
5. Results merged and ranked
   - Session-aware relevance boosting
   - Deduplication
       │
       ▼
6. Adaptive Materializer formats output
   - Appropriate detail levels
   - Token budget compliance
       │
       ▼
7. Session Manager updated
   - Record what was shown
   - Update understanding model
```

---

## 4. Component Design

### 4.1 Session Manager

The Session Manager maintains state across turns in a conversation, modeling the LLM's accumulated understanding.

#### 4.1.1 State Model

```python
@dataclass
class SessionState:
    # Phase tracking
    phase: Phase  # INITIAL_UNDERSTANDING | TASK_ORIENTED
    understanding_level: float  # 0.0 (none) to 1.0 (complete)

    # Knowledge tracking
    files_seen: Dict[str, FileSeenInfo]
    entities_seen: Dict[str, EntitySeenInfo]
    conclusions: List[Conclusion]

    # Task tracking
    current_task: Optional[Task]
    hypotheses: List[Hypothesis]
    dead_ends: Set[str]

    # Navigation tracking
    exploration_path: List[str]
    suggested_next: List[Suggestion]

@dataclass
class FileSeenInfo:
    path: str
    detail_level: int  # 0-4
    timestamp: datetime
    in_context_of: Optional[str]  # task/question when seen

@dataclass
class Hypothesis:
    id: str
    description: str
    status: HypothesisStatus  # ACTIVE | CONFIRMED | ELIMINATED
    related_entities: List[str]
    evidence_for: List[str]
    evidence_against: List[str]
    confidence: float
```

#### 4.1.2 Key Operations

| Operation | Description |
|-----------|-------------|
| `update_from_retrieval(results)` | Record what was shown to LLM |
| `update_from_llm_response(response)` | Extract conclusions, hypotheses from LLM output |
| `get_relevance_boosts()` | Return entity → boost factor based on current focus |
| `get_detail_recommendations()` | Recommend detail level per entity |
| `suggest_next_exploration()` | Proactively suggest where to look |
| `compress_for_context_limit(budget)` | Serialize state within token budget |

#### 4.1.3 Phase Detection

```python
def detect_phase(session: SessionState, query: str) -> Phase:
    # Initial understanding signals
    initial_signals = [
        session.understanding_level < 0.3,
        len(session.files_seen) < 3,
        query_is_broad(query),  # "How does this work?", "What is this?"
        not session.current_task,
    ]

    # Task-oriented signals
    task_signals = [
        session.understanding_level > 0.5,
        len(session.files_seen) > 5,
        query_is_specific(query),  # "Find X", "Change Y", "Fix bug in Z"
        session.current_task is not None,
    ]

    if sum(initial_signals) > sum(task_signals):
        return Phase.INITIAL_UNDERSTANDING
    return Phase.TASK_ORIENTED
```

### 4.2 Index Layers

#### 4.2.1 Relational Layer (Primary)

The relational layer models code as a graph of relationships. This is the **primary** layer for task-oriented work.

**Node Types**:
- `Function`: Callable code unit
- `Class`: Type definition
- `Module`: File/namespace
- `Variable`: Named value
- `Concept`: Virtual node for semantic grouping

**Edge Types**:
- `CALLS`: Function → Function (with optional annotation)
- `IMPORTS`: Module → Module
- `INHERITS`: Class → Class
- `IMPLEMENTS`: Class → Interface/Protocol
- `REFERENCES`: Any → Any (reads/writes)
- `CONTAINS`: Module → Function/Class
- `TAGGED_WITH`: Any → Concept

**Key Queries**:

```python
class RelationalIndex:
    def what_calls(self, entity_id: str) -> List[Entity]:
        """Find all callers of an entity."""

    def what_does_call(self, entity_id: str) -> List[Entity]:
        """Find all callees of an entity."""

    def impact_analysis(self, entity_id: str, depth: int = 3) -> Graph:
        """Find all entities that would be affected by changing this entity."""

    def find_path(self, from_id: str, to_id: str) -> List[Edge]:
        """Find how two entities are connected."""

    def by_concept(self, concept: str) -> List[Entity]:
        """Find all entities tagged with a concept."""
```

**Implementation**: Built from AST analysis. For Python, use `ast` module to extract calls, imports, class definitions. Store as adjacency lists or in lightweight graph DB (NetworkX for prototype, Neo4j for production).

#### 4.2.2 Structural Layer (Foundation)

The structural layer provides precise, deterministic information about code entities.

**Indexed Information**:
- Symbol table: name → (kind, location, signature)
- Type information: entity → type annotations
- Scope hierarchy: what contains what
- Signature variants: multiple detail levels

**Detail Levels**:
```
L0: "function get_user"
L1: "def get_user(user_id: str) -> User"
L2: "def get_user(user_id: str) -> User: '''Fetches user from database by ID.'''"
L3: L2 + "Calls: db.query, User.from_row. Called by: handle_request, auth_check"
L4: Full source code
```

**Implementation**: Tree-sitter for parsing (fast, incremental, multi-language). Store in SQLite for fast lookups.

#### 4.2.3 Semantic Layer (Fallback)

The semantic layer enables natural language queries when structural/relational queries fail.

**Key Insight from Testing**: Embed *explanations*, not raw code. Raw code embeddings suffer from the symptom-cause gap.

**Indexed Information**:
- LLM-generated explanation per entity
- Concept tags per entity
- Embeddings of explanations

**Generation Process**:
```python
async def generate_entity_explanation(entity: Entity, llm: LLM) -> str:
    prompt = f"""
    Explain what this code does in 1-2 sentences.
    Focus on PURPOSE and BEHAVIOR, not implementation details.

    {entity.source}
    """
    return await llm.generate(prompt)

async def extract_concepts(entity: Entity, llm: LLM) -> List[str]:
    prompt = f"""
    List 3-5 concepts this code relates to.
    Use lowercase, hyphenated terms.
    Examples: authentication, error-handling, data-validation, caching

    {entity.source}
    """
    return parse_concept_list(await llm.generate(prompt))
```

**Implementation**: Any embedding model (OpenAI, Voyage, local). Vector store (Chroma, Qdrant, pgvector).

#### 4.2.4 Curated Layer (Bootstrap)

The curated layer provides pre-selected, high-value information for initial understanding.

**Contents**:
- README and key documentation
- Identified "core files" (entry points, central modules)
- Architecture summary (auto-generated or human-written)
- "Start here" guide

**Core File Identification**:
```python
def identify_core_files(relational_index: RelationalIndex) -> List[str]:
    scores = {}

    for file in relational_index.get_all_files():
        # High in-degree = many things depend on it
        in_degree = len(relational_index.what_calls_in_file(file))

        # Contains entry points = important
        has_entry_points = has_main_or_api_routes(file)

        # Named significantly = probably important
        name_score = score_filename_importance(file)

        scores[file] = in_degree * 2 + has_entry_points * 10 + name_score

    return sorted(scores.keys(), key=lambda f: scores[f], reverse=True)[:5]
```

### 4.3 Phase-Aware Retriever

The retriever selects strategy based on detected phase and query characteristics.

#### 4.3.1 Initial Understanding Strategy

```python
def retrieve_for_initial_understanding(
    query: str,
    session: SessionState,
    indexes: Indexes
) -> RetrievalResult:
    results = []

    # Always include README if not seen
    if "README.md" not in session.files_seen:
        results.append(indexes.curated.get_readme())

    # Include core files not yet seen
    core_files = indexes.curated.get_core_files()
    for f in core_files:
        if f not in session.files_seen:
            results.append(indexes.structural.get_file_summary(f))

    # Include architecture overview
    if session.understanding_level < 0.3:
        results.append(indexes.curated.get_architecture_summary())

    return RetrievalResult(
        items=results,
        strategy="gestalt",
        detail_level=3  # Summary + context
    )
```

#### 4.3.2 Task-Oriented Strategy

```python
def retrieve_for_task(
    query: str,
    session: SessionState,
    indexes: Indexes
) -> RetrievalResult:
    # Classify query type
    query_type = classify_query(query)

    if query_type == QueryType.PATTERN_SEARCH:
        # "Find all places that do X"
        pattern = extract_pattern(query)
        results = indexes.structural.grep(pattern)

    elif query_type == QueryType.RELATIONSHIP:
        # "What calls X", "What does X depend on"
        entity = extract_entity(query)
        direction = extract_direction(query)
        if direction == "callers":
            results = indexes.relational.what_calls(entity)
        else:
            results = indexes.relational.what_does_call(entity)

    elif query_type == QueryType.IMPACT:
        # "What would break if I change X"
        entity = extract_entity(query)
        results = indexes.relational.impact_analysis(entity)

    elif query_type == QueryType.CONCEPT:
        # "Authentication code", "Error handling"
        concept = extract_concept(query)
        results = indexes.semantic.by_concept(concept)

    else:
        # Fallback: semantic search
        results = indexes.semantic.search(query)

    # Apply session-aware boosting
    results = apply_session_boosts(results, session)

    return RetrievalResult(
        items=results,
        strategy="surgical",
        detail_level=varies_by_relevance
    )
```

### 4.4 Adaptive Materializer

The materializer formats retrieval results for optimal LLM consumption.

#### 4.4.1 Detail Level Selection

```python
def select_detail_level(
    entity: Entity,
    session: SessionState,
    task_relevance: float,
    remaining_budget: int
) -> int:
    # Already seen in full detail → minimal
    if session.was_seen_at_level(entity.id, level=4):
        return 0  # Just mention

    # Central to active hypothesis → full detail
    for hyp in session.hypotheses:
        if hyp.status == "ACTIVE" and entity.id in hyp.related_entities:
            if hyp.confidence > 0.7:
                return 4  # Full source

    # High task relevance → more detail
    if task_relevance > 0.8:
        return 4
    elif task_relevance > 0.5:
        return 3
    elif task_relevance > 0.2:
        return 2
    else:
        return 1
```

#### 4.4.2 Token Budget Management

```python
def materialize_within_budget(
    entities: List[Entity],
    budget: int,
    session: SessionState
) -> str:
    output_parts = []
    remaining = budget

    # Sort by relevance
    entities = sorted(entities, key=lambda e: e.relevance, reverse=True)

    for entity in entities:
        level = select_detail_level(entity, session, entity.relevance, remaining)
        content = materialize_at_level(entity, level)

        token_cost = estimate_tokens(content)
        if token_cost > remaining:
            # Try lower detail level
            for lower_level in range(level - 1, -1, -1):
                content = materialize_at_level(entity, lower_level)
                token_cost = estimate_tokens(content)
                if token_cost <= remaining:
                    break
            else:
                continue  # Skip this entity

        output_parts.append(content)
        remaining -= token_cost

        if remaining < 100:  # Reserve for formatting
            break

    return format_output(output_parts)
```

---

## 5. Data Models

### 5.1 Entity Model

```python
@dataclass
class Entity:
    id: str                          # Unique identifier
    kind: EntityKind                  # FUNCTION | CLASS | MODULE | VARIABLE
    name: str                         # Short name
    qualified_name: str               # Full path (module.class.method)
    file_path: str                    # Source file
    line_start: int                   # Starting line
    line_end: int                     # Ending line

    # Structural info
    signature: Optional[str]          # For functions/methods
    docstring: Optional[str]          # Documentation
    type_annotation: Optional[str]    # Return type / variable type

    # Semantic info (populated lazily)
    explanation: Optional[str]        # LLM-generated explanation
    concepts: List[str]               # Concept tags
    embedding: Optional[List[float]]  # Vector embedding

    # Relational info (references to other entity IDs)
    calls: List[str]                  # Outgoing call edges
    called_by: List[str]              # Incoming call edges
    imports: List[str]                # Import dependencies
    imported_by: List[str]            # Reverse imports
    contains: List[str]               # Child entities
    contained_by: Optional[str]       # Parent entity
```

### 5.2 Query Model

```python
@dataclass
class Query:
    raw_text: str                     # Original query string
    query_type: QueryType             # Classified type
    extracted_entities: List[str]     # Entity references found
    extracted_concepts: List[str]     # Concept references found
    extracted_patterns: List[str]     # Grep patterns found

class QueryType(Enum):
    PATTERN_SEARCH = "pattern_search"      # "Find all X"
    RELATIONSHIP = "relationship"           # "What calls X"
    IMPACT = "impact"                       # "What breaks if X changes"
    CONCEPT = "concept"                     # "Authentication code"
    DEFINITION = "definition"               # "Where is X defined"
    EXPLANATION = "explanation"             # "How does X work"
    NAVIGATION = "navigation"               # "What should I look at"
```

### 5.3 Result Model

```python
@dataclass
class RetrievalResult:
    items: List[ResultItem]
    strategy: str                     # "gestalt" | "surgical"
    query_interpretation: str         # How query was understood
    total_tokens: int                 # Estimated token count
    suggestions: List[str]            # Suggested follow-up queries

@dataclass
class ResultItem:
    entity: Entity
    relevance: float                  # 0.0 to 1.0
    detail_level: int                 # 0 to 4
    content: str                      # Materialized content
    match_reason: str                 # Why this was included
```

---

## 6. Query Processing

### 6.1 Query Classification

```python
def classify_query(query: str) -> QueryType:
    query_lower = query.lower()

    # Pattern indicators
    if any(p in query_lower for p in ["find all", "search for", "grep", "where is"]):
        return QueryType.PATTERN_SEARCH

    # Relationship indicators
    if any(p in query_lower for p in ["what calls", "who calls", "calls what", "depends on"]):
        return QueryType.RELATIONSHIP

    # Impact indicators
    if any(p in query_lower for p in ["what would break", "impact of", "affected by"]):
        return QueryType.IMPACT

    # Explanation indicators
    if any(p in query_lower for p in ["how does", "explain", "what does", "why does"]):
        return QueryType.EXPLANATION

    # Definition indicators
    if any(p in query_lower for p in ["where is", "definition of", "find the"]):
        return QueryType.DEFINITION

    # Navigation indicators
    if any(p in query_lower for p in ["where should", "what next", "start with"]):
        return QueryType.NAVIGATION

    # Default to concept search
    return QueryType.CONCEPT
```

### 6.2 Query Processing Pipeline

```python
async def process_query(
    query: str,
    session: SessionState,
    indexes: Indexes
) -> RetrievalResult:

    # 1. Classify query
    query_type = classify_query(query)

    # 2. Detect phase
    phase = detect_phase(session, query)

    # 3. Select retrieval strategy
    if phase == Phase.INITIAL_UNDERSTANDING:
        result = retrieve_for_initial_understanding(query, session, indexes)
    else:
        result = retrieve_for_task(query, session, indexes)

    # 4. Apply session context
    result = apply_session_context(result, session)

    # 5. Materialize within budget
    budget = get_token_budget(session)
    result.content = materialize_within_budget(result.items, budget, session)

    # 6. Update session
    session.update_from_retrieval(result)

    # 7. Generate suggestions
    result.suggestions = generate_suggestions(result, session, indexes)

    return result
```

---

## 7. Implementation Phases

### Phase 1: Foundation (MVP)

**Goal**: Working system with basic capabilities

**Components**:
- [ ] Structural index: AST parsing, symbol extraction, signatures
- [ ] Basic relational index: Call graph, import graph
- [ ] Simple session state: Files seen, current task
- [ ] Grep-based pattern search
- [ ] Basic materialization: 2 detail levels

**Effort**: 1-2 weeks

**Deliverable**: CLI tool that can answer "what calls X" and "find pattern Y"

### Phase 2: Intelligence

**Goal**: Phase-aware retrieval and session tracking

**Components**:
- [ ] Phase detection logic
- [ ] Query classification
- [ ] Curated layer: Core file identification, README integration
- [ ] Enhanced session state: Hypotheses, conclusions
- [ ] Adaptive materialization: 5 detail levels

**Effort**: 2-3 weeks

**Deliverable**: System that behaves differently for initial understanding vs. tasks

### Phase 3: Semantic Enhancement

**Goal**: LLM-powered semantic capabilities

**Components**:
- [ ] LLM-generated explanations (cached)
- [ ] Concept extraction and tagging
- [ ] Embedding-based similarity search
- [ ] Concept navigation

**Effort**: 2-3 weeks

**Deliverable**: Natural language queries work well

### Phase 4: Advanced Features

**Goal**: Production-ready system

**Components**:
- [ ] Incremental index updates
- [ ] Cross-session learning
- [ ] Proactive suggestions
- [ ] Multiple language support
- [ ] Performance optimization

**Effort**: 4+ weeks

**Deliverable**: Robust, scalable system

---

## 8. Empirical Validation

### 8.1 Methodology

We tested the design concepts on a real codebase (LLMFed, ~2000 lines Python) with the author acting as the LLM consumer of the index.

### 8.2 Key Findings

#### Finding 1: Phase-Dependent Strategy

| Strategy | Initial Understanding | Task-Oriented |
|----------|----------------------|---------------|
| README + core files | ★★★★★ | ★☆☆☆☆ |
| Grep patterns | ★☆☆☆☆ | ★★★★★ |
| Call graph queries | ★★★☆☆ | ★★★★★ |
| Signatures only | ★★☆☆☆ | ★★★★☆ |
| Semantic search | ★★☆☆☆ | ★★★☆☆ |

**Conclusion**: Different phases need fundamentally different approaches.

#### Finding 2: Relational > Semantic for Tasks

For task-oriented work, call graph queries ("what calls X") provided precise, actionable results immediately. Semantic search was only useful when we didn't know what to search for.

#### Finding 3: Session State Eliminates Redundancy

In a simulated 3-turn debugging session, tracking files seen and hypotheses formed would have prevented re-reading files and re-discovering conclusions.

#### Finding 4: LLM-Generated Concepts >> Pattern Extraction

Naive pattern extraction (regex on code) produced noise. Useful concepts like "tick-based simulation" and "heat system" required understanding, not extraction.

### 8.3 Metrics from Testing

| Metric | Measured Value |
|--------|----------------|
| Tokens for initial understanding | ~7,000 (README + core file) |
| Queries to find bug location | 3 (grep + 2 reads) |
| Useful info from signatures alone | ~20% |
| Useful info from call graph query | ~90% |

---

## 9. Open Questions

### 9.1 Unresolved Design Questions

1. **Staleness management**: How to keep LLM-generated explanations fresh as code changes?
   - Option A: Regenerate on file modification
   - Option B: Invalidation + lazy regeneration
   - Option C: Version tracking with diff-based updates

2. **Cross-language boundaries**: How to handle polyglot codebases?
   - Option A: Language-specific indexes with bridge layer
   - Option B: Unified AST abstraction
   - Option C: Focus on interface boundaries only

3. **Scale limits**: At what size does each strategy break down?
   - Call graphs: Millions of edges?
   - Semantic search: Embedding quality at scale?
   - Session state: Context window limits?

4. **Evaluation metrics**: How to measure "good" retrieval for LLMs?
   - Task completion rate?
   - Token efficiency?
   - User satisfaction proxy?

### 9.2 Future Research Directions

1. **Learning from sessions**: Can we improve retrieval by learning from successful LLM sessions?

2. **Proactive retrieval**: Can the system anticipate what the LLM will need next?

3. **Multi-agent coordination**: How would this work with multiple LLM agents working on the same codebase?

4. **Behavioral indexing**: Can we incorporate runtime traces, test coverage, profiling data?

---

## 10. Appendices

### Appendix A: Query Examples

| Query | Type | Strategy | Primary Index |
|-------|------|----------|---------------|
| "How does this codebase work?" | Explanation | Gestalt | Curated |
| "Find all uses of UserService" | Pattern | Surgical | Structural |
| "What calls the authenticate function?" | Relationship | Surgical | Relational |
| "What would break if I change the session timeout?" | Impact | Surgical | Relational |
| "Show me the error handling code" | Concept | Surgical | Semantic |
| "Where should I look to fix the login bug?" | Navigation | Surgical | Session + Relational |

### Appendix B: Detail Level Examples

**L0 (Existence)**:
```
function authenticate
```

**L1 (Signature)**:
```
def authenticate(username: str, password: str) -> Optional[User]
```

**L2 (Summary)**:
```
def authenticate(username: str, password: str) -> Optional[User]
    """Validates credentials and returns user if valid, None otherwise."""
```

**L3 (Context)**:
```
def authenticate(username: str, password: str) -> Optional[User]
    """Validates credentials and returns user if valid, None otherwise."""

    # Calls: hash_password, db.get_user, compare_digest
    # Called by: login_handler, api_auth_middleware
    # Concepts: authentication, security, user-management
```

**L4 (Full Source)**:
```python
def authenticate(username: str, password: str) -> Optional[User]:
    """Validates credentials and returns user if valid, None otherwise."""
    user = db.get_user(username)
    if user is None:
        return None
    hashed = hash_password(password, user.salt)
    if compare_digest(hashed, user.password_hash):
        return user
    return None
```

### Appendix C: Session State Example

```yaml
session_state:
  phase: TASK_ORIENTED
  understanding_level: 0.7

  files_seen:
    core_engine/engine.py:
      detail_level: 4
      timestamp: "2025-01-05T10:30:00"
      in_context_of: "investigating heat bug"
    models/entities.py:
      detail_level: 2
      timestamp: "2025-01-05T10:32:00"
      in_context_of: "checking CrowdReactionResponse"

  current_task:
    description: "Fix heat not updating after crowd reactions"
    status: "investigating"

  hypotheses:
    - id: "h1"
      description: "Crowd heat adjustment reads from wrong data source"
      status: CONFIRMED
      confidence: 0.95
      related_entities: ["Engine.run_ticks", "Engine._parse_action_data"]
      evidence_for:
        - "Line 221 uses action_data.get() while other roles use meta.get()"
      evidence_against: []

  conclusions:
    - "Heat is tracked in GameState.heat (engine.py:59)"
    - "Roles process in order: promoter, participant, referee, crowd, announcer, backstage"
    - "All roles except crowd use parsed meta for state updates"

  dead_ends:
    - "heat.py functions (not used in bug path)"
```

---

## Document History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-01-05 | Initial design document |

---

*End of Design Document*
