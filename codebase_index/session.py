"""
Session Manager: Tracks LLM's accumulated understanding across turns.

Maintains:
- Files and entities seen (with detail levels)
- Current task and hypotheses
- Conclusions reached
- Dead ends identified
"""

from datetime import datetime
from typing import Dict, List, Optional, Set
import json

from .models import (
    SessionState,
    FileSeenInfo,
    Hypothesis,
    HypothesisStatus,
    Conclusion,
    Phase,
    Entity,
    RetrievalResult,
)


class SessionManager:
    """
    Manages session state across conversation turns.

    Tracks what the LLM has seen, what it's learned, and what it's investigating.
    Uses this information to influence future retrieval.
    """

    def __init__(self):
        self.state = SessionState()

    # -------------------------------------------------------------------------
    # State Updates
    # -------------------------------------------------------------------------

    def record_file_seen(
        self,
        file_path: str,
        detail_level: int,
        context: Optional[str] = None
    ) -> None:
        """Record that a file was shown to the LLM."""
        existing = self.state.files_seen.get(file_path)

        # Only update if we're showing more detail
        if existing and existing.detail_level >= detail_level:
            return

        self.state.files_seen[file_path] = FileSeenInfo(
            path=file_path,
            detail_level=detail_level,
            timestamp=datetime.now(),
            in_context_of=context or self.state.current_task,
        )

        # Update understanding level
        self._update_understanding_level()

    def record_entity_seen(self, entity_id: str, detail_level: int) -> None:
        """Record that an entity was shown at a certain detail level."""
        existing = self.state.entities_seen.get(entity_id, 0)
        self.state.entities_seen[entity_id] = max(existing, detail_level)

        # Add to exploration path
        if entity_id not in self.state.exploration_path[-5:]:
            self.state.exploration_path.append(entity_id)

    def record_retrieval(self, result: RetrievalResult) -> None:
        """Record all items from a retrieval result."""
        for item in result.items:
            self.record_entity_seen(item.entity.id, item.detail_level)
            if item.entity.file_path:
                self.record_file_seen(
                    item.entity.file_path,
                    item.detail_level,
                    self.state.current_task
                )

    def set_task(self, task: str) -> None:
        """Set the current task being worked on."""
        self.state.current_task = task
        if self.state.phase == Phase.INITIAL_UNDERSTANDING:
            self.state.phase = Phase.TASK_ORIENTED

    def add_hypothesis(
        self,
        description: str,
        related_entities: Optional[List[str]] = None
    ) -> str:
        """Add a new hypothesis."""
        hypothesis = Hypothesis(
            id=f"h{len(self.state.hypotheses) + 1}",
            description=description,
            status=HypothesisStatus.ACTIVE,
            related_entities=related_entities or [],
        )
        self.state.hypotheses.append(hypothesis)
        return hypothesis.id

    def update_hypothesis(
        self,
        hypothesis_id: str,
        status: Optional[HypothesisStatus] = None,
        evidence_for: Optional[str] = None,
        evidence_against: Optional[str] = None,
        confidence: Optional[float] = None,
    ) -> None:
        """Update a hypothesis with new information."""
        for hyp in self.state.hypotheses:
            if hyp.id == hypothesis_id:
                if status:
                    hyp.status = status
                if evidence_for:
                    hyp.evidence_for.append(evidence_for)
                if evidence_against:
                    hyp.evidence_against.append(evidence_against)
                if confidence is not None:
                    hyp.confidence = confidence
                break

    def add_conclusion(
        self,
        description: str,
        related_entities: Optional[List[str]] = None
    ) -> None:
        """Record a conclusion reached during investigation."""
        self.state.conclusions.append(Conclusion(
            description=description,
            timestamp=datetime.now(),
            related_entities=related_entities or [],
        ))

    def mark_dead_end(self, entity_id: str) -> None:
        """Mark an entity as a dead end (not relevant to current task)."""
        self.state.dead_ends.add(entity_id)

    # -------------------------------------------------------------------------
    # Queries
    # -------------------------------------------------------------------------

    def was_seen(self, entity_id: str) -> bool:
        """Check if an entity has been seen."""
        return entity_id in self.state.entities_seen

    def was_seen_at_level(self, entity_id: str, level: int) -> bool:
        """Check if an entity has been seen at a certain detail level or higher."""
        return self.state.entities_seen.get(entity_id, 0) >= level

    def is_dead_end(self, entity_id: str) -> bool:
        """Check if an entity has been marked as a dead end."""
        return entity_id in self.state.dead_ends

    def get_active_hypotheses(self) -> List[Hypothesis]:
        """Get all active hypotheses."""
        return [h for h in self.state.hypotheses if h.status == HypothesisStatus.ACTIVE]

    def get_phase(self) -> Phase:
        """Get current understanding phase."""
        return self.state.phase

    def get_understanding_level(self) -> float:
        """Get estimated understanding level (0-1)."""
        return self.state.understanding_level

    # -------------------------------------------------------------------------
    # Relevance Scoring
    # -------------------------------------------------------------------------

    def get_relevance_boost(self, entity: Entity) -> float:
        """
        Calculate relevance boost/penalty for an entity based on session state.

        Returns a multiplier (1.0 = neutral, >1 = boost, <1 = penalty).
        """
        boost = 1.0

        # Boost: Related to active hypothesis with high confidence
        for hyp in self.get_active_hypotheses():
            if entity.id in hyp.related_entities:
                boost *= (1.0 + hyp.confidence)

        # Penalty: Already seen in high detail
        seen_level = self.state.entities_seen.get(entity.id, 0)
        if seen_level >= 4:
            boost *= 0.3  # Heavy penalty for full source already seen
        elif seen_level >= 2:
            boost *= 0.6

        # Penalty: Marked as dead end
        if entity.id in self.state.dead_ends:
            boost *= 0.1

        # Boost: In recent exploration path (context continuity)
        if entity.id in self.state.exploration_path[-3:]:
            boost *= 1.2

        return boost

    def recommend_detail_level(self, entity: Entity, base_relevance: float) -> int:
        """
        Recommend a detail level for an entity based on session state.

        Returns 0-4.
        """
        # Already seen in detail -> minimal
        seen_level = self.state.entities_seen.get(entity.id, 0)
        if seen_level >= 4:
            return 0

        # Central to active hypothesis -> full detail
        for hyp in self.get_active_hypotheses():
            if entity.id in hyp.related_entities and hyp.confidence > 0.7:
                return 4

        # High relevance -> more detail
        if base_relevance > 0.8:
            return min(4, seen_level + 2)
        elif base_relevance > 0.5:
            return min(3, seen_level + 1)
        elif base_relevance > 0.2:
            return 2
        else:
            return 1

    # -------------------------------------------------------------------------
    # Phase Detection
    # -------------------------------------------------------------------------

    def detect_phase(self, query: str) -> Phase:
        """Detect what phase we're in based on session state and query."""
        # Initial understanding signals
        initial_signals = [
            self.state.understanding_level < 0.3,
            len(self.state.files_seen) < 3,
            self._is_broad_query(query),
            not self.state.current_task,
        ]

        # Task-oriented signals
        task_signals = [
            self.state.understanding_level > 0.5,
            len(self.state.files_seen) > 5,
            self._is_specific_query(query),
            self.state.current_task is not None,
        ]

        if sum(initial_signals) > sum(task_signals):
            return Phase.INITIAL_UNDERSTANDING
        return Phase.TASK_ORIENTED

    def _is_broad_query(self, query: str) -> bool:
        """Check if query is broad/exploratory."""
        broad_patterns = [
            "how does",
            "what is",
            "explain",
            "overview",
            "understand",
            "architecture",
            "structure",
        ]
        query_lower = query.lower()
        return any(p in query_lower for p in broad_patterns)

    def _is_specific_query(self, query: str) -> bool:
        """Check if query is specific/targeted."""
        specific_patterns = [
            "find",
            "fix",
            "change",
            "update",
            "add",
            "remove",
            "where is",
            "what calls",
            "who calls",
        ]
        query_lower = query.lower()
        return any(p in query_lower for p in specific_patterns)

    def _update_understanding_level(self) -> None:
        """Update the estimated understanding level."""
        # Simple heuristic: based on files seen and entities seen
        file_coverage = min(len(self.state.files_seen) / 10, 0.5)
        entity_coverage = min(len(self.state.entities_seen) / 20, 0.5)
        self.state.understanding_level = file_coverage + entity_coverage

        # Transition to task-oriented phase if understanding is sufficient
        if self.state.understanding_level > 0.3:
            self.state.phase = Phase.TASK_ORIENTED

    # -------------------------------------------------------------------------
    # Serialization
    # -------------------------------------------------------------------------

    def to_summary(self) -> str:
        """Generate a summary of the session state for context."""
        lines = [
            f"## Session State",
            f"Phase: {self.state.phase.value}",
            f"Understanding: {self.state.understanding_level:.0%}",
            f"Files seen: {len(self.state.files_seen)}",
            f"Entities seen: {len(self.state.entities_seen)}",
        ]

        if self.state.current_task:
            lines.append(f"\n### Current Task")
            lines.append(self.state.current_task)

        if self.state.hypotheses:
            lines.append(f"\n### Hypotheses")
            for hyp in self.state.hypotheses:
                status_icon = {
                    HypothesisStatus.ACTIVE: "?",
                    HypothesisStatus.CONFIRMED: "v",
                    HypothesisStatus.ELIMINATED: "x",
                }[hyp.status]
                lines.append(f"[{status_icon}] {hyp.description}")

        if self.state.conclusions:
            lines.append(f"\n### Conclusions")
            for conc in self.state.conclusions[-5:]:  # Last 5
                lines.append(f"- {conc.description}")

        return "\n".join(lines)

    def to_dict(self) -> dict:
        """Serialize session state to dict."""
        return {
            "phase": self.state.phase.value,
            "understanding_level": self.state.understanding_level,
            "files_seen": list(self.state.files_seen.keys()),
            "entities_seen": list(self.state.entities_seen.keys()),
            "current_task": self.state.current_task,
            "hypotheses": [
                {
                    "id": h.id,
                    "description": h.description,
                    "status": h.status.value,
                    "confidence": h.confidence,
                }
                for h in self.state.hypotheses
            ],
            "conclusions": [c.description for c in self.state.conclusions],
            "dead_ends": list(self.state.dead_ends),
        }

    def reset(self) -> None:
        """Reset session state."""
        self.state = SessionState()
