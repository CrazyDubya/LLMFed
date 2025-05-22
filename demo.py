import os
# Configure model and API base for local Ollama
os.environ["OPENAI_MODEL"] = "long-gemma"
os.environ["OPENAI_API_BASE"] = "http://127.0.0.1:11434/v1"
import logging
from dataclasses import asdict

# Configure debug logging to see prompt building
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)s:%(name)s: %(message)s')

from core_engine.engine import engine_instance

# Set some promoter hints for demonstration
engine_instance.set_hints({"promo_note": "Make the crowd go wild!"})

# Run a single tick
results = engine_instance.run_ticks(1)

# Print the TickResult(s)
for res in results:
    print(asdict(res))
