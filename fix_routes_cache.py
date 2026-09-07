import re

filepath = "api_gateway/routes/core_routes.py"
with open(filepath, "r") as f:
    content = f.read()

if "from fastapi_cache.decorator import cache" not in content:
    content = "from fastapi_cache.decorator import cache\n" + content

# Cache list_federations
content = re.sub(
    r'(@router\.get\("/federations", .*?\)\n)async def list_federations_endpoint',
    r"\1@cache(expire=60)\nasync def list_federations_endpoint",
    content,
)

with open(filepath, "w") as f:
    f.write(content)
