#!/usr/bin/env python3
"""
End-to-end simulation: run cards, weeks, or full federation simulation.

Usage:
  python scripts/run_simulation.py --card          # Run a demo card
  python scripts/run_simulation.py --week          # Run a demo week (1 card)
  python scripts/run_simulation.py --ticks 5       # Max ticks per match (default 50)
"""
import os
import sys
import argparse
import logging
import uuid

# Project root
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

os.environ.setdefault("OPENAI_API_BASE", "http://127.0.0.1:11434/v1")
os.environ.setdefault("OPENAI_MODEL", "llama3.2:3b")

from agent_service.database import SessionLocal, init_db
from agent_service.crud import get_agents, create_agent
from models.entities import AgentCreateData
from models.calendar import Card, Match
from simulation.orchestrator import SimulationOrchestrator, build_demo_card

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def ensure_demo_agents(db, federation_id: str = "demo-fed") -> list:
    """Create demo agents if none exist (one per role)."""
    agents = get_agents(db)
    if agents:
        return agents
    from core_engine.engine import engine_instance
    for role in engine_instance.ROLE_ORDER:
        create_agent(
            db,
            AgentCreateData(
                user_id=str(uuid.uuid4()),
                name=f"Demo_{role.title()}",
                role=role,
                gimmick_description=f"Demo agent for {role}",
                llm_config={"model": os.environ.get("OPENAI_MODEL", "llama3.2:3b"), "temperature": 0.7},
                federation_id=federation_id,
            ),
        )
    db.commit()
    return get_agents(db)


def main():
    parser = argparse.ArgumentParser(description="Run LLMFed end-to-end simulation")
    parser.add_argument("--card", action="store_true", help="Run a demo card (default)")
    parser.add_argument("--week", action="store_true", help="Run a demo week (1 card)")
    parser.add_argument("--ticks", type=int, default=50, help="Max ticks per match (default 50)")
    parser.add_argument("--dry-run", action="store_true", help="Print card only, do not run")
    args = parser.parse_args()

    init_db()
    db = SessionLocal()
    try:
        agents = ensure_demo_agents(db, "demo-fed")
        logger.info(f"Agents: {len(agents)}")
    finally:
        db.close()

    card = build_demo_card("demo-fed")
    logger.info(f"Card: {card.name} with {len(card.matches)} match(es)")
    for m in card.matches:
        logger.info(f"  Match: {m.participant_ids}")

    if args.dry_run:
        logger.info("Dry run: skipping simulation")
        return

    orch = SimulationOrchestrator()
    if args.week:
        results = orch.run_card(card, "demo-fed", max_ticks_per_match=args.ticks)
    else:
        results = orch.run_card(card, "demo-fed", max_ticks_per_match=args.ticks)

    total_ticks = sum(len(r) for r in results)
    logger.info(f"Completed: {len(results)} match(es), ~{total_ticks} tick results")


if __name__ == "__main__":
    main()
