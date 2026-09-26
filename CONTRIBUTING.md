# 🤝 Contributing to fast-mcp-telegram

Thank you for your interest in contributing to fast-mcp-telegram! This document provides comprehensive guidelines for developers who want to contribute to the project.

## 📋 Table of Contents

- [🎯 Design Philosophy](#-design-philosophy)
- [🚀 Getting Started](#-getting-started)
- [💻 Development Setup](#-development-setup)
- [🧪 Testing](#-testing)
- [🛠️ Development Workflow](#-development-workflow)
- [📦 Dependencies](#-dependencies)
- [🔧 Code Quality](#-code-quality)
- [🔐 Session Management Architecture](#-session-management-architecture)
- [📝 Contributing Guidelines](#-contributing-guidelines)

---

## 🎯 Design Philosophy

This MCP server is designed to **save context space for LLMs** by providing general-purpose tools rather than many narrow-purpose ones. Each tool description and the full tool list consume AI context; fewer, more capable tools reduce that cost. We accept more parameters per tool and slightly more complex signatures in exchange for fewer tools and less context.

**Guidelines for contributors:**

- **Prefer extending over adding**: Before proposing a new tool, consider whether the capability can be added as a parameter or mode to an existing tool (e.g. `get_messages` consolidates search, browse, read-by-ID, and replies).
- **Use `invoke_mtproto` as the escape hatch**: Rare or advanced operations can go through `invoke_mtproto` instead of dedicated tools. Propose new tools only when they meaningfully simplify LLM usage beyond what parameters + `invoke_mtproto` can achieve.
- **Keep tool descriptions concise**: Tool names and descriptions are part of the AI's context. Be direct; avoid redundant prose.
- **Maintain uniform schemas**: Consistent response shapes (e.g. `build_entity_dict`, `build_message_result`) reduce the need for per-tool documentation and enable automatic processing of responses when possible.

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.11+**
- **Git**
- **Telegram API credentials** ([get them here](https://my.telegram.org/auth))
- **MCP-compatible client** (Cursor, Claude Desktop, etc.)

### Quick Setup

```bash
# 1. Fork and clone the repository
git clone https://github.com/your-username/fast-mcp-telegram.git
cd fast-mcp-telegram

# 2. Set up development environment
pip install -e .[dev]

# 3. Configure environment
echo "API_ID=your_api_id" > .env
echo "API_HASH=your_api_hash" >> .env
echo "PHONE_NUMBER=+123456789" >> .env
# Edit .env with your actual credentials

# 4. Authenticate with Telegram
python -m src.cli_setup

# 5. Run tests
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
python -m src.cli_setup

# Using CLI arguments
python -m src.cli_setup --api-id="your_api_id" --api-hash="your_api_hash" --phone-number="+123456789"

# Using environment variables
API_ID="your_api_id" API_HASH="your_api_hash" PHONE_NUMBER="+123456789" \
python -m src.cli_setup

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
      "command": "uvx",
      "args": ["fast-mcp-telegram"],
      "cwd": "/path/to/fast-mcp-telegram"
    }
  }
}
```

### Development with telegram-dev MCP (Cursor IDE)

Use **telegram-dev** in [`.cursor/mcp.json`](.cursor/mcp.json) for day-to-day stdio development (no ACL):

```json
{
  "mcpServers": {
    "telegram-dev": {
      "command": "python3",
      "args": ["-m", "src.server"],
      "cwd": "/path/to/fast-mcp-telegram"
    }
  }
}
```

- Auth disabled; default session name `telegram` maps to `config.session_path` (not bearer-token rules).
- Restart **telegram-dev** in Cursor's MCP panel after code changes.
- Credentials from project-root `.env` (see `.env.example`). The server loads `.env` automatically when started via `python3 -m src.server` from the project root.
- **Do not** `source .env.local` in zsh before starting the server — zsh treats `#` comments and special characters in env values differently than Python's dotenv loader and can corrupt `API_HASH`, proxy URLs, or tokens. Use `python3 -m src.server` from the repo root instead.
- `MTPROTO_PROXY` in `.env` / `.env.local` applies when the server is started from the project root (via Python dotenv, not shell sourcing).

An optional **telegram-dev-acl** URL entry in `.cursor/mcp.json` (http-auth + fixed `Authorization` header) is **not recommended for ACL testing** — see below.

### ACL development and testing (not via Cursor MCP)

ACL applies only in **http-auth** mode with `ACL_ENABLED=true`. Cursor MCP is a poor fit for exercising the ACL matrix:

- **stdio has no ACL** — `telegram-dev` bypasses bearer tokens and ACL entirely.
- **Fixed Authorization header** — a URL MCP entry binds one Bearer token; switching profiles means editing `mcp.json` and reconnecting.
- **URL MCP limitations** — local http-auth MCP connections can be unreliable; the server must already be running separately.
- **Session per principal** — each ACL profile needs its own `{id}.session` via `/setup` (principal identifier = Bearer string today), not the stdio `telegram.session`.
- **Restart and cache issues** — code changes and session/env fixes require restarting both the HTTP server and the MCP client; stale MCP processes are easy to miss.

Use these methods instead:

#### 1. pytest (primary regression)

```bash
pytest tests/test_session_acl.py tests/test_mcp_tool_acl_integration.py tests/test_mtproto_api_acl.py -q
```

Full suite: `pytest tests/ -q`.

#### 2. Manual HTTP server + curl (live matrix)

1. Copy [`acl.dev.yaml.example`](acl.dev.yaml.example) to `acl.dev.yaml` (gitignored — **never commit real tokens or production ACL**).
2. Start the server from the project root:

```bash
SERVER_MODE=http-auth HOST=127.0.0.1 PORT=8765 \
  ACL_ENABLED=true ACL_CONFIG_PATH=acl.dev.yaml \
  python3 -m src.server
```

3. Create one session per profile at `http://127.0.0.1:8765/setup` (session files must match principal identifiers in `acl.dev.yaml`).
4. Call tools with curl, swapping the Bearer token per profile (Bearer = HTTP credential; yaml keys = principal identifiers):

```bash
TOKEN="dev_acl_readonly_abcdefghijklmnopqrstuvwxz0"  # from acl.dev.yaml

curl -sS -X POST "http://127.0.0.1:8765/v1/mcp" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "get_messages",
      "arguments": {"chat_id": "me", "limit": 1}
    }
  }'
```

Repeat with `dev_acl_empty_lane_…` and `dev_acl_team_lane__…` tokens. Expect denials as in the matrix below.

Optional wrapper: [`scripts/acl_mcp_smoke.sh`](scripts/acl_mcp_smoke.sh) runs the same curl pattern for all three profiles. It reads bearer names from `acl.dev.yaml` (override path with `ACL_CONFIG_PATH`); set `BEARER_TOKEN_FOR_TESTING` to override the readonly profile when your yaml uses a custom token key.

**Live ACL test matrix**

| Profile | Bearer token (example file) | Expect |
| ------- | --------------------------- | ------ |
| readonly | `dev_acl_readonly_…` | `send_message` denied; `get_messages` on `me` allowed |
| empty-lane | `dev_acl_empty_lane_…` | `find_chats` denied (principal has `chats: []`) |
| team | `dev_acl_team_lane__…` | Whitelisted chat only; other chats denied |

#### 3. Session setup (`/setup`)

Per-principal sessions for http-auth (including ACL profiles) are created at `http://127.0.0.1:8765/setup` while the server above is running. Each principal identifier in `acl.dev.yaml` needs a matching `{id}.session` under `~/.config/fast-mcp-telegram/`.

**Credentials**

- API keys: `.env` (gitignored)
- ACL rules: `acl.dev.yaml` (gitignored); example template only in git
- `mcp.json`: stdio launch command for **telegram-dev** only; no secrets in committed files

### 4. Start Using!

```json
{"tool": "search_messages_globally", "params": {"query": "hello", "limit": 5}}
{"tool": "send_message", "params": {"chat_id": "me", "message": "Hello from AI!"}}
```

**ℹ️ Session Info:** Your Telegram session is saved to `~/.config/fast-mcp-telegram/` (stdio mode: `telegram.session`, http-auth mode: `{token}.session`)

**📖 For detailed installation and configuration instructions, see [Installation Guide](docs/Installation.md)**

---

## 🧪 Testing

### Test Structure

```
tests/
├── __init__.py                    # Tests package initialization
├── conftest.py                    # Shared fixtures and configuration
└── test_*.py                      # Organized test modules by functionality
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

#### Forum Topics Suite
```bash
# Focused forum topics suite
pytest tests/test_forum_topics_minimal.py -v

# Optional live integration checks (disabled by default)
FAST_MCP_TELEGRAM_LIVE_TESTS=1 \
FAST_MCP_TELEGRAM_FORUM_CHAT_ID=<chat_id> \
pytest tests/test_forum_topics_minimal.py -m integration -v
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
python -m src.server

# Run specific test
pytest tests/test_specific.py -v

# Development server with auto-reload
uvicorn src.server:app --host 0.0.0.0 --port 8000 --reload
```

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

### Pull Request Requirements

- **Tests**: All new code must include tests
- **Documentation**: Update docs for API changes
- **Code Review**: Required for all PRs
- **CI/CD**: All checks must pass
- **Conventional Commits**: Follow commit message format

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

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/leshchenko1979/fast-mcp-telegram/issues)
- **Discussions**: [GitHub Discussions](https://github.com/leshchenko1979/fast-mcp-telegram/discussions)
- **Community**: [English](https://t.me/+U_3CpNWhXa9jZDcy) · [Russian](https://t.me/mcp_telegram)

## 📄 License

By contributing to this project, you agree that your contributions will be licensed under the same license as the project (MIT License).

---

<div align="center">

**Thank you for contributing to fast-mcp-telegram! 🚀**

*Your contributions help make AI-Telegram integration better for everyone.*

</div>