"""
CodebaseIndex: Main orchestrator for the indexing system.

Provides a unified interface to:
- Build indexes
- Process queries
- Manage sessions
"""

import json
from pathlib import Path
from typing import Optional

from .structural import StructuralIndex
from .relational import RelationalIndex
from .session import SessionManager
from .retriever import Retriever
from .materializer import Materializer
from .models import Phase


class CodebaseIndex:
    """
    Main interface for LLM-efficient codebase indexing.

    Usage:
        index = CodebaseIndex("/path/to/codebase")
        index.build()

        # For initial understanding
        print(index.get_overview())

        # For queries
        result = index.query("What calls the authenticate function?")
        print(result)

        # Direct access methods
        print(index.what_calls("authenticate"))
        print(index.grep("session"))
    """

    def __init__(self, root_path: str):
        """Initialize the index for a codebase."""
        self.root_path = Path(root_path).resolve()

        if not self.root_path.exists():
            raise ValueError(f"Path does not exist: {self.root_path}")

        # Initialize components
        self.structural = StructuralIndex(str(self.root_path))
        self.relational: Optional[RelationalIndex] = None
        self.session = SessionManager()
        self.retriever: Optional[Retriever] = None

        self._built = False

    def build(self, exclude_patterns: Optional[list] = None) -> "CodebaseIndex":
        """
        Build all indexes for the codebase.

        Args:
            exclude_patterns: Regex patterns for files/dirs to exclude

        Returns:
            self for chaining
        """
        print(f"Building index for: {self.root_path}")

        # Build structural index
        print("  Building structural index...")
        self.structural.build(exclude_patterns)

        # Build relational index
        print("  Building relational index...")
        self.relational = RelationalIndex(self.structural)
        self.relational.build()

        # Initialize retriever
        self.retriever = Retriever(self.structural, self.relational, self.session)

        self._built = True

        # Print stats
        stats = self.stats()
        print(f"  Done! Indexed {stats['files']} files, {stats['entities']} entities, {stats['call_edges']} call relationships")

        return self

    def _ensure_built(self):
        """Ensure index is built before operations."""
        if not self._built:
            raise RuntimeError("Index not built. Call build() first.")

    # -------------------------------------------------------------------------
    # Query Interface
    # -------------------------------------------------------------------------

    def query(self, query_text: str, budget: int = 4000) -> str:
        """
        Process a natural language query and return formatted results.

        This is the main entry point for LLM interaction.

        Args:
            query_text: Natural language query
            budget: Token budget for response

        Returns:
            Formatted response string
        """
        self._ensure_built()

        result = self.retriever.retrieve(query_text, budget)

        # Format output
        output_parts = []

        # Add interpretation
        output_parts.append(f"**Query**: {query_text}")
        output_parts.append(f"**Interpretation**: {result.query_interpretation}")
        output_parts.append("")

        # Add main content
        if result.items:
            content = self.retriever.materializer.materialize_results(
                result.items,
                budget=budget,
                strategy=result.strategy,
            )
            output_parts.append(content)
        elif result.strategy == "gestalt":
            output_parts.append(self.retriever.get_gestalt())

        # Add suggestions
        if result.suggestions:
            output_parts.append("\n**Suggestions**:")
            for s in result.suggestions:
                output_parts.append(f"  - {s}")

        return "\n".join(output_parts)

    # -------------------------------------------------------------------------
    # Direct Access Methods (for programmatic use)
    # -------------------------------------------------------------------------

    def get_overview(self) -> str:
        """Get codebase overview for initial understanding."""
        self._ensure_built()
        return self.retriever.get_gestalt()

    def what_calls(self, entity_name: str) -> str:
        """Find all callers of an entity."""
        self._ensure_built()
        return self.retriever.what_calls(entity_name)

    def what_does_call(self, entity_name: str) -> str:
        """Find all entities called by an entity."""
        self._ensure_built()
        return self.retriever.what_does_call(entity_name)

    def grep(self, pattern: str) -> str:
        """Search for a pattern in the codebase."""
        self._ensure_built()
        return self.retriever.grep(pattern)

    def impact(self, entity_name: str) -> str:
        """Analyze impact of changing an entity."""
        self._ensure_built()
        return self.retriever.impact(entity_name)

    def find(self, entity_name: str) -> str:
        """Find an entity by name."""
        self._ensure_built()

        entities = self.structural.find_by_name(entity_name)
        if not entities:
            entities = self.structural.find_by_pattern(entity_name)

        if not entities:
            return f"No entity found matching: {entity_name}"

        lines = []
        for entity in entities[:10]:
            lines.append(f"### {entity.name} ({entity.kind.value})")
            lines.append(f"📍 {entity.file_path}:{entity.line_start}")
            lines.append(f"```python\n{self.structural.materialize(entity, 2)}\n```")
            lines.append("")

        return "\n".join(lines)

    def file_summary(self, file_path: str) -> str:
        """Get summary of a file."""
        self._ensure_built()
        return self.structural.get_file_summary(file_path)

    def central_entities(self, top_k: int = 10) -> str:
        """Find the most connected entities in the codebase."""
        self._ensure_built()

        central = self.relational.get_central_entities(top_k)

        lines = ["## Most Connected Entities\n"]
        for entity, score in central:
            callers = len(entity.called_by)
            callees = len(entity.calls)
            lines.append(f"- **{entity.name}** ({entity.file_path}) — {callers} callers, {callees} callees")

        return "\n".join(lines)

    # -------------------------------------------------------------------------
    # Session Management
    # -------------------------------------------------------------------------

    def set_task(self, task: str) -> None:
        """Set the current task being worked on."""
        self.session.set_task(task)

    def add_hypothesis(self, description: str) -> str:
        """Add a hypothesis to track."""
        return self.session.add_hypothesis(description)

    def add_conclusion(self, description: str) -> None:
        """Record a conclusion."""
        self.session.add_conclusion(description)

    def mark_dead_end(self, entity_name: str) -> None:
        """Mark an entity as not relevant to current task."""
        entities = self.structural.find_by_name(entity_name)
        for e in entities:
            self.session.mark_dead_end(e.id)

    def session_summary(self) -> str:
        """Get summary of current session state."""
        return self.session.to_summary()

    def reset_session(self) -> None:
        """Reset the session state."""
        self.session.reset()

    # -------------------------------------------------------------------------
    # Statistics and Info
    # -------------------------------------------------------------------------

    def stats(self) -> dict:
        """Get index statistics."""
        self._ensure_built()

        structural_stats = self.structural.stats()
        relational_stats = self.relational.stats()

        return {**structural_stats, **relational_stats}

    def list_files(self) -> list:
        """List all indexed files."""
        self._ensure_built()
        return self.structural.get_all_files()

    def core_files(self) -> list:
        """Get identified core files."""
        self._ensure_built()
        return self.retriever.core_files

    # -------------------------------------------------------------------------
    # Serialization
    # -------------------------------------------------------------------------

    def save_session(self, path: str) -> None:
        """Save session state to file."""
        with open(path, "w") as f:
            json.dump(self.session.to_dict(), f, indent=2)

    def __repr__(self) -> str:
        status = "built" if self._built else "not built"
        return f"CodebaseIndex({self.root_path}, {status})"
