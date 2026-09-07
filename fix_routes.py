import os
import re

routes_dir = "api_gateway/routes"
for filename in os.listdir(routes_dir):
    if filename.endswith(".py"):
        filepath = os.path.join(routes_dir, filename)
        with open(filepath, "r") as f:
            content = f.read()

        # Add dependencies import if not present
        if "get_engine_dependency" not in content and "engine" in content:
            content = content.replace(
                "from fastapi import APIRouter, HTTPException, Depends, Query, Request",
                "from fastapi import APIRouter, HTTPException, Depends, Query, Request\nfrom api_gateway.dependencies import get_engine_dependency, get_llm_dependency",
            )

        # Update endpoints to inject engine
        # This is a basic regex to add engine dependency to functions that use it but don't inject it
        content = re.sub(
            r'def ([a-zA-Z0-9_]+)\((.*)\):\n(\s+)"""(.*?)"""\n\s+(.*?)engine(.*?)\.run_ticks',
            r'def \1(\2, engine=Depends(get_engine_dependency)):\n\3"""\4"""\n\3\5engine\6.run_ticks',
            content,
            flags=re.DOTALL,
        )

        content = re.sub(
            r"def ([a-zA-Z0-9_]+)\((.*)\):\n\s+eng = engine",
            r"def \1(\2, engine=Depends(get_engine_dependency)):\n    eng = engine",
            content,
        )

        with open(filepath, "w") as f:
            f.write(content)
