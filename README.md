# LLMFed - Federated Learning Management System with AI Agent Orchestration

[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

> An AI-powered wrestling federation simulator featuring autonomous LLM agents that create dynamic, emergent storytelling through tick-based simulation.

## 🎭 Overview

LLMFed is an innovative **Federated Learning Management System** that combines AI agent orchestration with professional wrestling simulation. The system creates autonomous wrestling events where Large Language Model (LLM) powered agents act as wrestlers, referees, announcers, promoters, and crowd members - each making intelligent, context-aware decisions that drive emergent narratives.

Unlike traditional simulation systems, LLMFed uses a **tick-based architecture** where AI agents process events in discrete time units, making decisions that influence the story, match outcomes, and character development in real-time.

### Key Features

- 🤖 **Multi-Agent AI System**: Six distinct agent roles (participants, referees, announcers, promoters, crowd, backstage)
- ⚡ **Tick-Based Simulation**: Discrete time-step processing for deterministic state management
- 🧠 **LLM Integration**: Support for multiple providers (OpenAI, Ollama, custom endpoints)
- 🎯 **Dynamic Storytelling**: Emergent narratives through agent interactions and decision-making
- 📊 **Heat System**: Sophisticated audience engagement metrics and momentum tracking
- 🔄 **RESTful API**: Complete FastAPI-based interface for programmatic control
- 🗄️ **Flexible Data Layer**: SQLAlchemy ORM with SQLite/PostgreSQL support
- 🎪 **Federation Management**: Create and manage multiple wrestling organizations
- 📝 **Narrative Logging**: Complete event history with playback capabilities

## 🏗️ Architecture

LLMFed follows a clean, modular architecture with clear separation of concerns:

```
┌─────────────────────────────────────────────────────────────┐
│                        API Gateway                          │
│              (FastAPI REST Endpoints)                       │
└────────────────────┬───────────────────────────────────────┘
                     │
        ┌────────────┼────────────┐
        │            │            │
┌───────▼──────┐ ┌──▼──────────┐ ┌▼────────────────┐
│ Agent Service│ │ Core Engine │ │ LLM Abstraction │
│              │ │             │ │                 │
│ - CRUD Ops   │ │ - Tick Loop │ │ - Multi-Provider│
│ - Federation │ │ - Scheduler │ │ - Prompt Build  │
│ - Database   │ │ - Heat Sys  │ │ - Response Parse│
└──────┬───────┘ └──────┬──────┘ └────────┬────────┘
       │                │                  │
       └────────────────┼──────────────────┘
                        │
                ┌───────▼────────┐
                │  Data Models   │
                │                │
                │ - Pydantic     │
                │ - SQLAlchemy   │
                │ - DB Schema    │
                └────────────────┘
```

### Core Components

#### 1. **API Gateway** (`api_gateway/`)
- FastAPI-based REST interface
- Endpoint definitions for all operations
- Request validation and error handling
- CORS configuration and middleware

#### 2. **Core Engine** (`core_engine/`)
- **Engine**: Tick-based simulation orchestrator
- **Scheduler**: Role-based agent processing order
- **Dispatcher**: Action selection and LLM coordination
- **RuleBook**: Game rule validation and enforcement
- **Heat System**: Audience engagement calculations
- **LLM Client**: Multi-provider LLM interface
- **Prompt Builder**: Context-aware prompt generation

#### 3. **Agent Service** (`agent_service/`)
- CRUD operations for agents and federations
- Database session management
- Business logic for agent lifecycle
- Data persistence and retrieval

#### 4. **Models** (`models/`)
- **entities.py**: Pydantic models for API validation
- **db_models.py**: SQLAlchemy ORM definitions
- Event contexts and action responses
- Federation and agent schemas

#### 5. **LLM Abstraction** (`llm_abstraction/`)
- Provider-agnostic LLM interface
- Support for OpenAI, Ollama, and custom endpoints
- Prompt templating and response parsing
- Graceful fallback handling

## 🚀 Quick Start

### Prerequisites

- Python 3.8 or higher
- pip package manager
- (Optional) PostgreSQL for production deployments
- (Optional) Ollama or OpenAI API access for LLM features

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/CrazyDubya/LLMFed.git
   cd LLMFed
   ```

2. **Create and activate virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment** (Optional)
   ```bash
   # For OpenAI
   export OPENAI_API_KEY="your-api-key"
   export OPENAI_MODEL="gpt-4"
   
   # For Ollama (local LLM)
   export OPENAI_API_BASE="http://127.0.0.1:11434/v1"
   export OPENAI_MODEL="long-gemma"
   
   # For PostgreSQL (production)
   export DATABASE_URL="postgresql://user:pass@localhost/llmfed"
   ```

5. **Initialize the database**
   ```bash
   python -c "from agent_service.database import init_db; init_db()"
   ```

6. **Start the server**
   ```bash
   uvicorn api_gateway.main:app --host 0.0.0.0 --port 8091 --reload
   ```

7. **Verify installation**
   ```bash
   curl http://localhost:8091/health
   ```

### Running Your First Simulation

#### Option 1: Using the Demo Script

```bash
python demo.py
```

#### Option 2: Using the API

```bash
# Create a federation
curl -X POST http://localhost:8091/federations \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Ultimate Wrestling Federation",
    "description": "The premier AI wrestling federation",
    "tier": 1,
    "owner_user_id": "user123"
  }'

# Create an agent (wrestler)
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
      "gimmick": "masked hero"
    },
    "federation_id": "<federation-id-from-above>"
  }'

# Advance the simulation
curl -X POST "http://localhost:8091/engine/advance?n_ticks=5"

# View narrative logs
curl http://localhost:8091/engine/narrative?limit=50
```

#### Option 3: Using Python

```python
import os
os.environ["OPENAI_MODEL"] = "long-gemma"
os.environ["OPENAI_API_BASE"] = "http://127.0.0.1:11434/v1"

from core_engine.engine import engine_instance

# Set promotional hints
engine_instance.set_hints({"storyline": "championship rivalry"})

# Run simulation ticks
results = engine_instance.run_ticks(10)

# Process results
for result in results:
    print(f"Tick {result.time_index}: Agent {result.agent_id}")
    for action in result.applied_actions:
        print(f"  - {action}")
```

## 📖 Documentation

- **[USAGE_GUIDE.md](USAGE_GUIDE.md)** - Comprehensive API reference and usage examples
- **[ANALYSIS.md](ANALYSIS.md)** - Technical analysis and architecture details
- **[ENHANCEMENT_PROPOSAL.md](ENHANCEMENT_PROPOSAL.md)** - Roadmap and planned features
- **[codebase.md](codebase.md)** - Detailed codebase documentation
- **[CONTRIBUTING.md](CONTRIBUTING.md)** - Contribution guidelines
- **[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)** - Community standards

### API Documentation

Once the server is running, interactive API documentation is available at:

- **Swagger UI**: http://localhost:8091/docs
- **ReDoc**: http://localhost:8091/redoc

## 🎮 Agent Roles

LLMFed supports six distinct agent roles, each with unique responsibilities:

| Role | Description | Processing Order |
|------|-------------|------------------|
| **Promoter** | Sets storyline direction and creative vision | 1st (Highest) |
| **Participant** | Main wrestlers who perform in-ring actions | 2nd |
| **Referee** | Officials who enforce rules and make calls | 3rd |
| **Crowd** | Audience members who react and influence heat | 4th |
| **Announcer** | Commentators providing play-by-play | 5th |
| **Backstage** | Supporting characters and storyline catalysts | 6th (Lowest) |

## 🔧 Configuration

### Environment Variables

```bash
# Database Configuration
DATABASE_URL="sqlite:///./llmfed.db"  # Default SQLite
# DATABASE_URL="postgresql://user:pass@localhost/llmfed"  # PostgreSQL

# LLM Configuration
OPENAI_API_KEY="your-api-key"
OPENAI_API_BASE="https://api.openai.com/v1"  # or custom endpoint
OPENAI_MODEL="gpt-4"

# Server Configuration
API_HOST="0.0.0.0"
API_PORT="8091"
LOG_LEVEL="INFO"
```

### LLM Agent Configuration

```python
{
  "model": "long-gemma",           # LLM model identifier
  "temperature": 0.8,              # Creativity (0.0-2.0)
  "max_tokens": 150,               # Response length limit
  "gimmick": "masked hero",        # Character archetype
  "personality_traits": {          # Custom attributes
    "aggression": 70,
    "charisma": 85,
    "technical_skill": 60
  }
}
```

## 🧪 Testing

Run the test suite:

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_engine.py -v

# Run with coverage
python -m pytest tests/ --cov=. --cov-report=html
```

### Test Coverage

- ✅ CRUD operations (agents, federations)
- ✅ Engine tick processing
- ✅ Heat calculations
- ✅ Rule validation
- ✅ LLM client integration
- ✅ Prompt building
- ⚠️ Multi-role interactions (in progress)

## 🗺️ Roadmap

### Short-term (v0.2.0)
- [ ] Web-based UI for federation management
- [ ] WebSocket support for real-time updates
- [ ] Enhanced narrative generation
- [ ] Match scheduling system

### Medium-term (v0.3.0)
- [ ] Multi-federation universe
- [ ] Tournament bracket generation
- [ ] Authentication and authorization
- [ ] Advanced analytics dashboard

### Long-term (v1.0.0)
- [ ] Fan interaction features
- [ ] Automated broadcasting system
- [ ] Cross-promotional events
- [ ] Mobile application

See [ENHANCEMENT_PROPOSAL.md](ENHANCEMENT_PROPOSAL.md) for detailed roadmap.

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for details on:

- Code of conduct
- Development setup
- Coding standards
- Pull request process
- Testing requirements

## 📊 Project Status

**Current Version**: 0.1.0 (Alpha)

- ✅ Core engine functional
- ✅ API gateway operational
- ✅ Database layer complete
- ✅ LLM integration working
- ⚠️ Test coverage improving
- 🔄 Documentation ongoing

## 🐛 Known Issues

- Multi-role tick processing needs optimization
- Pydantic v2 deprecation warnings to address
- WebSocket support not yet implemented
- Authentication system pending

See [Issues](https://github.com/CrazyDubya/LLMFed/issues) for full list.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- FastAPI for the excellent web framework
- SQLAlchemy for robust ORM capabilities
- The LLM community for model development
- Contributors and testers

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/CrazyDubya/LLMFed/issues)
- **Discussions**: [GitHub Discussions](https://github.com/CrazyDubya/LLMFed/discussions)
- **Documentation**: [Project Wiki](https://github.com/CrazyDubya/LLMFed/wiki)

## 🌟 Star History

If you find LLMFed useful, please consider starring the repository!

---

**Built with ❤️ by the LLMFed community**
