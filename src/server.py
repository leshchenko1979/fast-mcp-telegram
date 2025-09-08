"""
Main server module for the Telegram bot functionality.
Provides API endpoints and core bot features.
"""

import asyncio
import inspect
import json
import os
import sys
import time
import traceback
from collections.abc import Callable
from functools import wraps
from typing import Literal

from fastmcp import FastMCP
from loguru import logger
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.templating import Jinja2Templates

# Add the project root to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.client.connection import (
    MAX_ACTIVE_SESSIONS,
    _session_cache,
    cleanup_client,
    generate_bearer_token,
    set_request_token,
)
from src.config.logging import setup_logging
from src.config.settings import API_HASH, API_ID, SESSION_DIR
from src.tools.contacts import get_contact_info, search_contacts_telegram
from src.tools.messages import (
    edit_message_impl,
    read_messages_by_ids,
    send_message_impl,
    send_message_to_phone_impl,
)
from src.tools.mtproto import invoke_mtproto_method
from src.tools.search import search_messages as search_messages_impl
from src.utils.error_handling import (
    handle_tool_error,
    log_and_build_error,
)

# =============================================================================
# CONFIGURATION & SETUP
# =============================================================================

IS_TEST_MODE = "--test-mode" in sys.argv

if IS_TEST_MODE:
    transport = "http"
    host = "127.0.0.1"
    port = 8000
else:
    transport = os.environ.get("MCP_TRANSPORT", "stdio")
    host = os.environ.get("MCP_HOST", "127.0.0.1")
    port = int(os.environ.get("MCP_PORT", "8000"))

# Authentication configuration
DISABLE_AUTH = os.getenv("DISABLE_AUTH", "false").lower() in ("true", "1", "yes")

# Development token generation for testing
if DISABLE_AUTH:
    logger.info("🔓 Authentication DISABLED for development mode")
else:
    logger.info("🔐 Authentication ENABLED")
    if transport == "http":
        logger.info("🚨 HTTP transport: Bearer token authentication is MANDATORY")
        logger.info(
            "💡 For development, you can generate a token by calling generate_dev_token()"
        )
    else:
        logger.info(
            "📝 Stdio transport: Bearer token optional (fallback to default session)"
        )

# Initialize MCP server and logging
mcp = FastMCP("Telegram MCP Server", stateless_http=True)
setup_logging()

# Templates (Phase 1)
templates = Jinja2Templates(
    directory=os.path.join(os.path.dirname(__file__), "templates")
)

# Simple in-memory setup session store for Phase 1 (not for production)
_setup_sessions: dict[str, dict] = {}


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================


def with_error_handling(operation_name: str):
    """
    Decorator that adds consistent error handling to MCP tool functions.

    This decorator wraps tool functions to automatically handle error responses
    using the standardized error handling pattern, eliminating code duplication.

    Args:
        operation_name: Name of the operation for error reporting

    Returns:
        Decorated function with automatic error handling
    """

    def decorator(func: Callable) -> Callable:
        # Store the original signature before MCP decorators modify it
        try:
            # Try to get the original function if MCP has already transformed it
            original_func = func
            if hasattr(func, "__wrapped__"):
                original_func = func.__wrapped__
            elif hasattr(func, "func") and callable(func.func):
                original_func = func.func

            original_sig = inspect.signature(original_func)
        except (TypeError, ValueError, AttributeError):
            # If signature inspection fails, we'll handle it in the wrapper
            original_sig = None

        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Build params dict from stored original signature for error context
            params = {}
            if original_sig:
                try:
                    bound_args = original_sig.bind(*args, **kwargs)
                    bound_args.apply_defaults()
                    params = dict(bound_args.arguments)
                except Exception:
                    # Fallback: build params dict from kwargs and positional args
                    param_names = list(original_sig.parameters.keys())
                    if (
                        param_names and param_names[0] == "self"
                    ):  # Skip 'self' if present
                        param_names = param_names[1:]

                    # Add positional args
                    for i, arg in enumerate(args):
                        if i < len(param_names):
                            params[param_names[i]] = arg

                    # Add keyword args
                    params.update(kwargs)
            else:
                # No signature available, just use kwargs as fallback
                params = dict(kwargs)

            try:
                # Call the original function with exception handling
                result = await func(*args, **kwargs)

                # Check if this is an error response
                error_response = handle_tool_error(result, operation_name, params)
                if error_response:
                    return error_response

                return result

            except Exception as e:
                # Handle any exception that occurs during function execution
                return log_and_build_error(
                    operation=operation_name,
                    error_message=f"Unexpected error: {e}",
                    params=params,
                    exception=e,
                )

        return wrapper

    return decorator


def extract_bearer_token() -> str | None:
    """
    Extract Bearer token from HTTP Authorization header.

    This function accesses HTTP headers from the current request context
    when running in HTTP transport mode. For stdio transport, it returns None.

    Note: For HTTP transport, authentication is mandatory when DISABLE_AUTH is False.
    This function only extracts the token - validation is handled by with_auth_context.

    Returns:
        Bearer token string if found and valid, None otherwise
    """
    try:
        # Only extract headers in HTTP transport mode
        if transport != "http":
            return None

        # Import here to avoid issues when not running in HTTP mode
        from fastmcp.server.dependencies import get_http_headers

        headers = get_http_headers()
        auth_header = headers.get("authorization", "")

        if not auth_header or not auth_header.startswith("Bearer "):
            return None

        # Extract token from "Bearer <token>"
        token = auth_header[7:].strip()  # Remove "Bearer " prefix

        if not token:
            return None

        return token

    except Exception as e:
        logger.warning(f"Error extracting bearer token: {e}")
        return None


def with_auth_context(func: Callable) -> Callable:
    """
    Decorator that extracts Bearer token from request headers and sets it in the context.

    This decorator should be applied to all MCP tool functions to enable
    token-based session management. When DISABLE_AUTH is True, authentication
    is bypassed for development purposes.

    For HTTP transport: Bearer token authentication is mandatory when DISABLE_AUTH is False.
    For stdio transport: Falls back to singleton behavior for backward compatibility.

    Args:
        func: The MCP tool function to wrap

    Returns:
        Wrapped function with authentication context

    Raises:
        Exception: When no valid Bearer token is provided for HTTP transport
    """

    @wraps(func)
    async def wrapper(*args, **kwargs):
        if DISABLE_AUTH:
            # Skip authentication for development mode
            set_request_token(None)
            return await func(*args, **kwargs)

        # Extract token from current request
        token = extract_bearer_token()

        if not token:
            # For HTTP transport, authentication is mandatory when DISABLE_AUTH is false
            if transport == "http":
                from fastmcp.server.dependencies import get_http_headers

                headers = get_http_headers()
                auth_header = headers.get("authorization", "")

                if auth_header:
                    error_msg = f"Invalid authorization header format. Expected 'Bearer <token>' but got: {auth_header[:20]}..."
                else:
                    error_msg = (
                        "Missing Bearer token in Authorization header. "
                        "HTTP requests require authentication. Use: "
                        "'Authorization: Bearer <your-token>' header. "
                        "Generate a token using the generate_bearer_token_tool."
                    )

                logger.warning(f"Authentication failed: {error_msg}")
                raise Exception(error_msg)

            # For stdio transport, fall back to singleton behavior (backward compatibility)
            set_request_token(None)
            logger.info("No Bearer token provided, using default session")
        else:
            # Token provided - set it in context for token-based sessions
            set_request_token(token)
            logger.info(f"Bearer token extracted for request: {token[:8]}...")

        # Call the original function
        return await func(*args, **kwargs)

    return wrapper


# =============================================================================
# HEALTH CHECK & ROUTES
# =============================================================================


@mcp.custom_route("/health", methods=["GET"])
async def health_check(request):
    """Health check endpoint for monitoring and load balancers."""
    current_time = time.time()
    session_info = []

    for token, (client, last_access) in _session_cache.items():
        hours_since_access = (current_time - last_access) / 3600
        session_info.append(
            {
                "token_prefix": token[:8] + "...",
                "hours_since_access": round(hours_since_access, 2),
                "is_connected": client.is_connected() if client else False,
                "last_access": time.ctime(last_access),
            }
        )

    return JSONResponse(
        {
            "status": "healthy",
            "active_sessions": len(_session_cache),
            "max_sessions": MAX_ACTIVE_SESSIONS,
            "sessions": session_info,
        }
    )


# =============================================================================
# SETUP WEB UI (PHASE 1)
# =============================================================================


@mcp.custom_route("/setup", methods=["GET"])
async def setup_get(request):
    """Serve initial setup page with phone form."""
    return templates.TemplateResponse(request, "setup.html")


@mcp.custom_route("/setup/phone", methods=["POST"])
async def setup_phone(request: Request):
    """Accept phone number, validate, and trigger code send; return code form fragment.

    Phase 2: actually call Telethon to send code and keep the TelegramClient alive
    for subsequent steps using a temporary setup session kept in memory.
    """
    form = await request.form()
    phone_raw = str(form.get("phone", "")).strip()

    def _mask_phone(p: str) -> str:
        if not p or len(p) < 4:
            return p
        # Keep first 3 and last 2 visible when possible
        first = p[:3]
        last = p[-2:]
        return f"{first}{'*' * max(0, len(p) - 5)}{last}"

    masked = _mask_phone(phone_raw)

    # Create a simple setup session id
    setup_id = str(int(time.time() * 1000))

    # Create a temporary session file path under SESSION_DIR using a temp setup id
    # We use a dedicated filename to NOT collide with token-based sessions yet.
    temp_session_name = f"setup-{setup_id}.session"
    temp_session_path = SESSION_DIR / temp_session_name

    # Lazy import Telethon to avoid import cost when not used
    from telethon import TelegramClient
    from telethon.errors.rpcerrorlist import PhoneNumberFloodError

    client = TelegramClient(temp_session_path, API_ID, API_HASH)
    await client.connect()
    # Send the code; do not sign in yet
    try:
        await client.send_code_request(phone_raw)
    except PhoneNumberFloodError:
        return templates.TemplateResponse(
            request,
            "fragments/code_form.html",
            {
                "masked_phone": masked,
                "setup_id": setup_id,
                "error": "Too many attempts. Please wait before retrying.",
            },
        )

    # Store client and state in memory for reuse in /verify and /2fa
    _setup_sessions[setup_id] = {
        "phone": phone_raw,
        "masked_phone": masked,
        "client": client,
        "session_path": str(temp_session_path),
        "authorized": False,
    }

    # Return fragment for HTMX swap
    return templates.TemplateResponse(
        request,
        "fragments/code_form.html",
        {"masked_phone": masked, "setup_id": setup_id},
    )


@mcp.custom_route("/setup/verify", methods=["POST"])
async def setup_verify(request: Request):
    """Verify the code; if 2FA required, show 2FA form, else success fragment."""
    form = await request.form()
    setup_id = str(form.get("setup_id", "")).strip()
    code = str(form.get("code", "")).strip()

    if not setup_id or setup_id not in _setup_sessions:
        return JSONResponse(
            {"ok": False, "error": "Invalid setup session."}, status_code=400
        )

    state = _setup_sessions[setup_id]
    client = state.get("client")
    phone = state.get("phone")
    masked_phone = state.get("masked_phone")

    from telethon.errors import SessionPasswordNeededError

    try:
        await client.sign_in(phone=phone, code=code)
        state["authorized"] = True
        # No 2FA needed → show success fragment
        return templates.TemplateResponse(
            request, "fragments/success.html", {"setup_id": setup_id}
        )
    except SessionPasswordNeededError:
        # Need 2FA → show 2FA form
        return templates.TemplateResponse(
            request,
            "fragments/2fa_form.html",
            {"setup_id": setup_id, "masked_phone": masked_phone},
        )
    except Exception as e:
        return templates.TemplateResponse(
            request,
            "fragments/code_form.html",
            {
                "masked_phone": masked_phone,
                "setup_id": setup_id,
                "error": f"Verification failed: {e}",
            },
        )


@mcp.custom_route("/setup/2fa", methods=["POST"])
async def setup_2fa(request: Request):
    """Submit 2FA password and finalize authentication."""
    form = await request.form()
    setup_id = str(form.get("setup_id", "")).strip()
    password = str(form.get("password", "")).strip()

    if not setup_id or setup_id not in _setup_sessions:
        return JSONResponse(
            {"ok": False, "error": "Invalid setup session."}, status_code=400
        )

    state = _setup_sessions[setup_id]
    client = state.get("client")

    try:
        await client.sign_in(password=password)
        state["authorized"] = True
        return templates.TemplateResponse(
            request, "fragments/success.html", {"setup_id": setup_id}
        )
    except Exception as e:
        return templates.TemplateResponse(
            request,
            "fragments/2fa_form.html",
            {"setup_id": setup_id, "error": f"2FA failed: {e}"},
        )


# =============================================================================
# SETUP WEB UI (PHASE 3)
# =============================================================================


def _generate_mcp_config_json(domain: str, token: str) -> str:
    config = {
        "mcpServers": {
            "telegram": {
                "url": f"https://{domain}/mcp",
                "headers": {
                    "Authorization": f"Bearer {token}",
                },
            }
        }
    }
    return json.dumps(config, indent=2)


@mcp.custom_route("/setup/generate", methods=["POST"])
async def setup_generate(request: Request):
    """Finalize auth: generate token, move session file, and show config JSON."""
    form = await request.form()
    setup_id = str(form.get("setup_id", "")).strip()

    if not setup_id or setup_id not in _setup_sessions:
        return JSONResponse(
            {"ok": False, "error": "Invalid setup session."}, status_code=400
        )

    state = _setup_sessions[setup_id]
    if not state.get("authorized"):
        return JSONResponse(
            {"ok": False, "error": "Not authorized yet."}, status_code=400
        )

    client = state.get("client")
    temp_session_path = state.get("session_path")

    # Generate token and rename session file to token-based session
    token = generate_bearer_token()
    from pathlib import Path

    src = Path(temp_session_path)
    dst = SESSION_DIR / f"{token}.session"

    try:
        # Ensure any pending session writes are flushed
        await client.send_read_acknowledge(None)  # safe no-op to touch session
    except Exception:
        pass

    try:
        # Close the temp client after successful auth; the session file is now valid
        try:
            await client.disconnect()
        except Exception:
            pass

        if src.exists():
            src.rename(dst)
    except Exception as e:
        return JSONResponse(
            {"ok": False, "error": f"Failed to persist session: {e}"}, status_code=500
        )

    # Build config JSON using DOMAIN env (fallback to localhost for dev)
    domain = os.getenv("DOMAIN", "localhost")
    config_json = _generate_mcp_config_json(domain, token)

    # Save token into state for potential follow-up
    state["token"] = token
    state["final_session_path"] = str(dst)

    return templates.TemplateResponse(
        request,
        "fragments/config.html",
        {"setup_id": setup_id, "token": token, "config_json": config_json},
    )


@mcp.custom_route("/download-config/{token}", methods=["GET"])
async def download_config(request: Request):
    token = request.path_params.get("token")
    domain = os.getenv("DOMAIN", "localhost")
    config_json = _generate_mcp_config_json(domain, token)
    headers = {"Content-Disposition": "attachment; filename=mcp.json"}
    return PlainTextResponse(
        config_json, media_type="application/json", headers=headers
    )


# =============================================================================
# MESSAGE TOOLS
# =============================================================================


@mcp.tool()
@with_error_handling("search_messages_globally")
@with_auth_context
async def search_messages_globally(
    query: str,
    limit: int = 50,
    min_date: str | None = None,
    max_date: str | None = None,
    chat_type: Literal["private", "group", "channel"] | None = None,
    auto_expand_batches: int = 2,
    include_total_count: bool = False,
):
    """
    Search messages across all Telegram chats (global search).

    FEATURES:
    - Multiple queries: "term1, term2, term3"
    - Date filtering: ISO format (min_date="2024-01-01")
    - Chat type filter: "private", "group", "channel"

    SEARCH LIMITATIONS:
    - NO wildcards: "proj*", "meet%" won't work
    - NO regex: "^project", "deadline$" won't work
    - Use simple terms: "proj" finds "project", "projects"
    - Case insensitive: "DEADLINE" finds "deadline"

    EXAMPLES:
    search_messages_globally(query="deadline", limit=20)  # Global search
    search_messages_globally(query="project, launch", limit=30)  # Multi-term search
    search_messages_globally(query="proj", limit=20)  # Partial word search

    Args:
        query: Search terms (required). Comma-separated for multiple terms.
        limit: Max results (default: 50)
        min_date: Min date in YYYY-MM-DD format
        max_date: Max date in YYYY-MM-DD format
        chat_type: Filter by "private", "group", or "channel"
        auto_expand_batches: Extra batches for filtered results
        include_total_count: Include total count (ignored in global mode)
    """
    return await search_messages_impl(
        query=query,
        chat_id=None,
        limit=limit,
        min_date=min_date,
        max_date=max_date,
        chat_type=chat_type,
        auto_expand_batches=auto_expand_batches,
        include_total_count=include_total_count,
    )


@mcp.tool()
@with_error_handling("search_messages_in_chat")
@with_auth_context
async def search_messages_in_chat(
    chat_id: str,
    query: str | None = None,
    limit: int = 50,
    min_date: str | None = None,
    max_date: str | None = None,
    auto_expand_batches: int = 2,
    include_total_count: bool = False,
):
    """
    Search messages within a specific Telegram chat.

    FEATURES:
    - Multiple queries: "term1, term2, term3"
    - Date filtering: ISO format (min_date="2024-01-01")
    - Total count support for per-chat searches

    SEARCH LIMITATIONS:
    - NO wildcards: "proj*", "meet%" won't work
    - NO regex: "^project", "deadline$" won't work
    - Use simple terms: "proj" finds "project", "projects"
    - Case insensitive: "DEADLINE" finds "deadline"

    EXAMPLES:
    search_messages_in_chat(chat_id="me", limit=10)      # Latest messages (no query)
    search_messages_in_chat(chat_id="-1001234567890", query="launch")  # Specific chat
    search_messages_in_chat(chat_id="telegram", query="update, news")  # Multi-term search
    search_messages_in_chat(chat_id="me", query="proj")  # Partial word search

    Args:
        chat_id: Target chat ('me', ID, username, or -100... channel ID)
        query: Optional search term(s). If omitted, returns latest messages.
        limit: Max results
        min_date: Min date (YYYY-MM-DD)
        max_date: Max date (YYYY-MM-DD)
        auto_expand_batches: Extra batches for filtered results
        include_total_count: Include total matching count
    """
    return await search_messages_impl(
        query=query,
        chat_id=chat_id,
        limit=limit,
        min_date=min_date,
        max_date=max_date,
        chat_type=None,  # Not supported in per-chat mode
        auto_expand_batches=auto_expand_batches,
        include_total_count=include_total_count,
    )


@mcp.tool()
@with_error_handling("send_message")
@with_auth_context
async def send_message(
    chat_id: str,
    message: str,
    reply_to_msg_id: int | None = None,
    parse_mode: Literal["markdown", "html"] | None = None,
):
    """
    Send new message in Telegram chat.

    FORMATTING:
    - parse_mode=None: Plain text
    - parse_mode="markdown": *bold*, _italic_, [link](url), `code`
    - parse_mode="html": <b>bold</b>, <i>italic</i>, <a href="url">link</a>, <code>code</code>

    EXAMPLES:
    send_message(chat_id="me", message="Hello!")  # Send to Saved Messages
    send_message(chat_id="-1001234567890", message="New message", reply_to_msg_id=12345)  # Reply to message

    Args:
        chat_id: Target chat ID ('me' for Saved Messages, numeric ID, or username)
        message: Message text to send
        reply_to_msg_id: Reply to specific message ID (optional)
        parse_mode: Text formatting ("markdown", "html", or None)
    """
    return await send_message_impl(chat_id, message, reply_to_msg_id, parse_mode)


@mcp.tool()
@with_error_handling("edit_message")
@with_auth_context
async def edit_message(
    chat_id: str,
    message_id: int,
    message: str,
    parse_mode: Literal["markdown", "html"] | None = None,
):
    """
    Edit existing message in Telegram chat.

    FORMATTING:
    - parse_mode=None: Plain text
    - parse_mode="markdown": *bold*, _italic_, [link](url), `code`
    - parse_mode="html": <b>bold</b>, <i>italic</i>, <a href="url">link</a>, <code>code</code>

    EXAMPLES:
    edit_message(chat_id="me", message_id=12345, message="Updated text")  # Edit Saved Messages
    edit_message(chat_id="-1001234567890", message_id=67890, message="*Updated* message")  # Edit with formatting

    Args:
        chat_id: Target chat ID ('me' for Saved Messages, numeric ID, or username)
        message_id: Message ID to edit (required)
        message: New message text
        parse_mode: Text formatting ("markdown", "html", or None)
    """
    return await edit_message_impl(chat_id, message_id, message, parse_mode)


@mcp.tool()
@with_error_handling("read_messages")
@with_auth_context
async def read_messages(chat_id: str, message_ids: list[int]):
    """
    Read specific messages by their IDs from a Telegram chat.

    SUPPORTED CHAT FORMATS:
    - 'me': Saved Messages
    - Numeric ID: User/chat ID (e.g., 133526395)
    - Username: @channel_name or @username
    - Channel ID: -100xxxxxxxxx

    USAGE:
    - First use search_messages() to find message IDs
    - Then read specific messages using those IDs
    - Returns full message content with metadata

    EXAMPLES:
    read_messages(chat_id="me", message_ids=[680204, 680205])  # Saved Messages
    read_messages(chat_id="-1001234567890", message_ids=[123, 124])  # Channel

    Args:
        chat_id: Target chat identifier (use 'me' for Saved Messages)
        message_ids: List of message IDs to retrieve (from search results)
    """
    return await read_messages_by_ids(chat_id, message_ids)


# =============================================================================
# CONTACT TOOLS
# =============================================================================


@mcp.tool()
@with_error_handling("search_contacts")
@with_auth_context
async def search_contacts(query: str, limit: int = 20):
    """
    Search Telegram contacts and users by name, username, or phone number.

    SEARCH SCOPE:
    - Your saved contacts
    - Global Telegram users
    - Public channels and groups

    QUERY TYPES:
    - Name: "John Doe" or "Иванов"
    - Username: "@username" (without @)
    - Phone: "+1234567890"

    WORKFLOW:
    1. Search for contact: search_contacts("John Doe")
    2. Get chat_id from results
    3. Search messages: search_messages(chat_id=chat_id, query="topic")

    EXAMPLES:
    search_contacts("@telegram")      # Find user by username
    search_contacts("John Smith")     # Find by name
    search_contacts("+1234567890")    # Find by phone

    Args:
        query: Search term (name, username without @, or phone with +)
        limit: Max results (default: 20, recommended: ≤50)
    """
    return await search_contacts_telegram(query, limit)


@mcp.tool()
@with_error_handling("get_contact_details")
@with_auth_context
async def get_contact_details(chat_id: str):
    """
    Get detailed profile information for a specific Telegram user or chat.

    USE CASES:
    - Get full user profile after finding chat_id
    - Retrieve contact details, bio, and status
    - Check if user is online/bot/channel

    SUPPORTED FORMATS:
    - Numeric user ID: 133526395
    - Username: "telegram" (without @)
    - Channel ID: -100xxxxxxxxx

    EXAMPLES:
    get_contact_details("133526395")      # User by ID
    get_contact_details("telegram")       # User by username
    get_contact_details("-1001234567890") # Channel by ID

    Args:
        chat_id: Target chat/user identifier (numeric ID, username, or channel ID)
    """
    return await get_contact_info(chat_id)


# =============================================================================
# PHONE MESSAGING TOOLS
# =============================================================================


@mcp.tool()
@with_error_handling("send_message_to_phone")
@with_auth_context
async def send_message_to_phone(
    phone_number: str,
    message: str,
    first_name: str = "Contact",
    last_name: str = "Name",
    remove_if_new: bool = False,
    reply_to_msg_id: int | None = None,
    parse_mode: Literal["markdown", "html"] | None = None,
):
    """
    Send message to phone number, auto-managing Telegram contacts.

    FEATURES:
    - Auto-creates contact if phone not in contacts
    - Sends message immediately after contact creation
    - Optional contact cleanup after sending
    - Full message formatting support

    CONTACT MANAGEMENT:
    - Checks existing contacts first
    - Creates temporary contact only if needed
    - Removes temporary contact if remove_if_new=True

    REQUIREMENTS:
    - Phone number must be registered on Telegram
    - Include country code: "+1234567890"

    EXAMPLES:
    send_message_to_phone("+1234567890", "Hello from Telegram!")  # Basic send
    send_message_to_phone("+1234567890", "*Important*", remove_if_new=True)  # Auto cleanup

    Args:
        phone_number: Target phone number with country code (e.g., "+1234567890")
        message: Message text to send
        first_name: Contact first name (for new contacts only)
        last_name: Contact last name (for new contacts only)
        remove_if_new: Remove contact after sending if newly created
        reply_to_msg_id: Reply to specific message ID
        parse_mode: Text formatting ("markdown", "html", or None)

    Returns:
        Message send result + contact management info (contact_was_new, contact_removed)
    """
    return await send_message_to_phone_impl(
        phone_number=phone_number,
        message=message,
        first_name=first_name,
        last_name=last_name,
        remove_if_new=remove_if_new,
        reply_to_msg_id=reply_to_msg_id,
        parse_mode=parse_mode,
    )


# =============================================================================
# LOW-LEVEL API TOOLS
# =============================================================================


@mcp.tool()
@with_error_handling("invoke_mtproto")
@with_auth_context
async def invoke_mtproto(method_full_name: str, params_json: str):
    """
    Execute low-level Telegram MTProto API methods directly.

    USE CASES:
    - Access advanced Telegram API features
    - Custom queries not covered by standard tools
    - Administrative operations

    METHOD FORMAT:
    - Full class name: "messages.GetHistory", "users.GetFullUser"
    - Telegram API method names with proper casing

    PARAMETERS:
    - JSON string with method parameters
    - Parameter names match Telegram API documentation
    - Supports complex nested objects

    EXAMPLES:
    invoke_mtproto("users.GetFullUser", '{"id": {"_": "inputUserSelf"}}')  # Get self info
    invoke_mtproto("messages.GetHistory", '{"peer": {"_": "inputPeerChannel", "channel_id": 123456, "access_hash": 0}, "limit": 10}')

    Args:
        method_full_name: Telegram API method name (e.g., "messages.GetHistory")
        params_json: Method parameters as JSON string

    Returns:
        API response as dict, or error details if failed
    """
    try:
        try:
            params = json.loads(params_json)
        except Exception as e:
            return log_and_build_error(
                operation="invoke_mtproto",
                error_message=f"Invalid JSON in params_json: {e}",
                params={
                    "method_full_name": method_full_name,
                    "params_json": params_json,
                },
                exception=e,
            )

        # Convert any non-string keys to strings
        sanitized_params = {
            (k if isinstance(k, str) else str(k)): v for k, v in params.items()
        }

        return await invoke_mtproto_method(
            method_full_name, sanitized_params, params_json
        )
    except Exception as e:
        return log_and_build_error(
            operation="invoke_mtproto",
            error_message=f"Error in invoke_mtproto: {e!s}",
            params={
                "method_full_name": method_full_name,
                "params_json": params_json,
            },
            exception=e,
        )


# =============================================================================
# LIFECYCLE FUNCTIONS
# =============================================================================


def shutdown_procedure():
    """Synchronously performs async cleanup."""
    logger.info("Starting cleanup procedure.")

    # Create a new event loop for cleanup to avoid conflicts.
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(cleanup_client())
        loop.close()
        logger.info("Cleanup successful.")
    except Exception as e:
        logger.error(f"Error during cleanup: {e}\n{traceback.format_exc()}")


def main():
    """Entry point for console script; runs the MCP server and ensures cleanup."""

    run_args = {"transport": transport}
    if transport == "http":
        run_args.update({"host": host, "port": port})

    try:
        mcp.run(**run_args)
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received. Initiating shutdown.")
    finally:
        shutdown_procedure()


# Run the server if this file is executed directly
if __name__ == "__main__":
    main()
