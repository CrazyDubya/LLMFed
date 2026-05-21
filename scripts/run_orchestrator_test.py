#!/usr/bin/env python3
"""
Test LLMFed with largest Ollama model as orchestrator and smaller models as agents.

- Orchestrator: promoter role (sets storyline direction) — qwen3.5:35b (largest)
- Agents: participant, referee, crowd, announcer, backstage — smaller models
  (llama3.2:3b, gemma3:4b, gemma3:1b, etc.)
"""
import os
import sys
import logging
import uuid

# Project root
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# Ollama config before imports
os.environ["OPENAI_API_BASE"] = "http://127.0.0.1:11434/v1"
os.environ["OPENAI_MODEL"] = "qwen3.5:35b"  # default / orchestrator fallback

from agent_service.database import SessionLocal, init_db
from agent_service.crud import get_agents, create_agent
from models.entities import AgentCreateData
from core_engine.engine import engine_instance

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Model assignments: orchestrator (largest) vs agents (smaller)
ORCHESTRATOR_MODEL = "qwen3.5:35b"  # largest
AGENT_MODELS = [
    "llama3.2:3b",
    "gemma3:4b",
    "gemma3:1b",
    "llama3.2:1b",
    "smollm2:360m",
]

def main():
    init_db()
    db = SessionLocal()
    try:
        agents = get_agents(db)
        existing_roles = {a.role for a in agents}
        logger.info(f"Existing agents: {len(agents)}, roles: {existing_roles}")

        # Ensure one agent per role; orchestrator gets qwen3.5:35b, others get smaller models
        for i, role in enumerate(engine_instance.ROLE_ORDER):
            if role not in existing_roles:
                model = ORCHESTRATOR_MODEL if role == "promoter" else AGENT_MODELS[i % len(AGENT_MODELS)]
                create_agent(
                    db,
                    AgentCreateData(
                        user_id=str(uuid.uuid4()),
                        name=f"Demo_{role.title()}",
                        role=role,
                        gimmick_description=f"Demo agent for {role}",
                        llm_config={"model": model, "temperature": 0.7},
                    ),
                )
                logger.info(f"Created {role} agent with model {model}")

        db.commit()
        agents = get_agents(db)
        for a in agents:
            cfg = getattr(a, "llm_config", None) or {}
            model = cfg.get("model", "default")
            logger.info(f"  Agent {a.name} ({a.role}) -> {model}")

        engine_instance.set_hints({"promo_note": "Championship match! May the best wrestler win!"})
        engine_instance.llm_client.force_remote = True  # use Ollama
        engine_instance.llm_client.model_name = ORCHESTRATOR_MODEL

        logger.info("Running 3 ticks with mixed models (orchestrator + agents)...")
        results = engine_instance.run_ticks(3)  # 3 ticks × 6 roles = up to 18 LLM calls


        logger.info(f"Completed {len(results)} tick results:")
        for r in results:
            print(f"  Tick {r.time_index} | {r.role} | {r.agent_id} | {r.applied_actions[0].action_id}: {r.applied_actions[0].description[:60]}...")
    finally:
        db.close()


if __name__ == "__main__":
    main()
