import os
import re

filepath = "core_engine/engine.py"
with open(filepath, "r") as f:
    content = f.read()

# Make core methods async
content = content.replace("def run_ticks(self, n: int = 1)", "async def run_ticks(self, n: int = 1)")
content = content.replace("def _process_tick(self, tick_index: int)", "async def _process_tick(self, tick_index: int)")
content = content.replace("def _process_agent_in_role(self, agent_id: str, role: str, tick_index: int, tick_id: str)", "async def _process_agent_in_role(self, agent_id: str, role: str, tick_index: int, tick_id: str)")
content = content.replace("def _call_llm_for_agent(self, context: EventContext, agent_id: str)", "async def _call_llm_for_agent(self, context: EventContext, agent_id: str)")

# Add awaits
content = content.replace("results.extend(self._process_tick(tick_index))", "results.extend(await self._process_tick(tick_index))")
content = content.replace("result = self._process_agent_in_role(agent_id, role, tick_index, tick_id)", "result = await self._process_agent_in_role(agent_id, role, tick_index, tick_id)")
content = content.replace("raw_data = self._call_llm_for_agent(context, agent_id)", "raw_data = await self._call_llm_for_agent(context, agent_id)")

# Fix LLM client call
content = content.replace("return self.llm_client.send_prompt(prompt)", "return await self.llm_client.generate_action_async(prompt)")
content = content.replace("from core_engine.llm_client import LLMClient", "from llm_abstraction.provider import get_llm")
content = content.replace("self.llm_client = LLMClient()", "self.llm_client = get_llm()")

with open(filepath, "w") as f:
    f.write(content)
