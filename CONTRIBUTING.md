# Contributing to LLMFed

Thank you for your interest in contributing to LLMFed! This document provides guidelines and information for contributors to help maintain code quality and ensure a smooth collaboration process.

## 📋 Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Contributing Process](#contributing-process)
- [Coding Standards](#coding-standards)
- [Testing Guidelines](#testing-guidelines)
- [Documentation](#documentation)
- [Issue Guidelines](#issue-guidelines)
- [Pull Request Process](#pull-request-process)
- [Release Process](#release-process)

## 🤝 Code of Conduct

This project adheres to a [Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code. Please report unacceptable behavior to the project maintainers.

## 🚀 Getting Started

### Prerequisites

- Python 3.8 or higher
- Git
- Basic understanding of FastAPI, SQLAlchemy, and async programming
- Familiarity with LLM concepts (helpful but not required)

### Areas for Contribution

We welcome contributions in several areas:

- **Core Engine**: Simulation logic, tick processing, agent orchestration
- **API Development**: New endpoints, improved validation, error handling
- **LLM Integration**: New providers, prompt optimization, response parsing
- **Database**: Schema improvements, migrations, performance optimization
- **Testing**: Unit tests, integration tests, performance tests
- **Documentation**: API docs, tutorials, examples, architecture guides
- **Frontend**: Web UI development (future)
- **DevOps**: CI/CD, deployment, monitoring

## 🛠️ Development Setup

### 1. Fork and Clone

```bash
# Fork the repository on GitHub, then clone your fork
git clone https://github.com/YOUR_USERNAME/LLMFed.git
cd LLMFed

# Add upstream remote
git remote add upstream https://github.com/CrazyDubya/LLMFed.git
```

### 2. Environment Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install development dependencies
pip install pytest pytest-cov black flake8 mypy pre-commit
```

### 3. Database Initialization

```bash
# Initialize the database
python -c "from agent_service.database import init_db; init_db()"
```

### 4. Environment Configuration

Create a `.env` file for local development:

```bash
# Database
DATABASE_URL=sqlite:///./llmfed_dev.db

# LLM Configuration (choose one)
# For OpenAI
OPENAI_API_KEY=your-api-key
OPENAI_MODEL=gpt-4

# For Ollama (local)
OPENAI_API_BASE=http://127.0.0.1:11434/v1
OPENAI_MODEL=long-gemma

# Development Settings
LOG_LEVEL=DEBUG
API_HOST=127.0.0.1
API_PORT=8091
```

### 5. Verify Setup

```bash
# Run tests
python -m pytest tests/ -v

# Start development server
uvicorn api_gateway.main:app --reload --port 8091

# Test API
curl http://localhost:8091/health
```

## 🔄 Contributing Process

### 1. Choose or Create an Issue

- Browse [existing issues](https://github.com/CrazyDubya/LLMFed/issues)
- Look for issues labeled `good first issue` or `help wanted`
- Create a new issue if needed (see [Issue Guidelines](#issue-guidelines))
- Comment on the issue to indicate you're working on it

### 2. Create a Feature Branch

```bash
# Update your fork
git checkout master
git pull upstream master

# Create feature branch
git checkout -b feature/your-feature-name
# or
git checkout -b fix/issue-number-description
```

### 3. Make Changes

- Follow the [Coding Standards](#coding-standards)
- Write tests for new functionality
- Update documentation as needed
- Commit changes with clear messages

### 4. Test Your Changes

```bash
# Run full test suite
python -m pytest tests/ -v

# Run specific tests
python -m pytest tests/test_your_module.py -v

# Check code coverage
python -m pytest tests/ --cov=. --cov-report=html

# Run linting
flake8 .
black --check .
mypy .
```

### 5. Submit Pull Request

- Push your branch to your fork
- Create a pull request against the main repository
- Follow the [Pull Request Process](#pull-request-process)

## 📝 Coding Standards

### Python Style Guide

We follow [PEP 8](https://pep8.org/) with some modifications:

- **Line Length**: 88 characters (Black default)
- **Imports**: Use absolute imports, group by standard/third-party/local
- **Docstrings**: Use Google-style docstrings
- **Type Hints**: Required for all public functions and methods

### Code Formatting

We use [Black](https://black.readthedocs.io/) for code formatting:

```bash
# Format code
black .

# Check formatting
black --check .
```

### Linting

We use [flake8](https://flake8.pycqa.org/) for linting:

```bash
# Run linter
flake8 .
```

Configuration in `setup.cfg`:
```ini
[flake8]
max-line-length = 88
extend-ignore = E203, W503
exclude = venv, __pycache__, .git
```

### Type Checking

We use [mypy](http://mypy-lang.org/) for static type checking:

```bash
# Run type checker
mypy .
```

### Example Code Style

```python
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging

from pydantic import BaseModel
from sqlalchemy.orm import Session

from models.entities import Agent, AgentCreateData
from models.db_models import AgentDB


logger = logging.getLogger(__name__)


class AgentService:
    """Service for managing wrestling agents.
    
    This service provides CRUD operations for agents and handles
    the business logic for agent lifecycle management.
    """
    
    def __init__(self, db: Session) -> None:
        """Initialize the agent service.
        
        Args:
            db: Database session for operations.
        """
        self.db = db
    
    def create_agent(
        self, 
        agent_data: AgentCreateData,
        federation_id: Optional[str] = None
    ) -> Agent:
        """Create a new agent.
        
        Args:
            agent_data: Agent creation data.
            federation_id: Optional federation to assign agent to.
            
        Returns:
            Created agent instance.
            
        Raises:
            ValueError: If agent data is invalid.
            DatabaseError: If database operation fails.
        """
        try:
            # Implementation here
            pass
        except Exception as e:
            logger.error(f"Failed to create agent: {e}")
            raise
```

## 🧪 Testing Guidelines

### Test Structure

```
tests/
├── __init__.py
├── conftest.py              # Pytest fixtures
├── test_agent_service.py    # Agent service tests
├── test_core_engine.py      # Engine tests
├── test_api_gateway.py      # API endpoint tests
├── integration/             # Integration tests
│   ├── __init__.py
│   └── test_full_workflow.py
└── fixtures/                # Test data
    ├── __init__.py
    └── sample_data.py
```

### Writing Tests

```python
import pytest
from unittest.mock import Mock, patch
from sqlalchemy.orm import Session

from agent_service.crud import create_agent
from models.entities import AgentCreateData
from tests.fixtures.sample_data import sample_agent_data


class TestAgentCRUD:
    """Test suite for agent CRUD operations."""
    
    def test_create_agent_success(self, db_session: Session) -> None:
        """Test successful agent creation."""
        # Arrange
        agent_data = AgentCreateData(**sample_agent_data)
        
        # Act
        result = create_agent(db_session, agent_data)
        
        # Assert
        assert result.name == agent_data.name
        assert result.role == agent_data.role
        assert result.agent_id is not None
    
    def test_create_agent_invalid_data(self, db_session: Session) -> None:
        """Test agent creation with invalid data."""
        # Arrange
        invalid_data = AgentCreateData(name="", role="invalid")
        
        # Act & Assert
        with pytest.raises(ValueError):
            create_agent(db_session, invalid_data)
    
    @patch('core_engine.llm_client.LLMClient.generate')
    def test_agent_llm_interaction(self, mock_generate: Mock) -> None:
        """Test agent LLM interaction."""
        # Arrange
        mock_generate.return_value = {"action": "grapple", "target": "opponent"}
        
        # Act & Assert
        # Test implementation
```

### Test Categories

1. **Unit Tests**: Test individual functions and methods
2. **Integration Tests**: Test component interactions
3. **API Tests**: Test HTTP endpoints
4. **Database Tests**: Test data persistence
5. **LLM Tests**: Test AI integration (with mocking)

### Running Tests

```bash
# Run all tests
python -m pytest

# Run with verbose output
python -m pytest -v

# Run specific test file
python -m pytest tests/test_agent_service.py

# Run specific test
python -m pytest tests/test_agent_service.py::TestAgentCRUD::test_create_agent_success

# Run with coverage
python -m pytest --cov=. --cov-report=html

# Run only fast tests (skip slow integration tests)
python -m pytest -m "not slow"
```

## 📚 Documentation

### Types of Documentation

1. **Code Documentation**: Docstrings, type hints, comments
2. **API Documentation**: OpenAPI/Swagger (auto-generated)
3. **User Documentation**: README, usage guides, tutorials
4. **Developer Documentation**: Architecture, contributing guides
5. **Deployment Documentation**: Installation, configuration

### Docstring Style

Use Google-style docstrings:

```python
def process_agent_action(
    agent_id: str, 
    context: EventContext, 
    timeout: float = 30.0
) -> AgentActionResponse:
    """Process an agent's action in response to an event context.
    
    This function sends the event context to the specified agent's LLM
    and processes the response according to the game rules.
    
    Args:
        agent_id: Unique identifier for the agent.
        context: Event context containing available actions and game state.
        timeout: Maximum time to wait for LLM response in seconds.
        
    Returns:
        Validated agent action response.
        
    Raises:
        AgentNotFoundError: If agent_id doesn't exist.
        LLMTimeoutError: If LLM doesn't respond within timeout.
        ValidationError: If agent response is invalid.
        
    Example:
        >>> context = EventContext(
        ...     requesting_agent_id="agent_123",
        ...     role="participant",
        ...     available_actions=[PossibleAction(name="grapple", description="...")]
        ... )
        >>> response = process_agent_action("agent_123", context)
        >>> print(response.chosen_action)
        "grapple"
    """
```

### API Documentation

- API docs are auto-generated from FastAPI
- Add detailed descriptions to endpoint functions
- Include example requests/responses
- Document error codes and responses

## 🐛 Issue Guidelines

### Before Creating an Issue

1. Search existing issues to avoid duplicates
2. Check if it's already fixed in the latest version
3. Gather relevant information (logs, environment, steps to reproduce)

### Issue Types

#### Bug Reports

Use the bug report template:

```markdown
**Bug Description**
A clear description of the bug.

**Steps to Reproduce**
1. Go to '...'
2. Click on '....'
3. Scroll down to '....'
4. See error

**Expected Behavior**
What you expected to happen.

**Actual Behavior**
What actually happened.

**Environment**
- OS: [e.g. Ubuntu 20.04]
- Python Version: [e.g. 3.9.7]
- LLMFed Version: [e.g. 0.1.0]
- LLM Provider: [e.g. OpenAI GPT-4]

**Additional Context**
- Error logs
- Screenshots
- Configuration files (redacted)
```

#### Feature Requests

```markdown
**Feature Description**
A clear description of the feature you'd like to see.

**Use Case**
Describe the problem this feature would solve.

**Proposed Solution**
Describe how you envision this feature working.

**Alternatives Considered**
Other approaches you've considered.

**Additional Context**
Any other context, mockups, or examples.
```

#### Questions

```markdown
**Question**
What would you like to know?

**Context**
What are you trying to accomplish?

**What You've Tried**
Steps you've already taken to find the answer.
```

## 🔀 Pull Request Process

### PR Checklist

Before submitting a pull request, ensure:

- [ ] Code follows the style guidelines
- [ ] Tests pass (`python -m pytest`)
- [ ] New functionality includes tests
- [ ] Documentation is updated
- [ ] Commit messages are clear and descriptive
- [ ] PR description explains the changes
- [ ] No merge conflicts with master branch

### PR Template

```markdown
## Description
Brief description of changes made.

## Type of Change
- [ ] Bug fix (non-breaking change that fixes an issue)
- [ ] New feature (non-breaking change that adds functionality)
- [ ] Breaking change (fix or feature that causes existing functionality to change)
- [ ] Documentation update

## Testing
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Manual testing completed

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Documentation updated
- [ ] Tests added for new functionality

## Related Issues
Fixes #(issue number)
```

### Review Process

1. **Automated Checks**: CI/CD pipeline runs tests and linting
2. **Code Review**: Maintainers review code for quality and design
3. **Testing**: Reviewers may test functionality manually
4. **Approval**: At least one maintainer approval required
5. **Merge**: Maintainer merges after all checks pass

### Addressing Review Comments

- Respond to all review comments
- Make requested changes in new commits
- Push updates to the same branch
- Request re-review when ready

## 🚀 Release Process

### Versioning

We follow [Semantic Versioning](https://semver.org/):

- **MAJOR**: Breaking changes
- **MINOR**: New features (backward compatible)
- **PATCH**: Bug fixes (backward compatible)

### Release Checklist

1. Update version numbers
2. Update CHANGELOG.md
3. Run full test suite
4. Create release branch
5. Tag release
6. Update documentation
7. Deploy to production (if applicable)

## 🏷️ Labels and Milestones

### Issue Labels

- `bug`: Something isn't working
- `enhancement`: New feature or request
- `documentation`: Improvements or additions to documentation
- `good first issue`: Good for newcomers
- `help wanted`: Extra attention is needed
- `question`: Further information is requested
- `wontfix`: This will not be worked on
- `duplicate`: This issue or pull request already exists
- `invalid`: This doesn't seem right

### Priority Labels

- `priority: critical`: Critical issues that need immediate attention
- `priority: high`: High priority issues
- `priority: medium`: Medium priority issues
- `priority: low`: Low priority issues

### Component Labels

- `component: api`: API Gateway related
- `component: engine`: Core Engine related
- `component: database`: Database related
- `component: llm`: LLM integration related
- `component: tests`: Testing related

## 💬 Communication

### Channels

- **GitHub Issues**: Bug reports, feature requests
- **GitHub Discussions**: General questions, ideas
- **Pull Requests**: Code review, implementation discussion

### Communication Guidelines

- Be respectful and constructive
- Provide context and details
- Use clear, descriptive titles
- Tag relevant people when appropriate
- Follow up on your contributions

## 🎯 Getting Help

### For Contributors

- Read existing documentation
- Check GitHub Issues and Discussions
- Look at existing code for patterns
- Ask questions in GitHub Discussions

### For Maintainers

- Review PRs promptly
- Provide constructive feedback
- Help newcomers get started
- Keep documentation updated

## 🙏 Recognition

Contributors are recognized in:

- README.md contributors section
- Release notes
- GitHub contributors page
- Special recognition for significant contributions

Thank you for contributing to LLMFed! Your efforts help make this project better for everyone.