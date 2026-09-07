# API Usage Examples

Complete examples for using the LLMFed API endpoints.

## Table of Contents
- [Authentication](#authentication)
- [Federation Management](#federation-management)
- [Agent Management](#agent-management)
- [Engine Control](#engine-control)
- [Error Handling](#error-handling)

## Authentication

### Creating an Access Token

```python
from api_gateway.security import create_access_token
from datetime import timedelta

# Create a token
token = create_access_token(
    data={"sub": "user123", "username": "john_doe"}, expires_delta=timedelta(minutes=30)
)

print(f"Access Token: {token}")
```

### Using the Token

```bash
# In curl requests
curl -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  http://localhost:8091/protected-endpoint
```

```python
# In Python with httpx
import httpx

headers = {"Authorization": f"Bearer {token}"}
response = httpx.get("http://localhost:8091/protected-endpoint", headers=headers)
```

## Federation Management

### Create a Federation

```bash
curl -X POST http://localhost:8091/federations \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Ultimate Wrestling Federation",
    "description": "The premier AI wrestling federation",
    "tier": 1,
    "owner_user_id": "user123"
  }'
```

```python
import httpx

data = {
    "name": "Ultimate Wrestling Federation",
    "description": "The premier AI wrestling federation",
    "tier": 1,
    "owner_user_id": "user123",
}

response = httpx.post("http://localhost:8091/federations", json=data)
federation = response.json()
print(f"Created federation: {federation['federation_id']}")
```

### List All Federations

```bash
curl http://localhost:8091/federations
```

```python
response = httpx.get("http://localhost:8091/federations")
federations = response.json()
for fed in federations:
    print(f"- {fed['name']} (Tier {fed['tier']})")
```

### Get Federation by ID

```bash
curl http://localhost:8091/federations/{federation_id}
```

### Update Federation

```bash
curl -X PATCH http://localhost:8091/federations/{federation_id} \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Updated description",
    "tier": 2
  }'
```

### Delete Federation

```bash
curl -X DELETE http://localhost:8091/federations/{federation_id}
```

## Agent Management

### Create an Agent

```bash
curl -X POST http://localhost:8091/agents \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user123",
    "name": "The Masked Marvel",
    "role": "participant",
    "gimmick_description": "A mysterious masked hero with incredible agility",
    "llm_config": {
      "model": "long-gemma",
      "temperature": 0.8,
      "max_tokens": 150,
      "gimmick": "masked hero"
    },
    "federation_id": "fed123"
  }'
```

```python
agent_data = {
    "user_id": "user123",
    "name": "The Crusher",
    "role": "participant",
    "gimmick_description": "A powerhouse wrestler known for devastating slams",
    "llm_config": {"model": "long-gemma", "temperature": 0.7, "gimmick": "powerhouse"},
    "federation_id": "fed123",
}

response = httpx.post("http://localhost:8091/agents", json=agent_data)
agent = response.json()
print(f"Created agent: {agent['agent_id']}")
```

### Valid Agent Roles

- `participant` - Main wrestlers
- `referee` - Match officials
- `crowd` - Audience members
- `announcer` - Commentators
- `promoter` - Federation management
- `backstage` - Supporting characters

### List All Agents

```bash
curl http://localhost:8091/agents
```

```python
response = httpx.get("http://localhost:8091/agents")
agents = response.json()
for agent in agents:
    print(f"- {agent['name']} ({agent['role']})")
```

### Get Agent by ID

```bash
curl http://localhost:8091/agents/{agent_id}
```

### Update Agent

```bash
curl -X PATCH http://localhost:8091/agents/{agent_id} \
  -H "Content-Type: application/json" \
  -d '{
    "gimmick_description": "Updated character description",
    "llm_config": {
      "temperature": 0.9
    }
  }'
```

### Delete Agent

```bash
curl -X DELETE http://localhost:8091/agents/{agent_id}
```

## Engine Control

### Get Engine Status

```bash
curl http://localhost:8091/engine/status
```

```python
response = httpx.get("http://localhost:8091/engine/status")
status = response.json()
print(f"Current tick: {status['current_tick']}")
print(f"Pending requests: {status['pending_requests_count']}")
```

### Advance Simulation

```bash
# Advance by 1 tick
curl -X POST http://localhost:8091/engine/advance?n_ticks=1

# Advance by 10 ticks
curl -X POST http://localhost:8091/engine/advance?n_ticks=10
```

```python
# Advance simulation and process results
response = httpx.post("http://localhost:8091/engine/advance?n_ticks=5")
results = response.json()

for tick_result in results:
    print(f"Tick {tick_result['time_index']}: Agent {tick_result['agent_id']}")
    for action in tick_result["applied_actions"]:
        print(f"  Action: {action['action_id']}")
```

### Set Engine Hints

```bash
curl -X POST http://localhost:8091/engine/hints \
  -H "Content-Type: application/json" \
  -d '{
    "storyline": "championship rivalry",
    "intensity": "high",
    "focus": "main event"
  }'
```

### Get Narrative Logs

```bash
# Get last 100 logs
curl http://localhost:8091/engine/narrative?limit=100

# Get logs from specific tick
curl http://localhost:8091/engine/narrative?from_tick=50&limit=50
```

```python
response = httpx.get("http://localhost:8091/engine/narrative?limit=20")
logs = response.json()

for log in logs:
    print(f"[Tick {log['time_index']}] {log['role']}: {log['description']}")
```

## Error Handling

### Standard Error Response Format

All errors return a standardized JSON format:

```json
{
  "error": true,
  "message": "Description of the error",
  "status_code": 400,
  "details": {
    "additional": "error details"
  },
  "error_code": "ERROR_TYPE"
}
```

### Handling Validation Errors (422)

```python
try:
    response = httpx.post("http://localhost:8091/agents", json={"invalid": "data"})
    response.raise_for_status()
except httpx.HTTPStatusError as e:
    if e.response.status_code == 422:
        error = e.response.json()
        print("Validation errors:")
        for err in error["details"]["validation_errors"]:
            print(f"  - {err['field']}: {err['message']}")
```

### Handling Not Found Errors (404)

```python
try:
    response = httpx.get(f"http://localhost:8091/agents/{agent_id}")
    response.raise_for_status()
except httpx.HTTPStatusError as e:
    if e.response.status_code == 404:
        print("Agent not found")
```

### Handling Rate Limits (429)

```python
import time


def make_request_with_retry(url, max_retries=3):
    for attempt in range(max_retries):
        try:
            response = httpx.get(url)
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                # Get retry-after header if present
                retry_after = int(e.response.headers.get("Retry-After", 60))
                print(f"Rate limited. Retrying in {retry_after} seconds...")
                time.sleep(retry_after)
            else:
                raise
    raise Exception("Max retries exceeded")
```

## Complete Workflow Example

Here's a complete example of creating a federation, adding agents, and running a simulation:

```python
import httpx
import time

# Configuration
API_BASE = "http://localhost:8091"
client = httpx.Client(base_url=API_BASE)

try:
    # 1. Create a federation
    print("Creating federation...")
    federation_response = client.post(
        "/federations",
        json={
            "name": "Extreme Wrestling Alliance",
            "description": "High-energy wrestling entertainment",
            "tier": 2,
            "owner_user_id": "admin001",
        },
    )
    federation = federation_response.json()
    fed_id = federation["federation_id"]
    print(f"✓ Created federation: {fed_id}")

    # 2. Create multiple agents
    print("\nCreating agents...")
    agents = []

    wrestler_configs = [
        {
            "name": "Thunder Strike",
            "gimmick": "High-flying acrobat",
            "temperature": 0.8,
        },
        {
            "name": "Iron Mountain",
            "gimmick": "Unstoppable powerhouse",
            "temperature": 0.6,
        },
        {
            "name": "The Showman",
            "gimmick": "Charismatic entertainer",
            "temperature": 0.9,
        },
    ]

    for config in wrestler_configs:
        agent_response = client.post(
            "/agents",
            json={
                "user_id": "admin001",
                "name": config["name"],
                "role": "participant",
                "gimmick_description": config["gimmick"],
                "llm_config": {
                    "model": "long-gemma",
                    "temperature": config["temperature"],
                },
                "federation_id": fed_id,
            },
        )
        agent = agent_response.json()
        agents.append(agent)
        print(f"✓ Created agent: {agent['name']}")

    # 3. Add a referee
    print("\nAdding referee...")
    ref_response = client.post(
        "/agents",
        json={
            "user_id": "admin001",
            "name": "Ref Johnson",
            "role": "referee",
            "gimmick_description": "Fair and impartial official",
            "llm_config": {"model": "long-gemma", "temperature": 0.5},
            "federation_id": fed_id,
        },
    )
    print(f"✓ Created referee")

    # 4. Set engine hints for storyline
    print("\nSetting storyline hints...")
    client.post(
        "/engine/hints",
        json={
            "storyline": "rivalry between Thunder Strike and Iron Mountain",
            "intensity": "high",
            "event_type": "championship match",
        },
    )
    print("✓ Hints set")

    # 5. Run simulation
    print("\nRunning simulation...")
    for tick in range(5):
        print(f"  Advancing tick {tick + 1}/5...")
        advance_response = client.post("/engine/advance?n_ticks=1")
        results = advance_response.json()
        time.sleep(0.5)  # Brief pause between ticks
    print("✓ Simulation complete")

    # 6. Get narrative logs
    print("\nRetrieving narrative...")
    narrative_response = client.get("/engine/narrative?limit=20")
    logs = narrative_response.json()

    print("\n" + "=" * 60)
    print("MATCH NARRATIVE")
    print("=" * 60)
    for log in logs[:10]:
        print(f"[{log['role'].upper()}] {log['description']}")

    print("\n✅ Workflow complete!")

except httpx.HTTPStatusError as e:
    print(f"\n❌ Error: {e.response.status_code}")
    print(e.response.json())
finally:
    client.close()
```

## Advanced Features

### Using the LLM Abstraction Layer

```python
from llm_abstraction import get_llm

# Get LLM instance (auto-selects best available provider)
llm = get_llm()

# Generate a response
response = llm.generate(
    prompt="What's a good wrestling finishing move?",
    system_message="You are a creative wrestling consultant",
    temperature=0.8,
)

print(response.content)
```

### Input Validation

```python
from api_gateway.validation import (
    validate_agent_name,
    validate_user_id,
    ValidationError,
)

try:
    name = validate_agent_name("The Destroyer")
    print(f"Valid name: {name}")
except ValidationError as e:
    print(f"Invalid name: {e}")
```

### Security Headers

All API responses include security headers:
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `X-XSS-Protection: 1; mode=block`
- `Strict-Transport-Security: max-age=31536000`
- `Content-Security-Policy: default-src 'self'`

## Rate Limits

Default rate limits:
- Root endpoint (`/`): 100 requests/minute
- Agent creation: 10 requests/minute
- Other endpoints: No limit (configurable)

Rate limit information is included in response headers:
- `X-RateLimit-Limit`: Maximum requests allowed
- `X-RateLimit-Remaining`: Requests remaining
- `X-RateLimit-Reset`: Time when limit resets

## Support

For issues or questions:
- Check the [SECURITY_IMPLEMENTATION.md](SECURITY_IMPLEMENTATION.md) for security features
- Review [P0_IMPLEMENTATION_SUMMARY.md](P0_IMPLEMENTATION_SUMMARY.md) for implementation details
- See [COMPREHENSIVE_CODE_REVIEW.md](COMPREHENSIVE_CODE_REVIEW.md) for architecture overview
