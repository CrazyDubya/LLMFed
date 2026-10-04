from core_engine.engine import create_engine
from dataclasses import asdict
import logging
import os
import asyncio
# Configure model and API base for local Ollama
os.environ["OPENAI_MODEL"] = "long-gemma"
os.environ["OPENAI_API_BASE"] = "http://127.0.0.1:11434/v1"

# Configure debug logging to see prompt building
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)s:%(name)s: %(message)s')


# Set some promoter hints for demonstration
engine = create_engine()
engine.set_hints({"promo_note": "Make the crowd go wild!"})

# Run a single tick
async def main():
    results = await engine.run_ticks(1)

    # Print the TickResult(s)
    for res in results:
        print(asdict(res))

if __name__ == "__main__":
    asyncio.run(main())

