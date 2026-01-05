# LLM-Efficient Codebase Index

A prototype implementation of an indexing system designed to optimize codebase understanding for Large Language Models.

## Overview

This system indexes Python codebases with a focus on LLM efficiency:

- **Structural Index**: AST-based symbol extraction with multi-level signatures
- **Relational Index**: Call graph and dependency relationships
- **Session Manager**: Tracks accumulated understanding across conversation turns
- **Phase-Aware Retrieval**: Different strategies for initial understanding vs. task-oriented work

## Installation

No external dependencies beyond Python 3.8+ standard library.

```bash
cd /path/to/LLMFed
```

## Quick Start

### Python API

```python
from codebase_index import CodebaseIndex

# Build the index
index = CodebaseIndex("/path/to/codebase")
index.build()

# Get an overview for initial understanding
print(index.get_overview())

# Query with natural language
print(index.query("What calls the authenticate function?"))

# Direct access methods
print(index.what_calls("run_ticks"))        # Find callers
print(index.what_does_call("run_ticks"))    # Find callees
print(index.grep("heat"))                    # Pattern search
print(index.impact("send_prompt"))           # Impact analysis
print(index.find("Engine"))                  # Find entity definition
print(index.central_entities())              # Most connected entities

# Session management
index.set_task("Debug the authentication bug")
index.add_hypothesis("The token validation is failing")
index.add_conclusion("Issue is in the session timeout handling")
print(index.session_summary())
```

### Command Line Interface

```bash
# Interactive REPL
python -m codebase_index.cli /path/to/codebase

# Direct commands
python -m codebase_index.cli /path/to/codebase overview
python -m codebase_index.cli /path/to/codebase calls run_ticks
python -m codebase_index.cli /path/to/codebase grep "session"
python -m codebase_index.cli /path/to/codebase stats
```

### REPL Commands

```
.overview          - Show codebase overview
.grep <pattern>    - Search for pattern
.find <name>       - Find entity by name
.calls <name>      - What calls this?
.callees <name>    - What does this call?
.impact <name>     - Impact analysis
.stats             - Show statistics
.central           - Most connected entities
.files             - List files
.session           - Show session state
.task <desc>       - Set current task
.reset             - Reset session
.quit              - Exit
```

## Key Concepts

### Two-Phase Understanding

The system recognizes two distinct phases of LLM interaction:

1. **Initial Understanding** (gestalt): When the LLM is new to the codebase, provide overview + core files
2. **Task-Oriented** (surgical): When working on a specific task, provide precise, targeted results

### Session State

The Session Manager tracks:
- **Files seen**: What code has been shown and at what detail level
- **Hypotheses**: Active investigations being tracked
- **Conclusions**: Confirmed findings
- **Dead ends**: Areas ruled out as irrelevant

This information influences future retrievals:
- Already-seen code is de-prioritized
- Hypothesis-related code is boosted
- Dead ends are suppressed

### Progressive Materialization

Entities can be shown at 5 detail levels:
- **L0**: Just name and kind (`function get_user`)
- **L1**: Signature (`def get_user(user_id: str) -> User`)
- **L2**: Signature + docstring
- **L3**: Signature + docstring + relationships
- **L4**: Full source code

The materializer selects appropriate detail based on relevance and token budget.

## Architecture

```
CodebaseIndex
    │
    ├── StructuralIndex      # AST parsing, symbols, signatures
    │
    ├── RelationalIndex      # Call graph, dependencies
    │
    ├── SessionManager       # Conversation state
    │
    ├── Retriever           # Query processing, phase detection
    │
    └── Materializer        # Output formatting
```

## Index Statistics (Example)

When indexing the LLMFed codebase:
- 40 files indexed
- 254 entities (53 classes, 71 functions, 130 methods)
- 351 call relationships
- 53 import relationships

## Limitations (Prototype)

- Python only (AST-based parsing)
- No semantic embeddings (pure structural/relational)
- No cross-language support
- No incremental updates (full rebuild on changes)
- No persistence (rebuilds each session)

## Future Enhancements

See `LLM_CODEBASE_INDEX_DESIGN.md` for the full design document including:
- Semantic layer with LLM-generated explanations
- Concept tagging and navigation
- Cross-session learning
- Behavioral indexing (runtime traces)
