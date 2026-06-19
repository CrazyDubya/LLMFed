"""
Retriever: Phase-aware query processing.

Handles:
- Query classification
- Phase detection
- Retrieval strategy selection
- Result ranking and filtering
"""

import re
from pathlib import Path
from typing import List, Optional, Tuple

from .models import (
    Entity,
    Query,
    QueryType,
    Phase,
    RetrievalResult,
    ResultItem,
)
from .structural import StructuralIndex
from .relational import RelationalIndex
from .session import SessionManager
from .materializer import Materializer, create_result_item


class Retriever:
    """
    Phase-aware retrieval system.

    Selects appropriate strategy based on:
    - Current phase (initial understanding vs task-oriented)
    - Query type
    - Session state
    """

    def __init__(
        self,
        structural: StructuralIndex,
        relational: RelationalIndex,
        session: SessionManager,
    ):
        self.structural = structural
        self.relational = relational
        self.session = session
        self.materializer = Materializer(structural, session)

        # Try to load README
        self.readme_content = self._load_readme()

        # Identify core files
        self.core_files = self._identify_core_files()

    def _load_readme(self) -> Optional[str]:
        """Load README.md if it exists."""
        readme_path = self.structural.root_path / "README.md"
        if readme_path.exists():
            try:
                return readme_path.read_text()
            except:
                pass
        return None

    def _identify_core_files(self) -> List[str]:
        """Identify core files based on centrality and naming."""
        scores = {}

        for file_path in self.structural.get_all_files():
            score = 0

            # Score based on file name
            name = Path(file_path).stem
            if name in ("main", "app", "index", "core", "engine", "server"):
                score += 10
            if "test" in name.lower():
                score -= 5

            # Score based on number of entities
            entities = self.structural.get_file_entities(file_path)
            score += len(entities)

            # Score based on being imported
            deps = self.relational.get_file_dependencies(file_path)
            score += len(deps.get("depended_by", [])) * 2

            scores[file_path] = score

        # Return top 5
        sorted_files = sorted(scores.keys(), key=lambda f: scores[f], reverse=True)
        return sorted_files[:5]

    # -------------------------------------------------------------------------
    # Query Classification
    # -------------------------------------------------------------------------

    def classify_query(self, query: str) -> Query:
        """Classify a query and extract relevant information."""
        query_lower = query.lower()

        # Pattern search
        if any(p in query_lower for p in ["find all", "search for", "grep", "pattern"]):
            pattern = self._extract_pattern(query)
            return Query(
                raw_text=query,
                query_type=QueryType.PATTERN_SEARCH,
                extracted_patterns=[pattern] if pattern else [],
            )

        # Relationship: callers
        if any(p in query_lower for p in ["what calls", "who calls", "callers of"]):
            entity = self._extract_entity_name(query)
            return Query(
                raw_text=query,
                query_type=QueryType.RELATIONSHIP,
                extracted_entities=[entity] if entity else [],
                direction="callers",
            )

        # Relationship: callees
        if any(p in query_lower for p in ["calls what", "what does .* call", "dependencies of"]):
            entity = self._extract_entity_name(query)
            return Query(
                raw_text=query,
                query_type=QueryType.RELATIONSHIP,
                extracted_entities=[entity] if entity else [],
                direction="callees",
            )

        # Impact analysis
        if any(p in query_lower for p in ["what would break", "impact of", "affected by"]):
            entity = self._extract_entity_name(query)
            return Query(
                raw_text=query,
                query_type=QueryType.IMPACT,
                extracted_entities=[entity] if entity else [],
            )

        # Explanation / gestalt
        if any(p in query_lower for p in ["how does", "explain", "overview", "architecture"]):
            return Query(
                raw_text=query,
                query_type=QueryType.GESTALT if "codebase" in query_lower or "project" in query_lower else QueryType.EXPLANATION,
            )

        # Definition lookup
        if any(p in query_lower for p in ["where is", "find the", "show me", "definition of"]):
            entity = self._extract_entity_name(query)
            return Query(
                raw_text=query,
                query_type=QueryType.DEFINITION,
                extracted_entities=[entity] if entity else [],
            )

        # Default to pattern search with the whole query
        return Query(
            raw_text=query,
            query_type=QueryType.PATTERN_SEARCH,
            extracted_patterns=[self._make_pattern(query)],
        )

    def _extract_pattern(self, query: str) -> Optional[str]:
        """Extract a search pattern from query."""
        # Look for quoted strings
        match = re.search(r'["\']([^"\']+)["\']', query)
        if match:
            return match.group(1)

        # Look for pattern after keywords
        match = re.search(r'(?:find|search|grep|pattern)\s+(?:for\s+)?(\S+)', query, re.IGNORECASE)
        if match:
            return match.group(1)

        return None

    def _extract_entity_name(self, query: str) -> Optional[str]:
        """Extract an entity name from query."""
        # Look for quoted strings
        match = re.search(r'["\']([^"\']+)["\']', query)
        if match:
            return match.group(1)

        # Look for CamelCase or snake_case words
        matches = re.findall(r'\b([A-Z][a-zA-Z]+|[a-z]+_[a-z_]+)\b', query)
        if matches:
            return matches[-1]  # Take the last one (usually the target)

        # Look for words after keywords
        match = re.search(r'(?:calls?|of|the)\s+(\w+)', query, re.IGNORECASE)
        if match:
            return match.group(1)

        return None

    def _make_pattern(self, query: str) -> str:
        """Make a search pattern from query text."""
        # Remove common words
        stopwords = {"find", "search", "for", "the", "all", "in", "code", "where", "is"}
        words = [w for w in query.lower().split() if w not in stopwords]
        return "|".join(words) if words else query

    # -------------------------------------------------------------------------
    # Retrieval
    # -------------------------------------------------------------------------

    def retrieve(self, query: str, budget: int = 4000) -> RetrievalResult:
        """
        Process a query and return relevant results.

        This is the main entry point for retrieval.
        """
        # Classify query
        parsed_query = self.classify_query(query)

        # Detect phase
        phase = self.session.detect_phase(query)

        # Route to appropriate retrieval method
        if phase == Phase.INITIAL_UNDERSTANDING or parsed_query.query_type == QueryType.GESTALT:
            return self._retrieve_gestalt(parsed_query, budget)

        if parsed_query.query_type == QueryType.PATTERN_SEARCH:
            return self._retrieve_pattern(parsed_query, budget)

        if parsed_query.query_type == QueryType.RELATIONSHIP:
            return self._retrieve_relationship(parsed_query, budget)

        if parsed_query.query_type == QueryType.IMPACT:
            return self._retrieve_impact(parsed_query, budget)

        if parsed_query.query_type == QueryType.DEFINITION:
            return self._retrieve_definition(parsed_query, budget)

        if parsed_query.query_type == QueryType.EXPLANATION:
            return self._retrieve_explanation(parsed_query, budget)

        # Fallback to pattern search
        return self._retrieve_pattern(parsed_query, budget)

    def _retrieve_gestalt(self, query: Query, budget: int) -> RetrievalResult:
        """Retrieve gestalt/overview for initial understanding."""
        content = self.materializer.format_gestalt(
            readme_content=self.readme_content,
            core_files=self.core_files,
        )

        # Record what was shown
        for file_path in self.core_files:
            self.session.record_file_seen(file_path, detail_level=1, context="initial understanding")

        return RetrievalResult(
            items=[],  # Content is pre-formatted
            strategy="gestalt",
            query_interpretation="Providing codebase overview",
            suggestions=[
                "Ask about specific components",
                "Set a task to start working",
                "Ask what calls a specific function",
            ],
        )

    def _retrieve_pattern(self, query: Query, budget: int) -> RetrievalResult:
        """Retrieve by pattern/grep search."""
        pattern = query.extracted_patterns[0] if query.extracted_patterns else query.raw_text

        grep_results = self.structural.grep(pattern)

        items = []
        for entity, line_nums in grep_results[:20]:
            relevance = self.session.get_relevance_boost(entity)
            detail_level = self.session.recommend_detail_level(entity, 0.5)
            items.append(create_result_item(
                entity=entity,
                relevance=relevance,
                detail_level=detail_level,
                structural=self.structural,
                match_reason=f"matches pattern on lines {line_nums[:3]}",
            ))

        # Record what was shown
        result = RetrievalResult(
            items=items,
            strategy="surgical",
            query_interpretation=f"Pattern search for: {pattern}",
            suggestions=self._generate_suggestions(items),
        )
        self.session.record_retrieval(result)
        return result

    def _retrieve_relationship(self, query: Query, budget: int) -> RetrievalResult:
        """Retrieve by relationship (callers/callees)."""
        entity_name = query.extracted_entities[0] if query.extracted_entities else None

        if not entity_name:
            return RetrievalResult(
                items=[],
                strategy="surgical",
                query_interpretation="Could not extract entity name from query",
                suggestions=["Try: 'What calls function_name'"],
            )

        # Find the entity
        entities = self.structural.find_by_name(entity_name)
        if not entities:
            # Try pattern search
            entities = self.structural.find_by_pattern(entity_name)

        if not entities:
            return RetrievalResult(
                items=[],
                strategy="surgical",
                query_interpretation=f"Entity '{entity_name}' not found",
                suggestions=[f"Search for: {entity_name}"],
            )

        # Get relationships
        target = entities[0]
        if query.direction == "callers":
            related = self.relational.what_calls(target.id)
            direction = "Callers"
        else:
            related = self.relational.what_does_call(target.id)
            direction = "Callees"

        items = []
        for entity in related:
            relevance = self.session.get_relevance_boost(entity)
            detail_level = self.session.recommend_detail_level(entity, 0.6)
            items.append(create_result_item(
                entity=entity,
                relevance=relevance,
                detail_level=detail_level,
                structural=self.structural,
                match_reason=f"{direction.lower()} of {target.name}",
            ))

        result = RetrievalResult(
            items=items,
            strategy="surgical",
            query_interpretation=f"{direction} of {target.name}",
            suggestions=self._generate_suggestions(items),
        )
        self.session.record_retrieval(result)
        return result

    def _retrieve_impact(self, query: Query, budget: int) -> RetrievalResult:
        """Retrieve impact analysis."""
        entity_name = query.extracted_entities[0] if query.extracted_entities else None

        if not entity_name:
            return RetrievalResult(
                items=[],
                strategy="surgical",
                query_interpretation="Could not extract entity name from query",
            )

        entities = self.structural.find_by_name(entity_name)
        if not entities:
            return RetrievalResult(
                items=[],
                strategy="surgical",
                query_interpretation=f"Entity '{entity_name}' not found",
            )

        target = entities[0]
        impact = self.relational.impact_analysis(target.id)

        items = []
        for entity in impact.get("all_affected", []):
            relevance = self.session.get_relevance_boost(entity)
            is_direct = entity in impact.get("direct_callers", [])
            detail_level = 2 if is_direct else 1
            items.append(create_result_item(
                entity=entity,
                relevance=relevance,
                detail_level=detail_level,
                structural=self.structural,
                match_reason="direct caller" if is_direct else "indirect caller",
            ))

        result = RetrievalResult(
            items=items,
            strategy="surgical",
            query_interpretation=f"Impact analysis for {target.name}",
            suggestions=[
                f"Look at {target.name} implementation",
                "Check test coverage for affected code",
            ],
        )
        self.session.record_retrieval(result)
        return result

    def _retrieve_definition(self, query: Query, budget: int) -> RetrievalResult:
        """Retrieve entity definition."""
        entity_name = query.extracted_entities[0] if query.extracted_entities else None

        if not entity_name:
            return RetrievalResult(
                items=[],
                strategy="surgical",
                query_interpretation="Could not extract entity name",
            )

        entities = self.structural.find_by_name(entity_name)
        if not entities:
            entities = self.structural.find_by_pattern(entity_name)

        items = []
        for entity in entities[:5]:
            relevance = self.session.get_relevance_boost(entity)
            items.append(create_result_item(
                entity=entity,
                relevance=relevance,
                detail_level=4,  # Full source for definitions
                structural=self.structural,
                match_reason="definition",
            ))

        result = RetrievalResult(
            items=items,
            strategy="surgical",
            query_interpretation=f"Definition of {entity_name}",
            suggestions=self._generate_suggestions(items),
        )
        self.session.record_retrieval(result)
        return result

    def _retrieve_explanation(self, query: Query, budget: int) -> RetrievalResult:
        """Retrieve code for explanation."""
        # Extract what needs explaining
        entity_name = self._extract_entity_name(query.raw_text)

        if entity_name:
            entities = self.structural.find_by_name(entity_name)
            if entities:
                items = []
                for entity in entities[:3]:
                    items.append(create_result_item(
                        entity=entity,
                        relevance=1.0,
                        detail_level=4,
                        structural=self.structural,
                        match_reason="for explanation",
                    ))
                return RetrievalResult(
                    items=items,
                    strategy="surgical",
                    query_interpretation=f"Explaining {entity_name}",
                )

        # Fall back to gestalt
        return self._retrieve_gestalt(query, budget)

    def _generate_suggestions(self, items: List[ResultItem]) -> List[str]:
        """Generate follow-up suggestions based on results."""
        suggestions = []

        if items:
            first = items[0].entity
            suggestions.append(f"What calls {first.name}")
            suggestions.append(f"What does {first.name} call")

        active_hyps = self.session.get_active_hypotheses()
        if active_hyps:
            suggestions.append(f"Investigate: {active_hyps[0].description}")

        return suggestions[:3]

    # -------------------------------------------------------------------------
    # Direct Access Methods
    # -------------------------------------------------------------------------

    def get_gestalt(self) -> str:
        """Get formatted gestalt/overview."""
        return self.materializer.format_gestalt(
            readme_content=self.readme_content,
            core_files=self.core_files,
        )

    def what_calls(self, entity_name: str) -> str:
        """Direct method to find callers of an entity."""
        entities = self.structural.find_by_name(entity_name)
        if not entities:
            return f"Entity '{entity_name}' not found"

        callers = self.relational.what_calls(entities[0].id)
        return self.materializer.format_call_chain(callers, "callers")

    def what_does_call(self, entity_name: str) -> str:
        """Direct method to find what an entity calls."""
        entities = self.structural.find_by_name(entity_name)
        if not entities:
            return f"Entity '{entity_name}' not found"

        callees = self.relational.what_does_call(entities[0].id)
        return self.materializer.format_call_chain(callees, "callees")

    def grep(self, pattern: str) -> str:
        """Direct grep search."""
        results = self.structural.grep(pattern)
        return self.materializer.format_grep_results(results, pattern)

    def impact(self, entity_name: str) -> str:
        """Direct impact analysis."""
        entities = self.structural.find_by_name(entity_name)
        if not entities:
            return f"Entity '{entity_name}' not found"

        impact = self.relational.impact_analysis(entities[0].id)
        return self.materializer.format_impact_analysis(entities[0].id, impact)
