filepath = "api_gateway/routes/core_routes.py"
with open(filepath, "r") as f:
    content = f.read()

content = content.replace(
    "results = engine.run_ticks(n_ticks)", "results = await engine.run_ticks(n_ticks)"
)
content = content.replace(
    "db.query(EngineRequestDB)", "await db.execute(select(EngineRequestDB))"
)
content = content.replace(
    "db.query(NarrativeLogDB)", "await db.execute(select(NarrativeLogDB))"
)
content = content.replace("from sqlalchemy.future import select\n", "")
content = "from sqlalchemy.future import select\n" + content

content = content.replace(".all()", ".scalars().all()")
content = content.replace(
    "order_by(EngineRequestDB.due_tick.desc()).limit(limit)",
    "order_by(EngineRequestDB.due_tick.desc()).limit(limit)",
)

with open(filepath, "w") as f:
    f.write(content)
