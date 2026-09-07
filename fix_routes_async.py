import os
import re

routes_dir = "api_gateway/routes"
for filename in os.listdir(routes_dir):
    if filename.endswith(".py"):
        filepath = os.path.join(routes_dir, filename)
        with open(filepath, "r") as f:
            content = f.read()

        # Update Session to AsyncSession
        content = content.replace("Session =", "AsyncSession =")
        if "from sqlalchemy.orm import Session" in content:
            content = content.replace(
                "from sqlalchemy.orm import Session",
                "from sqlalchemy.ext.asyncio import AsyncSession",
            )
        elif "AsyncSession" not in content:
            content = "from sqlalchemy.ext.asyncio import AsyncSession\n" + content

        # Make route definitions async
        content = re.sub(
            r"@router\.(get|post|put|patch|delete)\((.*?)\)\ndef ([a-zA-Z0-9_]+)",
            r"@router.\1(\2)\nasync def \3",
            content,
        )

        # Make crud calls await
        content = re.sub(r"crud\.([a-zA-Z0-9_]+)\(", r"await crud.\1(", content)

        with open(filepath, "w") as f:
            f.write(content)
