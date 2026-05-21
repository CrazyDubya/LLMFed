#!/usr/bin/env python3
"""
Run the match in the middle of a 3-match card and log what context/hints it has.

Builds: card (3 matches) -> full card (segments) -> middle segment = match 2.
Prints: hints (venue, audience, viewing_context, storyline, title, card_name, etc.)
Then runs the middle match (optional, --run) with low tick count for a quick check.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys

_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from agent_service.database import init_db
from simulation.orchestrator import SimulationOrchestrator
from simulation.card_builder import build_full_card
from models.card_structure import CardType, SegmentType

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    ap = argparse.ArgumentParser(description="Build middle match and show what it has; optionally run it.")
    ap.add_argument("--run", action="store_true", help="Actually run the middle match (a few ticks)")
    ap.add_argument("--max-ticks", type=int, default=5, help="Max ticks when --run (default 5)")
    ap.add_argument("--federation", default="demo-fed", help="Federation ID")
    args = ap.parse_args()

    init_db()
    orch = SimulationOrchestrator()

    # Build card with 3 matches and venue
    from simulation.orchestrator import build_demo_card_three_matches
    card = build_demo_card_three_matches(args.federation)
    full_card = build_full_card(card, card_type=CardType.MAJOR_TV)

    # Middle match = second match segment (order 2 or 3 depending on template; first match is often order 2)
    match_segments = [s for s in full_card.segments if s.segment_type in (SegmentType.MATCH, SegmentType.DARK_MATCH)]
    if len(match_segments) < 2:
        logger.warning("Not enough match segments; using first match.")
        seg = match_segments[0] if match_segments else None
    else:
        seg = match_segments[1]  # middle = index 1

    if not seg:
        logger.error("No match segment found on full card.")
        sys.exit(1)

    match = orch._match_from_segment(full_card, seg)
    if not match:
        logger.error("Could not resolve match from segment.")
        sys.exit(1)

    # Card for hints (same as run_full_card: has venue_id from full_card)
    from models.calendar import Card
    hint_card = Card(
        card_id=full_card.card_id,
        federation_id=full_card.federation_id,
        name=full_card.name,
        card_date=full_card.card_date,
        week_id=full_card.week_id,
        venue_id=getattr(full_card, "venue_id", None),
        is_ppv=full_card.card_type in (CardType.PPV, CardType.MARQUEE_SEASON, CardType.MARQUEE_YEAR),
        matches=[],
    )

    hints = orch._build_hints(args.federation, match, hint_card)

    # --- What the match has ---
    logger.info("=== Middle match: what it has ===\n")
    logger.info("Match: %s", match.match_id)
    logger.info("Participants: %s", match.participant_ids)
    logger.info("Card: %s (venue_id=%s)", hint_card.name, getattr(hint_card, "venue_id", None))
    logger.info("\nHints passed to engine (venue, audience, viewing_context, storyline, title, etc.):")
    # Pretty-print hints (skip very long values)
    for k, v in hints.items():
        if isinstance(v, dict) and k in ("promoter_guidance", "conceptual_card") and v:
            logger.info("  %s: <dict with %s keys>", k, len(v))
        else:
            logger.info("  %s: %s", k, json.dumps(v, default=str)[:200] + ("..." if len(str(v)) > 200 else ""))

    # Optional: run the middle match
    if args.run:
        logger.info("\n=== Running middle match (max_ticks=%s) ===", args.max_ticks)
        results = orch.run_match(
            match,
            hint_card,
            args.federation,
            max_ticks=args.max_ticks,
            segment_type=SegmentType.MATCH.value,
            card_type=full_card.card_type.value,
        )
        logger.info("Tick results: %s", len(results))
        for r in results[:3]:
            logger.info("  %s", r)


if __name__ == "__main__":
    main()
