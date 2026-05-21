"""Simulation orchestrator: runs cards, weeks, and full federation simulations."""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timezone
from typing import List, Optional, Any, Dict

from models.calendar import Card, Match, EventPhase, Month
from models.card_structure import FullCard, CardType, Segment, SegmentType, CardRunState, SEGMENT_ROLES
from models.wrestling import MatchResult, StorylineStatus
from core_engine.engine import engine_instance
from core_engine.character_evolution import CharacterEvolution
from agent_service.database import SessionLocal, init_db
from agent_service.crud import get_agents, get_agent_by_id
from simulation.card_builder import build_full_card, card_type_from_show_type
from agent_service.wrestling_crud import (
    get_current_champion,
    start_reign,
    get_title_by_id,
)
from models.db_models import (
    AgentDB,
    MatchResultDB,
    NarrativeLogDB,
    StorylineDB,
    TitleDB,
    ReignDB,
    VenueDB,
    AudienceSegmentDB,
)

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SimulationOrchestrator:
    """Orchestrates end-to-end simulation: cards, matches, phases, records."""

    def __init__(self) -> None:
        init_db()
        self._match_results: List[MatchResult] = []

    def run_match(
        self,
        match: Match,
        card: Card,
        federation_id: str,
        max_ticks: int = 200,
        hints: Optional[Dict[str, Any]] = None,
        segment_type: Optional[str] = None,
        card_type: Optional[str] = None,
    ) -> List[Any]:
        """Run a single match through pre_match → match → post_match.

        Returns list of TickResults. Updates agent heat/momentum. Records match result.
        """
        if segment_type or card_type:
            engine_instance.set_segment_context(segment_type=segment_type, card_type=card_type)
        base_hints = hints or {}
        built_hints = self._build_hints(federation_id, match, card)
        engine_instance.set_hints({**base_hints, **built_hints})
        engine_instance.set_match_context(participant_ids=match.participant_ids)
        results = engine_instance.run_full_match(max_ticks=max_ticks)

        # Winner = agent who hit the finisher (engine sets _last_finisher_agent_id)
        winner_id = engine_instance.get_last_finisher_agent_id()

        # Persist match result
        db = SessionLocal()
        try:
            self._persist_match_result(
                db,
                match_id=match.match_id,
                card_id=card.card_id,
                federation_id=federation_id,
                participant_ids=match.participant_ids,
                winner_id=winner_id,
                title_id=match.title_id,
                storyline_id=match.storyline_id,
            )
            db.commit()
            # Character evolution: stats, personality, heat, momentum, win/loss streaks
            evo = CharacterEvolution()
            for pid in match.participant_ids:
                evo.update_agent_after_match(
                    agent_id=pid,
                    federation_id=federation_id,
                    match_result={"winner_id": winner_id},
                    won=(pid == winner_id),
                    was_decisive=True,
                )
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to persist match result: {e}")
            raise
        finally:
            db.close()

        return results

    def _build_hints(
        self, federation_id: str, match: Match, card: Card
    ) -> Dict[str, Any]:
        """Build hints from active storylines, title context, card name."""
        hints: Dict[str, Any] = {}
        db = SessionLocal()
        try:
            if match.storyline_id:
                story = db.query(StorylineDB).filter(
                    StorylineDB.storyline_id == match.storyline_id
                ).first()
                if story and story.status == "active":
                    hints["storyline"] = {
                        "title": story.title,
                        "type": story.storyline_type,
                        "heat": story.heat,
                        "participants": story.participant_ids,
                    }
            if match.title_id:
                title = get_title_by_id(db, match.title_id)
                champ_id = get_current_champion(db, match.title_id) if title else None
                if title:
                    hints["title_match"] = {
                        "title_name": title.name,
                        "tier": title.tier,
                        "is_title_match": True,
                        "champion_id": champ_id,
                    }
            if card.name:
                hints["card_name"] = card.name
            if card.is_ppv:
                hints["is_ppv"] = True
            # Venue: the place where the card happens (name, capacity, concessions, PPV)
            venue_id = getattr(card, "venue_id", None)
            if venue_id:
                from agent_service.venue_crud import get_venue, venue_to_hint
                venue_row = get_venue(db, venue_id)
                if venue_row:
                    hints["venue"] = venue_to_hint(venue_row)
            # Audience: crowd mix and fan preferences (favorites / hated) for reaction bias
            seg_row = db.query(AudienceSegmentDB).filter(
                AudienceSegmentDB.card_id == card.card_id
            ).first()
            if seg_row:
                fav = getattr(seg_row, "favorite_agent_ids", None)
                hated = getattr(seg_row, "hated_agent_ids", None)
                if isinstance(fav, str):
                    try:
                        import json
                        fav = json.loads(fav) if fav else []
                    except Exception:
                        fav = []
                if isinstance(hated, str):
                    try:
                        import json
                        hated = json.loads(hated) if hated else []
                    except Exception:
                        hated = []
                hints["audience"] = {
                    "venue_type": getattr(seg_row, "venue_type", "arena"),
                    "superfan_pct": getattr(seg_row, "superfan_pct", 10),
                    "super_viewer_pct": getattr(seg_row, "super_viewer_pct", 20),
                    "common_viewer_pct": getattr(seg_row, "common_viewer_pct", 40),
                    "common_fan_pct": getattr(seg_row, "common_fan_pct", 30),
                    "favorite_agent_ids": fav if isinstance(fav, list) else [],
                    "hated_agent_ids": hated if isinstance(hated, list) else [],
                }
            else:
                hints["audience"] = {
                    "venue_type": "arena",
                    "superfan_pct": 10,
                    "super_viewer_pct": 20,
                    "common_viewer_pct": 40,
                    "common_fan_pct": 30,
                    "favorite_agent_ids": [],
                    "hated_agent_ids": [],
                }
            # Viewing context: where the audience is (arena = live crowd for match in the middle)
            hints["viewing_context"] = "arena"
            # Travel squad and day-before (who is on this show; prep date for day-before context)
            if getattr(card, "travel_squad_ids", None):
                hints["travel_squad_ids"] = card.travel_squad_ids
            if getattr(card, "prep_date", None):
                hints["prep_date"] = str(card.prep_date)
            if getattr(card, "show_type", None):
                hints["show_type"] = card.show_type
            # Month/season context: where we are in the month (build-up, PPV week, fallout)
            if card.card_date:
                from core_engine.promoter_guidance import build_month_context, build_season_context
                hints["month_context"] = build_month_context(card.card_date)
                hints["season_context"] = build_season_context(card.card_date)
            # World anchor: 4-year spine, marquee show 2 years out (continuity and stakes)
            if card.card_date:
                from models.world_anchor import WorldAnchor, build_default_anchor
                from models.db_models import WorldAnchorDB
                from agent_service.anchor_crud import get_conceptual_card
                from simulation.roster_timeline import get_anchor_card_composition
                from core_engine.promoter_guidance import build_promoter_guidance, build_anchor_stakes_hint

                anchor_row = db.query(WorldAnchorDB).filter(
                    WorldAnchorDB.federation_id == federation_id
                ).first()
                if anchor_row:
                    ws = anchor_row.world_start_date.date() if hasattr(anchor_row.world_start_date, "date") else anchor_row.world_start_date
                    ad = anchor_row.anchor_date.date() if anchor_row.anchor_date and hasattr(anchor_row.anchor_date, "date") else anchor_row.anchor_date
                    anchor = WorldAnchor(federation_id=anchor_row.federation_id, world_start_date=ws, anchor_event_name=anchor_row.anchor_event_name, anchor_date=ad)
                else:
                    anchor = build_default_anchor(federation_id, start_year=card.card_date.year - 2)
                wa_dict = {
                    "phase": anchor.phase_for(card.card_date).value,
                    "anchor_event": anchor.anchor_event_name,
                    "weeks_until_marquee": anchor.weeks_until_marquee(card.card_date),
                    "weeks_since_marquee": anchor.weeks_since_marquee(card.card_date),
                    "years_from_anchor": anchor.years_from_anchor(card.card_date),
                }
                hints["world_anchor"] = wa_dict
                conceptual = get_conceptual_card(db, federation_id)
                if conceptual:
                    hints["conceptual_card"] = conceptual
                composition = get_anchor_card_composition(db, federation_id, anchor)
                hints["promoter_guidance"] = build_promoter_guidance(wa_dict, conceptual, composition)
                hints["anchor_stakes"] = build_anchor_stakes_hint(wa_dict)
                # Run timeline: ripples, trapdoors (gamification layer)
                from agent_service.temporals_crud import get_recent_ripples, get_recent_trapdoors
                hints["run_state"] = {
                    "recent_ripples": get_recent_ripples(db, federation_id, limit=10),
                    "recent_trapdoors": get_recent_trapdoors(db, federation_id, limit=5),
                }
                # Tier 9 immutables: canonical records for recall
                from agent_service.memory_crud import recall_context_for_prompt
                hints["tier9_recall"] = recall_context_for_prompt(db, federation_id, tiers=[9])
        finally:
            db.close()
        return hints

    def _persist_match_result(
        self,
        db,
        match_id: str,
        card_id: str,
        federation_id: str,
        participant_ids: List[str],
        winner_id: Optional[str],
        title_id: Optional[str],
        storyline_id: Optional[str],
    ) -> None:
        """Write MatchResultDB row. Update title reign if title match + winner."""
        title_changed = False
        if title_id and winner_id:
            champ = get_current_champion(db, title_id)
            if champ != winner_id:
                if get_title_by_id(db, title_id):
                    start_reign(db, title_id, winner_id)
                    title_changed = True
        db.add(MatchResultDB(
            match_id=match_id,
            card_id=card_id,
            federation_id=federation_id,
            participant_ids=participant_ids,
            winner_id=winner_id,
            title_id=title_id,
            title_changed=bool(title_changed),
            storyline_id=storyline_id,
            completed_at=_utc_now(),
        ))

    def run_card(
        self,
        card: Card | FullCard,
        federation_id: Optional[str] = None,
        max_ticks_per_match: int = 200,
        hints: Optional[Dict[str, Any]] = None,
        run_prep: bool = False,
        run_fallout: bool = False,
        create_coverage: bool = False,
        compute_revenue: bool = False,
    ) -> List[List[Any]]:
        """Run all matches on a card. Accepts Card or FullCard."""
        if isinstance(card, FullCard):
            return self.run_full_card(
                card, federation_id, max_ticks_per_match, hints,
                run_prep=run_prep, run_fallout=run_fallout,
                create_coverage=create_coverage, compute_revenue=compute_revenue,
            )
        fid = federation_id or card.federation_id
        all_results: List[List[Any]] = []
        for match in card.matches:
            logger.info(f"Running match {match.match_id} on card {card.name}")
            results = self.run_match(match, card, fid, max_ticks=max_ticks_per_match, hints=hints)
            all_results.append(results)
        # Day after: fatigue increment once per card for everyone who worked
        if getattr(card, "card_date", None) and card.matches:
            all_participants = set()
            for m in card.matches:
                if m.participant_ids:
                    all_participants.update(m.participant_ids)
            if all_participants:
                db = SessionLocal()
                try:
                    from core_engine.fatigue import increment_fatigue
                    increment_fatigue(db, list(all_participants), fid, card.card_date)
                finally:
                    db.close()
        return all_results

    def _run_day_before_prep(
        self,
        card: Card,
        federation_id: str,
        card_type: str = "major_tv",
    ) -> List[Any]:
        """Run one promoter+backstage tick for day-before prep: travel, venue, card tomorrow."""
        hints = self._build_hints(
            federation_id,
            Match(match_id="", card_id=card.card_id, participant_ids=[]),
            card,
        )
        hints["card_run_state"] = {
            "segment_index": 0,
            "previous_segment_type": None,
            "last_match_result": None,
            "segments_completed": 0,
        }
        return engine_instance.run_one_segment_tick("prep", card_type, hints["card_run_state"], hints)

    def _run_day_after_fallout(
        self,
        card: Card,
        federation_id: str,
        last_match_results: List[Dict[str, Any]],
        card_type: str = "major_tv",
    ) -> List[Any]:
        """Run one promoter+backstage tick for day-after fallout: react to results, plan next."""
        last = last_match_results[-1] if last_match_results else None
        hints = self._build_hints(
            federation_id,
            Match(match_id="", card_id=card.card_id, participant_ids=[]),
            card,
        )
        hints["card_run_state"] = {
            "segment_index": 0,
            "previous_segment_type": "closing",
            "last_match_result": last,
            "segments_completed": len(last_match_results),
        }
        return engine_instance.run_one_segment_tick("fallout", card_type, hints["card_run_state"], hints)

    def run_full_card(
        self,
        full_card: FullCard,
        federation_id: Optional[str] = None,
        max_ticks_per_match: int = 200,
        hints: Optional[Dict[str, Any]] = None,
        run_prep: bool = False,
        run_fallout: bool = False,
        create_coverage: bool = False,
    ) -> List[List[Any]]:
        """Run a full card segment-by-segment. Before match: opening/promo/backstage etc. run one tick.
        Match segments run full matches. After match: post_match then next segment. CardRunState
        glues segments (previous_segment_type, last_match_result) into hints."""
        fid = federation_id or full_card.federation_id
        all_results: List[List[Any]] = []
        card_run_state = CardRunState(segment_index=0, previous_segment_type=None, last_match_result=None)
        # Build Card for hints (orchestrator expects Card; pass venue_id for venue/place context)
        card = Card(
            card_id=full_card.card_id,
            federation_id=full_card.federation_id,
            name=full_card.name,
            card_date=full_card.card_date,
            week_id=full_card.week_id,
            venue_id=getattr(full_card, "venue_id", None),
            show_type=getattr(full_card, "show_type", None),
            prep_date=getattr(full_card, "prep_date", None),
            travel_squad_ids=getattr(full_card, "travel_squad_ids", None),
            is_ppv=full_card.card_type == CardType.PPV
            or full_card.card_type == CardType.MARQUEE_SEASON
            or full_card.card_type == CardType.MARQUEE_YEAR,
            matches=[],  # Filled per segment
        )
        # Base hints (venue, audience, viewing_context, etc.) for all segments including non-match
        sentinel_match = Match(match_id="", card_id=full_card.card_id, participant_ids=[])
        first_match = (
            self._match_from_segment(full_card, full_card.segments[0])
            if full_card.segments
            and full_card.segments[0].segment_type in (SegmentType.MATCH, SegmentType.DARK_MATCH)
            else None
        )
        base_hints = self._build_hints(fid, first_match or sentinel_match, card)

        if run_prep and getattr(full_card, "prep_date", None):
            logger.info(f"Day-before prep tick for card {full_card.name}")
            self._run_day_before_prep(card, fid, full_card.card_type.value)

        for seg_idx, seg in enumerate(full_card.segments):
            card_run_state.segment_index = seg_idx
            segment_hints = dict(base_hints)
            segment_hints.update(hints or {})
            segment_hints["card_run_state"] = card_run_state.to_hint_dict()

            if seg.segment_type in (SegmentType.MATCH, SegmentType.DARK_MATCH):
                match = self._match_from_segment(full_card, seg)
                if match:
                    logger.info(
                        f"Segment {seg.order}: {seg.segment_type.value} "
                        f"match {match.match_id} on card {full_card.name}"
                    )
                    results = self.run_match(
                        match,
                        card,
                        fid,
                        max_ticks=max_ticks_per_match,
                        hints=segment_hints,
                        segment_type=seg.segment_type.value,
                        card_type=full_card.card_type.value,
                    )
                    all_results.append(results)
                    winner_id = engine_instance.get_last_finisher_agent_id()
                    card_run_state.last_match_result = {
                        "winner_id": winner_id,
                        "match_id": match.match_id,
                        "participant_ids": match.participant_ids,
                    }
                    card_run_state.segment_results.append({
                        "order": seg.order,
                        "segment_type": seg.segment_type.value,
                        "match_id": match.match_id,
                        "winner_id": winner_id,
                    })
                card_run_state.previous_segment_type = seg.segment_type.value
            else:
                # Non-match segment: run one segment tick (opening, promo, backstage, closing, etc.)
                if seg.segment_type.value in SEGMENT_ROLES:
                    logger.info(
                        f"Segment {seg.order}: {seg.segment_type.value} "
                        f"(running segment tick, card={full_card.name})"
                    )
                    if seg.segment_type == SegmentType.PROMO and seg.participant_ids:
                        segment_hints = {**segment_hints, "promo_participant_ids": seg.participant_ids}
                    seg_results = engine_instance.run_one_segment_tick(
                        seg.segment_type.value,
                        full_card.card_type.value,
                        card_run_state.to_hint_dict(),
                        segment_hints,
                    )
                    card_run_state.segment_results.append({
                        "order": seg.order,
                        "segment_type": seg.segment_type.value,
                        "tick_count": len(seg_results),
                    })
                else:
                    logger.info(
                        f"Segment {seg.order}: {seg.segment_type.value} "
                        f"(card={full_card.name}, card_type={full_card.card_type.value})"
                    )
                card_run_state.previous_segment_type = seg.segment_type.value
        # Day after: fatigue increment once per card for everyone who worked (off-camera life)
        if getattr(full_card, "card_date", None):
            all_participants = set()
            match_results_summary: List[Dict[str, Any]] = []
            for seg in full_card.segments:
                if seg.segment_type in (SegmentType.MATCH, SegmentType.DARK_MATCH):
                    match = self._match_from_segment(full_card, seg)
                    if match and match.participant_ids:
                        all_participants.update(match.participant_ids)
                        winner_id = next(
                            (s.get("winner_id") for s in card_run_state.segment_results
                            if s.get("match_id") == match.match_id),
                            None,
                        )
                        if winner_id:
                            match_results_summary.append({
                                "match_id": match.match_id,
                                "winner_id": winner_id,
                                "participant_ids": match.participant_ids,
                            })
            db = SessionLocal()
            try:
                if all_participants:
                    from core_engine.fatigue import increment_fatigue
                    increment_fatigue(db, list(all_participants), fid, full_card.card_date)
                if run_fallout and match_results_summary:
                    logger.info(f"Day-after fallout tick for card {full_card.name}")
                    self._run_day_after_fallout(card, fid, match_results_summary, full_card.card_type.value)
                if create_coverage and full_card.card_date:
                    from agent_service.coverage_crud import create_next_day_coverage
                    create_next_day_coverage(db, full_card.card_id, fid, full_card.card_date)
                if compute_revenue:
                    from agent_service.revenue_crud import compute_and_persist_card_revenue
                    from agent_service.venue_crud import get_venue
                    venue_id = getattr(full_card, "venue_id", None)
                    if venue_id:
                        venue_row = get_venue(db, venue_id)
                        if venue_row:
                            compute_and_persist_card_revenue(
                                db,
                                full_card.card_id,
                                fid,
                                venue_row,
                                show_type=getattr(full_card, "show_type", None),
                                is_ppv=full_card.card_type
                                in (CardType.PPV, CardType.MARQUEE_SEASON, CardType.MARQUEE_YEAR),
                            )
                # Tier 9 immutables: card date, attendance, match card/results, title changes
                from agent_service.memory_crud import record_tier9_immutable
                mr_rows = db.query(MatchResultDB).filter(
                    MatchResultDB.card_id == full_card.card_id
                ).all()
                match_results = [
                    {
                        "match_id": r.match_id,
                        "participant_ids": r.participant_ids or [],
                        "winner_id": r.winner_id,
                        "title_id": r.title_id,
                        "title_changed": bool(r.title_changed),
                    }
                    for r in mr_rows
                ]
                record_tier9_immutable(
                    db,
                    fid,
                    full_card.card_id,
                    full_card.card_date,
                    full_card.name or "",
                    match_results,
                )
                db.commit()
            finally:
                db.close()
        return all_results

    def _match_from_segment(self, full_card: FullCard, seg: Segment) -> Optional[Match]:
        """Build Match from segment; lookup in matches list or card legacy."""
        if not seg.match_id or not seg.participant_ids:
            return None
        for m in full_card.matches:
            if isinstance(m, dict) and m.get("match_id") == seg.match_id:
                return Match(
                    match_id=m["match_id"],
                    card_id=full_card.card_id,
                    participant_ids=m.get("participant_ids", []),
                    stipulation=m.get("stipulation", "StandardMatch"),
                    title_id=m.get("title_id"),
                    storyline_id=m.get("storyline_id"),
                )
        return Match(
            match_id=seg.match_id,
            card_id=full_card.card_id,
            participant_ids=seg.participant_ids,
        )



def run_card(
    card: Card,
    federation_id: Optional[str] = None,
    max_ticks_per_match: int = 200,
    hints: Optional[Dict[str, Any]] = None,
) -> List[List[Any]]:
    """Convenience: run a card with default orchestrator."""
    orch = SimulationOrchestrator()
    return orch.run_card(card, federation_id, max_ticks_per_match, hints)


def build_demo_full_card(
    federation_id: str = "demo-fed", card_type: CardType = CardType.MAJOR_TV
) -> FullCard:
    """Build a demo full card with segments (participants from DB)."""
    card = build_demo_card(federation_id)
    return build_full_card(card, card_type=card_type)


def build_demo_card_three_matches(federation_id: str = "demo-fed") -> Card:
    """Build a demo card with three matches (opener, middle, main). Used to run 'match in the middle'."""
    db = SessionLocal()
    try:
        agents = get_agents(db)
        participants = [a.agent_id for a in agents if getattr(a, "role", None) == "participant"]
        if len(participants) < 2:
            participants = [a.agent_id for a in agents][:6]
        while len(participants) < 6:
            participants = participants + participants[: 6 - len(participants)]
        from agent_service.venue_crud import ensure_default_venue
        venue_id = ensure_default_venue(db, federation_id)
    finally:
        db.close()

    card_id = str(uuid.uuid4())
    matches = [
        Match(match_id=str(uuid.uuid4()), card_id=card_id, participant_ids=participants[0:2], stipulation="StandardMatch"),
        Match(match_id=str(uuid.uuid4()), card_id=card_id, participant_ids=participants[2:4], stipulation="StandardMatch"),
        Match(match_id=str(uuid.uuid4()), card_id=card_id, participant_ids=participants[4:6], stipulation="StandardMatch"),
    ]
    return Card(
        card_id=card_id,
        federation_id=federation_id,
        name="Demo Show (3 matches)",
        card_date=date.today(),
        venue_id=venue_id,
        is_ppv=False,
        matches=matches,
    )


def build_demo_card(federation_id: str = "demo-fed") -> Card:
    """Build a demo card with one match (participants from DB). Ensures a default venue."""
    db = SessionLocal()
    try:
        agents = get_agents(db)
        participants = [a.agent_id for a in agents if getattr(a, "role", None) == "participant"]
        if len(participants) < 2:
            participants = [a.agent_id for a in agents][:2]
        if len(participants) < 2:
            participants = [participants[0], participants[0]] if participants else ["p1", "p2"]
        from agent_service.venue_crud import ensure_default_venue
        venue_id = ensure_default_venue(db, federation_id)
    finally:
        db.close()

    card_id = str(uuid.uuid4())
    match = Match(
        match_id=str(uuid.uuid4()),
        card_id=card_id,
        participant_ids=participants[:2],
        stipulation="StandardMatch",
    )
    return Card(
        card_id=card_id,
        federation_id=federation_id,
        name="Monday Night Demo",
        card_date=date.today(),
        venue_id=venue_id,
        is_ppv=False,
        matches=[match],
    )


def run_week(
    cards: List[Card | FullCard],
    federation_id: Optional[str] = None,
    max_ticks_per_match: int = 200,
    run_prep: bool = False,
    run_fallout: bool = False,
    create_coverage: bool = False,
    compute_revenue: bool = False,
) -> List[List[List[Any]]]:
    """Run all cards in a week. Accepts Card or FullCard. Returns list of card results."""
    orch = SimulationOrchestrator()
    all_card_results: List[List[List[Any]]] = []
    for card in cards:
        fid = federation_id or card.federation_id
        card_results = orch.run_card(
            card, fid, max_ticks_per_match,
            run_prep=run_prep, run_fallout=run_fallout,
            create_coverage=create_coverage, compute_revenue=compute_revenue,
        )
        all_card_results.append(card_results)
    return all_card_results


def run_week_from_template(
    federation_id: str,
    week_start_date: date,
    template: Optional[Any] = None,
    max_ticks_per_match: int = 200,
    fill_matches: bool = True,
    run_prep: bool = False,
    run_fallout: bool = False,
    create_coverage: bool = False,
    compute_revenue: bool = False,
) -> List[List[List[Any]]]:
    """
    Build a week from template, optionally fill matches, then run all cards.

    Returns list of card results (each card = list of match results).
    """
    from models.week_schedule import default_standard_week_template
    from simulation.week_builder import build_week_from_template, fill_week_matches

    tpl = template or default_standard_week_template(federation_id)
    db = SessionLocal()
    try:
        week = build_week_from_template(db, federation_id, week_start_date, tpl)
        if fill_matches:
            fill_week_matches(db, week)
        db.commit()
    finally:
        db.close()

    # Convert each Card to FullCard so run_week uses full segment flow (opening, promo, matches, commercial, backstage, closing)
    full_cards: List[FullCard] = []
    for card in week.cards:
        ct = card_type_from_show_type(getattr(card, "show_type", None))
        full_cards.append(build_full_card(card, card_type=ct))

    return run_week(
        cards=full_cards,
        federation_id=federation_id,
        max_ticks_per_match=max_ticks_per_match,
        run_prep=run_prep,
        run_fallout=run_fallout,
        create_coverage=create_coverage,
        compute_revenue=compute_revenue,
    )


def run_month(
    month: Month,
    federation_id: Optional[str] = None,
    max_ticks_per_match: int = 200,
    fill_matches: bool = True,
    run_prep: bool = False,
    run_fallout: bool = False,
    create_coverage: bool = False,
    compute_revenue: bool = False,
) -> List[List[List[List[Any]]]]:
    """
    Run all cards in a month. For each week, build full cards, fill matches, run.
    Returns list of week results (each week = list of card results).
    """
    from simulation.card_builder import build_full_card, card_type_from_show_type
    fid = federation_id or month.federation_id
    db = SessionLocal()
    all_week_results: List[List[List[List[Any]]]] = []
    try:
        for week in month.weeks:
            if fill_matches:
                from simulation.week_builder import fill_week_matches
                fill_week_matches(db, week)
            full_cards = [
                build_full_card(c, card_type_from_show_type(getattr(c, "show_type", None)))
                for c in week.cards
            ]
            week_results = run_week(
                full_cards,
                federation_id=fid,
                max_ticks_per_match=max_ticks_per_match,
                run_prep=run_prep,
                run_fallout=run_fallout,
                create_coverage=create_coverage,
                compute_revenue=compute_revenue,
            )
            all_week_results.append(week_results)
    finally:
        db.close()
    return all_week_results


def run_season(
    months: List[Month],
    federation_id: Optional[str] = None,
    max_ticks_per_match: int = 200,
    fill_matches: bool = True,
    run_prep: bool = False,
    run_fallout: bool = False,
    create_coverage: bool = False,
    compute_revenue: bool = False,
) -> List[List[List[List[List[Any]]]]]:
    """
    Run all months in a season. Returns list of month results
    (each month = list of week results).
    """
    all_month_results: List[List[List[List[List[Any]]]]] = []
    for month in months:
        month_results = run_month(
            month,
            federation_id=federation_id,
            max_ticks_per_match=max_ticks_per_match,
            fill_matches=fill_matches,
            run_prep=run_prep,
            run_fallout=run_fallout,
            create_coverage=create_coverage,
            compute_revenue=compute_revenue,
        )
        all_month_results.append(month_results)
    return all_month_results
