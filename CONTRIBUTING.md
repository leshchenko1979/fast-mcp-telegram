# 🤝 Contributing to fast-mcp-telegram

Thank you for your interest in contributing to fast-mcp-telegram! This document provides comprehensive guidelines for developers who want to contribute to the project.

> **🧠 Recommended for AI-Assisted Development**: This project uses a **Memory Bank system** for knowledge management. While not mandatory, it's **highly recommended for developers using AI coding agents** (like Cursor, Claude, or GitHub Copilot) to ensure consistent understanding and better collaboration. See the [Memory Bank System](#-memory-bank-system) section below for details.

## 📋 Table of Contents

- [🚀 Getting Started](#-getting-started)
- [💻 Development Setup](#-development-setup)
- [🧪 Testing](#-testing)
- [🛠️ Development Workflow](#-development-workflow)
- [📦 Dependencies](#-dependencies)
- [🔧 Code Quality](#-code-quality)
- [🔐 Session Management Architecture](#-session-management-architecture)
- [📝 Contributing Guidelines](#-contributing-guidelines)
- [🧠 Memory Bank System](#-memory-bank-system)
- [🚀 Deployment](#-deployment)

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.10+**
- **Git**
- **Telegram API credentials** ([get them here](https://my.telegram.org/auth))
- **MCP-compatible client** (Cursor, Claude Desktop, etc.)

### Quick Setup

```bash
# 1. Fork and clone the repository
git clone https://github.com/your-username/fast-mcp-telegram.git
cd fast-mcp-telegram

# 2. (Optional for AI-assisted development) Read the Memory Bank
# 💡 Recommended: Read key memory-bank files for better AI collaboration
# cat memory-bank/projectbrief.md
# cat memory-bank/activeContext.md

# 3. Set up development environment
pip install -e .[dev]

# 4. Configure environment
echo "API_ID=your_api_id" > .env
echo "API_HASH=your_api_hash" >> .env
echo "PHONE_NUMBER=+123456789" >> .env
# Edit .env with your actual credentials

# 5. Authenticate with Telegram
python src/setup_telegram.py

# 6. Run tests
pytest tests/
```

---

## 💻 Development Setup

### 1. Clone and Setup

```bash
git clone https://github.com/leshchenko1979/fast-mcp-telegram.git
cd fast-mcp-telegram
pip install -e .[dev]  # Install all dependencies including dev tools
```

### 2. Authenticate with Telegram

**Setup Command Options:**

```bash
# Automatic .env file loading (recommended)
echo "API_ID=your_api_id" > .env
echo "API_HASH=your_api_hash" >> .env
echo "PHONE_NUMBER=+123456789" >> .env
python src/setup_telegram.py

# Using CLI arguments
python src/setup_telegram.py --api-id="your_api_id" --api-hash="your_api_hash" --phone="+123456789"

# Using environment variables
API_ID="your_api_id" API_HASH="your_api_hash" PHONE_NUMBER="+123456789" \
python src/setup_telegram.py

# Additional options available:
# --overwrite          # Auto-overwrite existing session
# --session-name NAME  # Use custom session name
```

**📝 Note:** The setup script automatically loads `.env` files from the project directory if they exist, making authentication seamless.

### 3. Configure Your MCP Client

```json
{
  "mcpServers": {
    "telegram": {
      "command": "python3",
      "args": ["src/server.py"],
      "cwd": "/path/to/fast-mcp-telegram"
    }
  }
}
```

### 4. Start Using!

```json
{"tool": "search_messages", "params": {"query": "hello", "limit": 5}}
{"tool": "send_or_edit_message", "params": {"chat_id": "me", "message": "Hello from AI!"}}
```

**ℹ️ Session Info:** Your Telegram session is saved to `~/.config/fast-mcp-telegram/telegram.session` (one-time setup)

---

## 🧪 Testing

### Test Structure

```
tests/
├── __init__.py                    # Tests package initialization
├── conftest.py                    # Shared fixtures and configuration
├── test_*.py                      # Organized test modules by functionality
└── README.md                      # Test documentation and guidelines
```

### Running Tests

#### All Tests
```bash
# From project root
pytest tests/

# Verbose output
pytest tests/ -v

# Coverage report
pytest tests/ --cov=src --cov-report=html

# Parallel execution
pytest tests/ -n auto
```

### Running Tests Locally
```bash
# Install test dependencies
pip install pytest pytest-asyncio pytest-cov pytest-xdist

# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html

# Open coverage report in browser
open htmlcov/index.html
```

### Test Guidelines

- **Unit Tests**: Test individual functions and classes
- **Integration Tests**: Test MCP tool functionality
- **Mocking**: Use fixtures for external dependencies (Telegram API)
- **Coverage**: Aim for >80% code coverage
- **CI/CD**: Tests run automatically on pull requests

---

## 🛠️ Development Workflow

### Code Quality Tools

```bash
# Format code
ruff format .

# Lint code
ruff check .

# Type checking
mypy src/

# Run tests with coverage
pytest tests/ --cov=src --cov-report=html

# Run all checks
ruff format . && ruff check . && mypy src/
```

### Development Commands

```bash
# Install dev dependencies
pip install -e .[dev]

# Format code
ruff format .

# Lint code
ruff check .

# Test server
python src/server.py

# Run specific test
pytest tests/test_specific.py -v

# Development server with auto-reload
uvicorn src.server:app --reload
```

---

## 📦 Dependencies

### Core Dependencies

| Package | Purpose |
|---------|---------|
| **fastmcp** | MCP server framework |
| **telethon** | Telegram API client |
| **loguru** | Structured logging |
| **aiohttp** | Async HTTP client |
| **python-dotenv** | Environment management |

### Development Dependencies

| Package | Purpose |
|---------|---------|
| **pytest** | Testing framework |
| **pytest-asyncio** | Async testing support |
| **pytest-cov** | Coverage reporting |
| **ruff** | Code formatting and linting |
| **mypy** | Type checking |

**Installation:** `pip install -e .[dev]` (dependencies managed via `pyproject.toml`)

### Dependency Management

- **pyproject.toml**: Main dependency configuration with setuptools
- **requirements.txt**: Optional lock file for reproducible builds
- **pip**: Standard Python package manager
- **Dependabot**: Automated dependency updates
- **Security**: Regular security audits of dependencies

### Package Management

This project uses **setuptools** and **pip** for dependency management:
- **Standard Python tooling**: Uses setuptools.build_meta as build backend
- **Reproducible builds**: pyproject.toml ensures consistent environments
- **Docker optimization**: Multi-stage builds optimized for pip installations
- **Cross-platform compatibility**: Works on all platforms with standard Python tooling

---

## 🔧 Code Quality

### Code Style

- **Formatter**: Ruff (fast, comprehensive)
- **Linting**: Ruff rules + custom rules
- **Type Hints**: Full type coverage required
- **Docstrings**: Google-style docstrings for all public functions

### Commit Messages

We follow conventional commit format:

```
type(scope): description

[optional body]

[optional footer]
```

**Types:**
- `feat`: New features
- `fix`: Bug fixes
- `docs`: Documentation
- `style`: Code style changes
- `refactor`: Code refactoring
- `test`: Testing
- `chore`: Maintenance

**Examples:**
```
feat(auth): add multi-user Bearer token authentication
fix(tools): resolve message search timeout issue
docs(readme): update installation instructions
```

---

## 🔐 Session Management Architecture

### Overview
This project uses a sophisticated session management system that supports both single-user and multi-user deployments with automatic session isolation and persistence.

### Key Features
- **Token-Based Authentication**: Bearer tokens create isolated user sessions
- **LRU Cache Management**: Configurable `MAX_ACTIVE_SESSIONS` limit with automatic eviction
- **Session Persistence**: Sessions stored in `~/.config/fast-mcp-telegram/` for cross-platform compatibility
- **Automatic Cleanup**: Invalid session files are automatically deleted
- **Cross-Platform Support**: Handles macOS resource forks and permission differences

### Session Files
- **Location**: `~/.config/fast-mcp-telegram/`
- **Format**: `{token}.session` for multi-user isolation
- **Security**: Session files are excluded from version control
- **Permissions**: Automatic permission fixing for container user access (1000:1000)

### Authentication Flow
```
HTTP Request → extract_bearer_token() → @with_auth_context → set_request_token() → _get_client_by_token() → Session Cache/New Session → Tool Execution
```

### Development Notes
- Use `DISABLE_AUTH=true` for development mode (bypasses authentication)
- Session files are automatically backed up and restored across deployments
- The system handles session conflicts and provides clear error messages

---

## 📝 Contributing Guidelines

### Development Process

1. **Fork the repository**
2. **Create a feature branch**: `git checkout -b feature/amazing-feature`
3. **Make your changes**
4. **Add tests** for new functionality
5. **Run the test suite**: `pytest tests/`
6. **Format and lint**: `ruff format . && ruff check . && mypy src/`
7. **Commit changes**: `git commit -m 'feat: add amazing feature'`
8. **Push to branch**: `git push origin feature/amazing-feature`
9. **Open a Pull Request**

**For AI-assisted development:** Consider reading `memory-bank/` files and updating them when making architectural decisions to improve collaboration between you and your AI coding assistant.

### Memory Bank System

This project uses a comprehensive **Memory Bank system** to maintain project knowledge, architectural decisions, and development context. While not mandatory for all contributors, it's **highly recommended for developers using AI coding agents** to ensure better collaboration and consistent understanding of the project state.

#### 📚 What is the Memory Bank?

The Memory Bank is a structured documentation system located in the `memory-bank/` directory that serves as the project's institutional memory:

```
memory-bank/
├── projectbrief.md      # Core requirements and project goals
├── productContext.md    # User experience and problem-solving focus
├── activeContext.md     # Current work focus and active decisions
├── systemPatterns.md    # Architecture and technical patterns
├── techContext.md       # Technologies, setup, and technical constraints
└── progress.md          # What's working and what needs to be built
```

#### 🧠 Why Use the Memory Bank?

The Memory Bank system provides significant benefits, especially for **AI-assisted development**:

- **AI Context Awareness**: Gives AI coding agents (like Cursor, Claude, GitHub Copilot) access to project-specific knowledge and architectural decisions
- **Consistent Understanding**: Ensures AI assistants have the same context and understanding as human developers
- **Knowledge Preservation**: Prevents loss of important decisions and architectural context over time
- **Better AI Suggestions**: Enables AI tools to provide more accurate and relevant code suggestions
- **Collaborative Development**: Provides shared understanding across both human and AI-assisted development
- **Faster Onboarding**: New contributors (and their AI assistants) can quickly understand the project state
- **Reduced Technical Debt**: Maintains clear project history and architectural decisions

#### 📝 Memory Bank Workflow (Recommended)

For the best experience with AI-assisted development, consider this workflow:

**Before starting work:**
1. **Read key memory bank files** to understand current state (`projectbrief.md`, `activeContext.md`)
2. **Check systemPatterns.md** for architectural guidelines
3. **Review techContext.md** for technical constraints

**During development:**
1. **Document major decisions** in `activeContext.md` when making architectural choices
2. **Update progress.md** when completing significant features
3. **Note architectural changes** in `systemPatterns.md` for future reference
4. **Update techContext.md** when technical approaches change

**When your work is complete:**
1. **Consider updating progress.md** to reflect new capabilities
2. **Document architectural insights** in `systemPatterns.md` if discovered
3. **Archive completed work** from `activeContext.md` to `progress.md`

#### 🔍 Memory Bank Reading Order

1. **projectbrief.md** - Foundation & scope (read first)
2. **productContext.md** - Why & how (read second)
3. **activeContext.md** - Current focus (read third)
4. **systemPatterns.md** - Architecture (read fourth)
5. **techContext.md** - Technology setup (read fifth)
6. **progress.md** - Status & evolution (read last)

#### 📋 Memory Bank Update Guidelines (Best Practices)

When updating the Memory Bank, consider these best practices:

- **Read essential files** (`projectbrief.md`, `activeContext.md`) before major work
- **Document significant decisions** when they impact project architecture
- **Be specific** - include rationale, implementation details, and impact
- **Use dates** - timestamp entries when adding them (YYYY-MM-DD format)
- **Consider archiving** completed work from activeContext to progress when appropriate
- **Focus on current state** - document what's been done rather than future plans

#### 💡 Memory Bank Benefits for AI-Assisted Development

**For developers using AI coding agents, the Memory Bank provides:**

- **Better AI Context**: AI assistants can provide more relevant suggestions with project-specific knowledge
- **Consistent Collaboration**: Both human and AI contributors work from the same understanding
- **Improved Code Quality**: AI suggestions align better with established project patterns
- **Faster Development**: Reduced time spent explaining project context to AI assistants
- **Knowledge Continuity**: Project understanding persists across development sessions

#### 🔧 Memory Bank Integration with AI Coding Agents

**Cursor IDE (Recommended):**
- Memory Bank rules are **automatically applied** to AI agents in Cursor
- No additional setup required - the AI agent will use the memory bank by default
- If rules are not auto-applied, instruct the AI agent: **"use the memory bank"** or **"update the memory bank"**

**Other IDEs (VS Code, etc.):**
- Copy the memory bank rules to your IDE's AI configuration path
- Ensure your AI extension/plugin can access the `memory-bank/` directory
- Configure your AI agent to reference memory bank files when making suggestions

**Contributors using AI tools are encouraged to:**
- 📖 Read memory bank files to understand project context
- ✏️ Update memory bank when making architectural decisions
- 🤝 Share insights that help both human and AI collaborators
- 🔧 Ensure AI agents are properly configured to use the memory bank

### Pull Request Requirements

- **Tests**: All new code must include tests
- **Documentation**: Update docs for API changes
- **Code Review**: Required for all PRs
- **CI/CD**: All checks must pass
- **Conventional Commits**: Follow commit message format
- **Memory Bank Updates**: Consider updating memory bank files for architectural changes (especially beneficial for AI-assisted development)

### Issue Guidelines

- **Bug Reports**: Use the bug report template
- **Feature Requests**: Use the feature request template
- **Questions**: Check existing issues first
- **Reproduction**: Provide minimal reproduction case

### Code Review Process

1. **Automated Checks**: CI runs tests, linting, formatting
2. **Peer Review**: At least one maintainer review required
3. **Approval**: Code owner approval for major changes
4. **Merge**: Squash merge with descriptive commit message

---

## 🚀 Deployment

### Development Deployment

#### Local Development
```bash
# Run in development mode
python src/server.py

# With environment variables
DEBUG=true python src/server.py

# Development with stdio transport (single-user)
python src/server.py  # Uses stdio transport by default
```

#### Docker Development
```bash
# Build development image
docker build -t fast-mcp-telegram:dev .

# Run with hot reload and volume mounting
docker run -v $(pwd):/app -p 8000:8000 fast-mcp-telegram:dev

# Development with Docker Compose
docker compose -f docker-compose.dev.yml up
```

### Production Deployment

#### Docker Compose Production
```bash
# Production deployment with session persistence
docker compose --profile server up -d

# Check deployment status
docker compose ps

# View logs
docker compose logs -f fast-mcp-telegram
```

#### Key Production Features
- **Session Persistence**: Automatic backup/restore across deployments
- **Cross-Platform Compatibility**: Handles macOS, Linux, and Windows
- **Permission Auto-Fix**: Automatic container user permission management
- **Health Monitoring**: Comprehensive container health checks
- **Security Hardened**: Session files excluded from version control

#### Deployment Architecture
- **Transport**: HTTP with SSE mounted at `/mcp`
- **Ingress**: Traefik with Let's Encrypt TLS certificates
- **Sessions**: Persistent storage in `~/.config/fast-mcp-telegram/`
- **Volume Mounting**: Optimized directory mounts for session files
- **Multi-User Support**: Bearer token authentication for isolation

#### Environment Configuration
```bash
# Production environment variables
MCP_TRANSPORT=http          # HTTP transport for production
MCP_HOST=0.0.0.0           # Bind to all interfaces
MCP_PORT=8000              # Service port
MAX_ACTIVE_SESSIONS=10     # LRU cache limit
DISABLE_AUTH=false         # Enable authentication in production
```

See [README.md](README.md) for detailed production deployment instructions including remote server deployment and domain configuration.

---

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/leshchenko1979/fast-mcp-telegram/issues)
- **Discussions**: [GitHub Discussions](https://github.com/leshchenko1979/fast-mcp-telegram/discussions)
- **Community**: [Telegram Community](https://t.me/mcp_telegram)

## 📄 License

By contributing to this project, you agree that your contributions will be licensed under the same license as the project (MIT License).

---

<div align="center">

**Thank you for contributing to fast-mcp-telegram! 🚀**

*Your contributions help make AI-Telegram integration better for everyone.*

</div>