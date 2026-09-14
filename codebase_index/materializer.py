"""
Materializer: Adaptive output formatting.

Formats retrieval results with appropriate detail levels
based on token budget, session state, and relevance.
"""

from typing import List, Optional

from .models import Entity, ResultItem, RetrievalResult, SessionState
from .structural import StructuralIndex
from .session import SessionManager


class Materializer:
    """
    Formats entities for LLM consumption with adaptive detail levels.

    Considers:
    - Token budget
    - What's been seen before
    - Relevance to current task
    - Entity type and importance
    """

    # Approximate tokens per character (conservative)
    TOKENS_PER_CHAR = 0.3

    def __init__(self, structural: StructuralIndex, session: SessionManager):
        self.structural = structural
        self.session = session

    def materialize_results(
        self,
        items: List[ResultItem],
        budget: int = 4000,
        strategy: str = "surgical",
    ) -> str:
        """
        Materialize a list of result items within a token budget.

        Args:
            items: List of result items to materialize
            budget: Maximum tokens to use
            strategy: "gestalt" for overview or "surgical" for detailed
        """
        output_parts = []
        remaining_budget = budget

        # Sort by relevance if surgical, keep order if gestalt
        if strategy == "surgical":
            items = sorted(items, key=lambda x: x.relevance, reverse=True)

        for item in items:
            content = self._format_item(item)
            tokens = self._estimate_tokens(content)

            if tokens > remaining_budget:
                # Try lower detail level
                for lower_level in range(item.detail_level - 1, -1, -1):
                    item.detail_level = lower_level
                    content = self._format_item(item)
                    tokens = self._estimate_tokens(content)
                    if tokens <= remaining_budget:
                        break
                else:
                    continue  # Skip this item

            output_parts.append(content)
            remaining_budget -= tokens

            if remaining_budget < 100:
                break

        return "\n\n".join(output_parts)

    def _format_item(self, item: ResultItem) -> str:
        """Format a single result item."""
        entity = item.entity
        level = item.detail_level

        # Header
        header = f"### {entity.name} ({entity.kind.value})"
        if item.match_reason:
            header += f" — {item.match_reason}"

        location = f"📍 {entity.file_path}:{entity.line_start}"

        # Content based on detail level
        content = self.structural.materialize(entity, level)

        return f"{header}\n{location}\n```python\n{content}\n```"

    def _estimate_tokens(self, text: str) -> int:
        """Estimate tokens in text."""
        return int(len(text) * self.TOKENS_PER_CHAR)

    def format_gestalt(
        self,
        readme_content: Optional[str],
        core_files: List[str],
        architecture_summary: Optional[str] = None,
    ) -> str:
        """
        Format gestalt/overview response for initial understanding.
        """
        parts = []

        if readme_content:
            parts.append("## Overview\n" + self._truncate(readme_content, 2000))

        if architecture_summary:
            parts.append("## Architecture\n" + architecture_summary)

        if core_files:
            parts.append("## Core Files")
            for file_path in core_files[:5]:
                summary = self.structural.get_file_summary(file_path)
                parts.append(f"\n### {file_path}\n```python\n{summary}\n```")

        return "\n\n".join(parts)

    def format_call_chain(self, entities: List[Entity], direction: str) -> str:
        """Format a call chain (callers or callees)."""
        if not entities:
            return "No results found."

        lines = [f"## {direction.title()} ({len(entities)} found)\n"]

        for entity in entities[:10]:  # Limit to 10
            sig = entity.signature or entity.name
            loc = f"{entity.file_path}:{entity.line_start}"
            lines.append(f"- **{entity.name}** `{loc}`")
            lines.append(f"  `{sig}`")
            if entity.docstring:
                doc = entity.docstring.split('\n')[0][:100]
                lines.append(f"  _{doc}_")

        if len(entities) > 10:
            lines.append(f"\n... and {len(entities) - 10} more")

        return "\n".join(lines)

    def format_grep_results(
        self,
        results: List[tuple],  # List of (Entity, [line_numbers])
        pattern: str,
    ) -> str:
        """Format grep search results."""
        if not results:
            return f"No matches found for pattern: `{pattern}`"

        lines = [f"## Pattern: `{pattern}` ({len(results)} matches)\n"]

        for entity, line_nums in results[:15]:
            lines.append(f"### {entity.name} ({entity.file_path}:{entity.line_start})")
            lines.append(f"Matches on lines: {', '.join(map(str, line_nums[:5]))}")
            lines.append(f"```python\n{self.structural.materialize(entity, 1)}\n```")

        if len(results) > 15:
            lines.append(f"\n... and {len(results) - 15} more matches")

        return "\n".join(lines)

    def format_impact_analysis(
        self,
        entity_id: str,
        impact: dict,
    ) -> str:
        """Format impact analysis results."""
        entity = self.structural.get_entity(entity_id)
        name = entity.name if entity else entity_id

        lines = [f"## Impact Analysis: {name}\n"]

        direct = impact.get("direct_callers", [])
        indirect = impact.get("indirect_callers", [])

        lines.append(f"### Direct Callers ({len(direct)})")
        for e in direct[:10]:
            lines.append(f"- **{e.name}** `{e.file_path}:{e.line_start}`")

        if indirect:
            lines.append(f"\n### Indirect Callers ({len(indirect)})")
            for e in indirect[:10]:
                lines.append(f"- {e.name} `{e.file_path}:{e.line_start}`")

        total = len(direct) + len(indirect)
        lines.append(f"\n**Total affected: {total} entities**")

        return "\n".join(lines)

    def format_session_context(self) -> str:
        """Format current session context for inclusion in prompts."""
        return self.session.to_summary()

    def _truncate(self, text: str, max_chars: int) -> str:
        """Truncate text to max characters."""
        if len(text) <= max_chars:
            return text
        return text[:max_chars - 3] + "..."


def create_result_item(
    entity: Entity,
    relevance: float,
    detail_level: int,
    structural: StructuralIndex,
    match_reason: str = "",
) -> ResultItem:
    """Helper to create a ResultItem."""
    content = structural.materialize(entity, detail_level)
    return ResultItem(
        entity=entity,
        relevance=relevance,
        detail_level=detail_level,
        content=content,
        match_reason=match_reason,
    )
