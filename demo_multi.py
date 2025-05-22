import logging
from dataclasses import asdict
import uuid
import os
from dataclasses import asdict

# Configure model and API base for local Ollama BEFORE importing engine
os.environ["OPENAI_MODEL"] = "long-gemma:latest"
os.environ["OPENAI_API_BASE"] = "http://127.0.0.1:11434/v1"

from core_engine.llm_client import LLMClient
from agent_service.database import SessionLocal
from agent_service.crud import get_agents, create_agent
from models.entities import AgentCreateData
from core_engine.engine import engine_instance

# Re-initialize llm_client with new API base
engine_instance.llm_client = LLMClient()
# For demo, use local dispatcher stub instead of LLM HTTP calls
engine_instance.llm_client.force_remote = False
engine_instance.llm_client.api_key = None  # clear API key to force dispatcher fallback

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)s:%(name)s: %(message)s')

# Ensure at least one agent per role exists in the database
db = SessionLocal()
agents = get_agents(db)
logging.info("Seeding demo agents for missing roles...")
existing_roles = {a.role for a in agents}
for role in engine_instance.role_order:
    if role not in existing_roles:
        name = f"Demo_{role.title()}"
        logging.info(f"Creating agent for role: {role}")
        create_agent(
            db,
            AgentCreateData(
                user_id=str(uuid.uuid4()),
                name=name,
                role=role,
                gimmick_description=f"Demo agent for {role}",
                llm_config={},
            )
        )
agents = get_agents(db)
for ag in agents:
    logging.debug(f"Agent in DB: {ag.agent_id} - {ag.name} (role: {ag.role})")

# Close DB session
db.close()

# Set promoter hints
engine_instance.set_hints({"promo_note": "May the best champion win!"})

# Run multiple ticks (e.g., 5) with multi-agent selection
results = engine_instance.run_ticks(5)

# Display results
for res in results:
    print(asdict(res))
