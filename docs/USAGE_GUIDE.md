# LLMFed Usage Guide

## Overview

LLMFed is an AI Wrestling Federation Simulator that creates autonomous wrestling events with LLM-powered agents acting as wrestlers, referees, announcers, and other characters. The system operates on a tick-based simulation engine where AI agents make decisions and interact in real-time wrestling scenarios.

## Architecture

### Core Components

1. **API Gateway** (`api_gateway/main.py`) - REST API interface
2. **Core Engine** (`core_engine/`) - Simulation engine with tick-based processing
3. **Agent Service** (`agent_service/`) - Agent and federation management
4. **Models** (`models/`) - Data structures and database schemas
5. **LLM Abstraction** - Interface for various LLM providers

### Key Concepts

- **Federations**: Wrestling organizations that contain multiple agents
- **Agents**: AI-powered characters (wrestlers, referees, announcers, etc.)
- **Ticks**: Discrete time units where the simulation advances
- **Events**: Contexts where agents make decisions
- **Actions**: Decisions made by agents in response to events

## Getting Started

### Prerequisites

```bash
pip install fastapi uvicorn sqlalchemy pydantic httpx openai pytest
```

### Starting the Server

```bash
cd /path/to/LLMFed
python -m uvicorn api_gateway.main:app --host 0.0.0.0 --port 8091 --reload
```

The API will be available at `http://localhost:8091`

### Basic API Endpoints

#### Health Check
```bash
curl http://localhost:8091/health
```

#### Engine Status
```bash
curl http://localhost:8091/engine/debug
```

## API Reference

### Federation Management

#### Create Federation
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

#### List Federations
```bash
curl http://localhost:8091/federations
```

#### Get Federation Details
```bash
curl http://localhost:8091/federations/{federation_id}
```

### Agent Management

#### Create Agent
```bash
curl -X POST http://localhost:8091/agents \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user123",
    "name": "The Masked Marvel",
    "role": "participant",
    "gimmick_description": "A mysterious masked wrestler with incredible agility",
    "llm_config": {
      "model": "long-gemma",
      "temperature": 0.8,
      "gimmick": "masked hero",
      "personality_traits": {"brave": 80, "mysterious": 90}
    },
    "federation_id": "{federation_id}"
  }'
```

#### Get Agent Details
```bash
curl http://localhost:8091/agents/{agent_id}
```

#### Update Agent
```bash
curl -X PATCH http://localhost:8091/agents/{agent_id} \
  -H "Content-Type: application/json" \
  -d '{
    "gimmick_description": "Updated character description"
  }'
```

### Engine Control

#### Advance Simulation
```bash
curl -X POST "http://localhost:8091/engine/advance?n_ticks=5"
```

#### Get Engine Requests
```bash
curl http://localhost:8091/engine/requests
```

#### Get Narrative Logs
```bash
curl http://localhost:8091/engine/narrative?limit=50
```

#### Submit Promoter Hints
```bash
curl -X POST http://localhost:8091/prompter/hints \
  -H "Content-Type: application/json" \
  -d '{
    "context": {
      "requesting_agent_id": "agent123",
      "role": "participant",
      "available_actions": []
    },
    "hints": {
      "drama_level": "high",
      "storyline": "rivalry escalating"
    }
  }'
```

## Agent Configuration

### LLM Configuration Options

```json
{
  "model": "long-gemma",           // LLM model to use
  "temperature": 0.8,             // Creativity level (0.0-2.0)
  "max_tokens": 150,              // Response length limit
  "gimmick": "masked hero",       // Character archetype
  "personality_traits": {         // Character attributes
    "aggression": 70,
    "charisma": 85,
    "technical_skill": 60
  }
}
```

### Agent Roles

- **participant**: Main wrestlers who perform actions
- **referee**: Officials who make calls and enforce rules  
- **crowd**: Audience that reacts to events
- **announcer**: Commentators who provide play-by-play
- **promoter**: Organizers who influence storylines
- **backstage**: Behind-the-scenes characters

## Simulation Engine

### Tick Processing

The engine processes simulation in discrete ticks:

1. **Tick Initiation**: Engine advances to next tick
2. **Agent Selection**: Agents are processed by role order
3. **Context Generation**: Event context created for each agent
4. **LLM Interaction**: Agents receive context and choose actions
5. **Action Processing**: Actions validated and applied to game state
6. **State Update**: Game state updated with results
7. **Narrative Logging**: Events logged for playback

### Role Processing Order

1. **promoter** - Sets storyline direction
2. **participant** - Main character actions
3. **referee** - Official decisions
4. **crowd** - Audience reactions
5. **announcer** - Commentary
6. **backstage** - Supporting events

## Database Schema

### Tables

- **agents**: Agent definitions and configuration
- **federations**: Wrestling federation information
- **engine_requests**: Queued agent decisions
- **narrative_logs**: Event history and storytelling
- **matches**: Match definitions (future)
- **events**: Scheduled events (future)

### Key Relationships

```
federations -> agents (one-to-many)
agents -> engine_requests (one-to-many)
agents -> narrative_logs (one-to-many)
```

## Advanced Usage

### Custom LLM Integration

The system supports custom LLM providers by configuring environment variables:

```bash
export OPENAI_API_BASE="http://your-llm-server:8080/v1"
export OPENAI_API_KEY="your-api-key"
export OPENAI_MODEL="your-model-name"
```

### Webhook Notifications

Agents can register webhooks for event notifications:

```bash
curl -X POST "http://localhost:8091/agents/{agent_id}/subscribe?webhook_url=https://your-webhook.com/notify"
```

### Batch Operations

Create multiple agents for a full roster:

```bash
# Create multiple wrestlers with different gimmicks
for gimmick in "powerhouse" "high-flyer" "technician" "brawler"; do
  curl -X POST http://localhost:8091/agents \
    -H "Content-Type: application/json" \
    -d "{
      \"user_id\": \"user123\",
      \"name\": \"The $gimmick\",
      \"role\": \"participant\",
      \"gimmick_description\": \"A wrestling $gimmick specialist\",
      \"llm_config\": {\"model\": \"long-gemma\", \"gimmick\": \"$gimmick\"}
    }"
done
```

## Programming Interface

### Direct Engine Access

```python
from core_engine.engine import engine_instance

# Set promotional hints
engine_instance.set_hints({"storyline": "championship tournament"})

# Advance simulation
results = engine_instance.run_ticks(10)

# Process results
for result in results:
    print(f"Tick {result.time_index}: {result.agent_id} performed {result.applied_actions}")
```

### Database Queries

```python
from agent_service.database import SessionLocal
from models.db_models import AgentDB, FederationDB

db = SessionLocal()
try:
    # Get all agents in a federation
    agents = db.query(AgentDB).filter(AgentDB.federation_id == federation_id).all()
    
    # Get narrative history
    logs = db.query(NarrativeLogDB).order_by(NarrativeLogDB.created_at.desc()).limit(100).all()
finally:
    db.close()
```

## Testing

### Run Test Suite

```bash
python -m pytest tests/ -v
```

### Test Coverage Areas

- **CRUD Operations**: Agent and federation management
- **Engine Logic**: Tick processing and state management
- **LLM Integration**: Prompt building and response parsing
- **Heat System**: Crowd reaction mechanics
- **Rule Validation**: Action processing and game rules

### Current Test Status

✅ **Passing Tests (9/21)**:
- Agent CRUD operations
- Federation management
- Engine hint system
- Heat calculations
- Rule validation
- Tick scheduling

⚠️ **Needs Attention**:
- Multi-role tick processing
- LLM client error handling
- Prompt builder integration

## Deployment Considerations

### Production Setup

1. **Database**: Use PostgreSQL instead of SQLite
2. **Environment**: Set production environment variables
3. **Scaling**: Deploy with gunicorn or similar WSGI server
4. **Monitoring**: Implement logging and metrics collection
5. **Security**: Add authentication and rate limiting

### Environment Variables

```bash
# Database
DATABASE_URL="postgresql://user:pass@localhost/llmfed"

# LLM Configuration
OPENAI_API_KEY="your-openai-key"
OPENAI_MODEL="gpt-4"

# API Settings
API_HOST="0.0.0.0"
API_PORT="8091"
```

## Roadmap

### Immediate Enhancements

1. **Web Interface**: Frontend for managing federations and viewing matches
2. **Real-time Events**: WebSocket support for live match updates
3. **Enhanced Narrative**: Richer storytelling and match descriptions
4. **Match Scheduling**: Automated tournament and event creation

### Long-term Vision

1. **Multi-Federation Universe**: Cross-promotional events
2. **AI Storytelling**: Autonomous narrative generation
3. **Fan Interaction**: Community features and voting
4. **Broadcasting**: Automated match commentary and highlights

## Contributing

### Development Setup

1. Clone repository
2. Install dependencies: `pip install -r requirements.txt`
3. Run tests: `python -m pytest`
4. Start development server: `uvicorn api_gateway.main:app --reload`

### Code Structure

- Follow existing patterns for new endpoints
- Add tests for new functionality
- Update this guide for new features
- Maintain backward compatibility

## Support

For issues, feature requests, or contributions:

1. Check existing issues in the repository
2. Create detailed bug reports with reproduction steps
3. Submit pull requests with tests
4. Update documentation for new features

## License

This project is open source. See LICENSE file for details.