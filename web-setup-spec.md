## Telegram MCP Server Web Interface Specification

### Project Overview

Build a lightweight HTMX-powered web interface for the existing Telegram MCP server that allows users to authenticate with Telegram and generate MCP configuration files through a browser interface.

### Current System Architecture

- **Framework**: FastMCP/Starlette with HTTP transport
- **Authentication**: Bearer token-based session management
- **Existing CLI Setup**: `setup_telegram.py` handles phone/code/2FA flow
- **Session Management**: Token-based client caching in `connection.py`
- **Deployment**: Docker container with health checks

### Feature Requirements

#### Core Functionality

- **Web-based Telegram Authentication**: Replace CLI setup with browser interface
- **Multi-step Flow**: Phone → Code → 2FA → Success
- **MCP Config Generation**: Auto-generate `mcp.json` with HTTP transport
- **File Delivery**: Both download and copy-paste options
- **Integration**: Part of existing server/container

### Technical Approach

- **HTMX**: Single-page app with content swapping
- **Template Engine**: Jinja2 for server-side rendering
- **Fragment-based**: Each step returns HTML fragments
- **Progressive Enhancement**: Works without JavaScript
- **Session Lifecycle Rule**: Keep Telegram sessions open across all auth steps; do not close until authentication completes successfully.

### Detailed Phase Descriptions

#### Phase 1: Create HTMX-Powered Web Interface Foundation

- **Objective**: Establish the basic web interface structure with HTMX support

- **Key Deliverables**:
  - HTML template directory structure
  - Base HTMX template with phone input form
  - Starlette template rendering integration
  - Initial `/setup` GET route
  - Minimal POST `/setup/phone` handler stub that validates and echoes masked phone via fragment (no Telegram call)
  - Simple per-session state (cookie or server-side map) that persists the entered phone to validate step-to-step state

- **Technical Details**:

```text
templates/
├── base.html          # HTMX CDN, CSS, main layout
├── setup.html         # Phone input form
└── fragments/         # HTMX response fragments
    ├── code_form.html
    ├── 2fa_form.html
    └── success.html
```

- **Implementation Steps**:
  - Create `templates/` directory in project root
  - Add Starlette `TemplateResponse` support to `server.py`
  - Build responsive HTML form with HTMX attributes
  - Include minimal CSS for professional appearance
  - Create GET `/setup` route serving the initial form
  - Implement POST `/setup/phone` to return `code_form.html` with masked phone (static success path for Phase 1)
  - Add simple session state holder (e.g., signed cookie or server store) to persist phone across requests

- **Dependencies**:
  - Add Jinja2 to project dependencies
  - HTMX via CDN (no additional deps)

#### Phase 2: Implement HTMX Fragment-Based Authentication Flow

- **Objective**: Build the multi-step authentication using HTMX content swapping

- **Key Deliverables**:
  - Real phone number submission endpoint that triggers Telegram to send the code
  - Code verification endpoint
  - 2FA password endpoint
  - HTML fragment templates for each step
  - Session lifecycle adherence: reuse the same `TelegramClient` between steps; do not close until success
  - Early config preview after successful code verification (if no 2FA) with placeholder token (read-only)

- **Technical Details**:

```text
# Route structure
POST /setup/phone    → returns code_form.html fragment
POST /setup/verify   → returns 2fa_form.html or success.html
POST /setup/2fa      → returns success.html fragment
```

- **Implementation Steps**:
  - Extract Telegram auth logic from `setup_telegram.py`
  - Create session state management for web requests (map setupId → TelegramClient + state)
  - Build fragment-returning endpoints with error handling
  - Implement phone masking and validation
  - Handle Telegram API errors gracefully
  - Ensure the same `TelegramClient` instance is reused across `/setup/phone`, `/setup/verify`, `/setup/2fa` for the same setup session

- **Integration Points**:
  - Reuse `TelegramClient` creation logic
  - Leverage existing `generate_bearer_token()` function
  - Maintain session state between HTMX requests

#### Phase 3: Generate MCP Config with Auto-Download

- **Objective**: Create MCP configuration generation and delivery system

- **Key Deliverables**:
  - `mcp.json` generation function using runtime domain from env var `DOMAIN`
  - Success page with config display
  - Auto-download functionality
  - Copy-to-clipboard feature

- **Technical Details**:

```json
{
  "mcpServers": {
    "telegram": {
      "url": "https://$DOMAIN/mcp",
      "headers": {
        "Authorization": "Bearer <generated-token>"
      }
    }
  }
}
```
 
 - Use the exact shape from the current `mcp.json`, replacing the domain at runtime with env var `DOMAIN`.

- **Implementation Steps**:
  - Create `generate_mcp_config(domain: str, token: str)` function that emits the JSON above
  - Read `DOMAIN` from environment at runtime; validate non-empty; optionally default to `localhost` for development
  - Build success page template with JSON display
  - Add `/download-config/<token>` route for file download
  - Implement JavaScript for copy-to-clipboard
  - Add auto-download trigger on success
  - Generate bearer token immediately after successful authentication and inject into the config

- **User Experience**:
  - JSON displayed in formatted code block
  - One-click copy button
  - Automatic file download
  - Clear setup instructions

#### Phase 4: Integrate HTMX Interface with Existing Server

- **Objective**: Seamlessly integrate web interface with existing MCP server

- **Key Deliverables**:
  - Updated Docker configuration
  - Dependency management
  - Production-ready deployment
  - Comprehensive testing

- **Technical Details**:

```dockerfile
# Add template files to Docker image
COPY templates/ ./templates/

# Ensure Jinja2 is installed
RUN pip install jinja2
```

- **Implementation Steps**:
  - Update `pyproject.toml` with Jinja2 dependency
  - Modify `Dockerfile` to include template files
  - Ensure web routes coexist with MCP tools
  - Add health check validation for web interface
  - Test complete flow in Docker environment

- **Quality Assurance**:
  - End-to-end authentication flow testing
  - Error handling validation
  - Mobile responsiveness check
  - Docker deployment verification

### Success Criteria

#### Functional Requirements

- ✅ Users can authenticate via web browser
- ✅ Multi-step flow works seamlessly with HTMX
- ✅ MCP configuration auto-generates and downloads
- ✅ Integration maintains existing MCP functionality

#### Technical Requirements

- ✅ Single Docker container deployment
- ✅ No JavaScript dependencies (HTMX via CDN)
- ✅ Responsive design for mobile/desktop
- ✅ Proper error handling and user feedback

#### User Experience

- ✅ Intuitive step-by-step process
- ✅ Clear error messages and guidance
- ✅ Professional, clean interface
- ✅ Immediate config file availability

### Architecture Benefits

- **HTMX Advantages**: Eliminates complex JavaScript, natural state progression
- **Server-Side Rendering**: Better SEO, faster initial load, simpler debugging
- **Progressive Enhancement**: Works without JavaScript as fallback
- **Minimal Dependencies**: Only adds Jinja2, uses HTMX via CDN
- **Container Integration**: No additional services or complexity


