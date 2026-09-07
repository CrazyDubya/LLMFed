from pathlib import Path


def replace(path: str, old: str, new: str, count: int = 1) -> None:
    target = Path(path)
    text = target.read_text()
    if old not in text:
        raise SystemExit(f"expected anchor not found in {path}: {old!r}")
    target.write_text(text.replace(old, new, count))


provider = Path("llm_abstraction/provider.py")
text = provider.read_text()
anchor = "    def get_budget_summary(self) -> Dict[str, Any]:\n        return self.budget.summary()\n"
compat = """    def send_prompt(self, prompt: dict) -> dict:
        \"\"\"Compatibility bridge for the simulation engine's structured prompts.\"\"\"
        if not isinstance(prompt, dict) or not prompt:
            return self._fallback_action()
        response = self.generate(json.dumps(prompt))
        try:
            parsed = json.loads(response.content)
            if isinstance(parsed, dict):
                return parsed
        except (json.JSONDecodeError, TypeError):
            pass
        return self._fallback_action()

    async def generate_action_async(self, prompt: dict) -> dict:
        \"\"\"Async compatibility bridge without blocking the event loop.\"\"\"
        import asyncio

        return await asyncio.to_thread(self.send_prompt, prompt)

    @staticmethod
    def _fallback_action() -> dict:
        from core_engine.dispatcher import LLMDispatcher

        fallback = LLMDispatcher().choose_action()
        return {
            \"action_id\": fallback.action_id,
            \"description\": fallback.description,
            \"meta\": fallback.meta,
        }

    def get_budget_summary(self) -> Dict[str, Any]:
        return self.budget.summary()
"""
if anchor not in text:
    raise SystemExit("provider compatibility anchor not found")
provider.write_text(text.replace(anchor, compat, 1))

replace(
    "core_engine/engine.py",
    "# Backwards-compatible alias — will be removed in a future release\nengine_instance = get_engine()\n",
    """# Backwards-compatible alias without import-time database/LLM side effects.
class _LazyEngineProxy:
    def __getattr__(self, name):
        return getattr(get_engine(), name)

    def __setattr__(self, name, value):
        setattr(get_engine(), name, value)


engine_instance = _LazyEngineProxy()
""",
)

replace(
    "api_gateway/main.py",
    'ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")',
    'ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1,testserver").split(",")',
)

replace(
    "api_gateway/routes/core_routes.py",
    """async def engine_debug(engine=Depends(get_engine_dependency)):
    if os.getenv("DEBUG_MODE", "false").lower() != "true":
        raise HTTPException(status_code=404, detail="Endpoint not found")
    try:
        eng = engine
""",
    """async def engine_debug(request: Request):
    if os.getenv("DEBUG_MODE", "false").lower() != "true":
        raise HTTPException(status_code=404, detail="Endpoint not found")
    try:
        eng = get_engine_dependency(request)
""",
)
