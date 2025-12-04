import contextlib
import os
import shutil
import time
from pathlib import Path
from typing import Any

from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.templating import Jinja2Templates
from telethon import TelegramClient
from telethon.errors import PasswordHashInvalidError, SessionPasswordNeededError
from telethon.errors.rpcerrorlist import PhoneNumberFloodError

from src.client.connection import generate_bearer_token
from src.config.server_config import ServerMode, get_config
from src.config.settings import API_HASH, API_ID
from src.server_components.auth import RESERVED_SESSION_NAMES
from src.utils.mcp_config import generate_mcp_config_json

# Constants
SETUP_SESSION_PREFIX = "setup-"
REAUTH_SESSION_PREFIX = "reauth-"

# Templates (Phase 1)
# Use the project-level templates directory: /app/src/templates
templates = Jinja2Templates(
    directory=os.path.join(os.path.dirname(__file__), "..", "templates")
)

# Simple in-memory setup session store for web setup flow
_setup_sessions: dict[str, dict] = {}
# Use unified config for TTL
SETUP_SESSION_TTL_SECONDS = get_config().setup_session_ttl_seconds


# Helper functions
def mask_phone_number(phone: str) -> str:
    """Mask phone number for display, showing only first 3 and last 2 digits."""
    if not phone or len(phone) < 4:
        return phone
    first = phone[:3]
    last = phone[-2:]
    return f"{first}{'*' * max(0, len(phone) - 5)}{last}"


def validate_setup_session(setup_id: str) -> dict[str, Any] | None:
    """Validate setup session exists and return state, or None if invalid."""
    if not setup_id or setup_id not in _setup_sessions:
        return None
    return _setup_sessions[setup_id]


def create_error_response(error: str, template: str = "fragments/error.html") -> dict:
    """Create standardized error response."""
    return {"error": error}


def create_session_client(session_path: Path) -> TelegramClient:
    """Create and return a configured TelegramClient."""
    return TelegramClient(
        session_path,
        API_ID,
        API_HASH,
        entity_cache_limit=get_config().entity_cache_limit,
    )


async def cleanup_stale_setup_sessions():
    """Clean up expired setup sessions and their temporary files."""
    now = time.time()
    stale_ids: list[str] = []

    for sid, state in list(_setup_sessions.items()):
        created_at = state.get("created_at") or 0
        if created_at and (now - float(created_at) > SETUP_SESSION_TTL_SECONDS):
            stale_ids.append(sid)

    for sid in stale_ids:
        state = _setup_sessions.pop(sid, None) or {}
        await _cleanup_session_state(state)


async def _cleanup_session_state(state: dict[str, Any]):
    """Clean up a single session state (client and temp files)."""
    client = state.get("client")
    session_path = state.get("session_path")

    # Disconnect client
    if client:
        with contextlib.suppress(Exception):
            await client.disconnect()

    # Remove temporary session files
    try:
        if isinstance(session_path, str) and session_path:
            p = Path(session_path)
            if (
                p.name.startswith(SETUP_SESSION_PREFIX)
                or p.name.startswith(REAUTH_SESSION_PREFIX)
            ) and p.exists():
                p.unlink(missing_ok=True)
    except Exception:
        pass


async def setup_complete_reauth(request: Request):
    """Complete reauthorization by replacing the original session file with reauthorized version."""
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
    original_path = Path(state.get("original_session_path"))
    temp_path = Path(state.get("temp_session_path"))
    existing_token = state.get("existing_token")

    try:
        with contextlib.suppress(Exception):
            await client.send_read_acknowledge(None)  # touch session

        with contextlib.suppress(Exception):
            await client.disconnect()

        # Replace original session with reauthorized one
        temp_path.replace(original_path)

        # Clean up
        state.clear()

        return templates.TemplateResponse(
            request,
            "fragments/success.html",
            {
                "message": f"Session reauthorized successfully! Your token {existing_token[:8]}... is now active.",
                "token": existing_token,
            },
        )

    except Exception as e:
        return templates.TemplateResponse(
            request,
            "fragments/error.html",
            {"error": f"Failed to complete reauthorization: {e}"},
        )


async def setup_generate(request: Request):
    """Complete new session setup by generating token and config."""
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

    # Use desired token if specified, otherwise generate random one
    desired_token = state.get("desired_token")
    token = desired_token if desired_token else generate_bearer_token()

    src = Path(temp_session_path)
    session_dir = get_config().session_directory
    dst = session_dir / f"{token}.session"

    # Check if session already exists (only when using desired token)
    if desired_token and dst.exists():
        return JSONResponse(
            {"ok": False, "error": f"Session with token '{token}' already exists"},
            status_code=409,
        )

    try:
        with contextlib.suppress(Exception):
            await client.send_read_acknowledge(None)  # touch session

        with contextlib.suppress(Exception):
            await client.disconnect()

        if src.exists():
            src.rename(dst)
    except Exception as e:
        return JSONResponse(
            {"ok": False, "error": f"Failed to persist session: {e}"},
            status_code=500,
        )

    domain = get_config().domain
    # Web setup always uses HTTP_AUTH mode
    config_json = generate_mcp_config_json(
        ServerMode.HTTP_AUTH,
        session_name="",  # Not used for HTTP_AUTH
        bearer_token=token,
        domain=domain,
    )

    state.clear()
    state.update(
        {
            "token": token,
            "final_session_path": str(dst),
            "created_at": time.time(),
        }
    )

    return templates.TemplateResponse(
        request,
        "fragments/config.html",
        {"setup_id": setup_id, "token": token, "config_json": config_json},
    )


async def _complete_authentication(request: Request, state: dict[str, Any]):
    """Complete authentication flow based on session type."""
    if state.get("reauthorizing"):
        return await setup_complete_reauth(request)
    return await setup_generate(request)


def register_web_setup_routes(mcp_app):
    @mcp_app.custom_route("/setup", methods=["GET"])
    async def setup_get(request):
        await cleanup_stale_setup_sessions()
        return templates.TemplateResponse(request, "setup.html")

    @mcp_app.custom_route("/setup/phone", methods=["POST"])
    async def setup_phone(request: Request):
        form = await request.form()
        phone_raw = str(form.get("phone", "")).strip()

        masked = mask_phone_number(phone_raw)
        await cleanup_stale_setup_sessions()

        setup_id = str(int(time.time() * 1000))
        temp_session_path = (
            get_config().session_directory / f"{SETUP_SESSION_PREFIX}{setup_id}.session"
        )

        client = create_session_client(temp_session_path)
        await client.connect()

        try:
            await client.send_code_request(phone_raw)
        except PhoneNumberFloodError:
            await client.disconnect()
            return templates.TemplateResponse(
                request,
                "fragments/code_form.html",
                {
                    "masked_phone": masked,
                    "setup_id": setup_id,
                    "error": "Too many attempts. Please wait before retrying.",
                },
            )

        _setup_sessions[setup_id] = {
            "phone": phone_raw,
            "masked_phone": masked,
            "client": client,
            "session_path": str(temp_session_path),
            "authorized": False,
            "created_at": time.time(),
        }

        return templates.TemplateResponse(
            request,
            "fragments/code_form.html",
            {"masked_phone": masked, "setup_id": setup_id},
        )

    @mcp_app.custom_route("/setup/verify", methods=["POST"])
    async def setup_verify(request: Request):
        form = await request.form()
        setup_id = str(form.get("setup_id", "")).strip()
        code = str(form.get("code", "")).strip()

        state = validate_setup_session(setup_id)
        if not state:
            return JSONResponse(
                {"ok": False, "error": "Invalid setup session."}, status_code=400
            )

        await cleanup_stale_setup_sessions()

        client = state.get("client")
        phone = state.get("phone")
        masked_phone = state.get("masked_phone")

        try:
            await client.sign_in(phone=phone, code=code)
            state["authorized"] = True
            return await _complete_authentication(request, state)
        except SessionPasswordNeededError:
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

    @mcp_app.custom_route("/setup/2fa", methods=["POST"])
    async def setup_2fa(request: Request):
        form = await request.form()
        setup_id = str(form.get("setup_id", "")).strip()
        password = str(form.get("password", "")).strip()

        state = validate_setup_session(setup_id)
        if not state:
            return JSONResponse(
                {"ok": False, "error": "Invalid setup session."}, status_code=400
            )

        await cleanup_stale_setup_sessions()

        client = state.get("client")
        masked_phone = state.get("masked_phone")

        try:
            await client.sign_in(password=password)
            state["authorized"] = True
            return await _complete_authentication(request, state)
        except PasswordHashInvalidError:
            return templates.TemplateResponse(
                request,
                "fragments/2fa_form.html",
                {
                    "setup_id": setup_id,
                    "masked_phone": masked_phone,
                    "error": "Invalid password. Please try again.",
                },
            )
        except Exception as e:
            return templates.TemplateResponse(
                request,
                "fragments/2fa_form.html",
                {
                    "setup_id": setup_id,
                    "masked_phone": masked_phone,
                    "error": f"Authentication failed: {e}",
                },
            )

    @mcp_app.custom_route("/setup/reauthorize", methods=["POST"])
    async def setup_reauthorize(request: Request):
        form = await request.form()
        existing_token = str(form.get("token", "")).strip()

        if not existing_token:
            return templates.TemplateResponse(
                request,
                "fragments/error.html",
                create_error_response("Bearer token is required"),
            )

        # Security: Prevent reserved session names
        if existing_token.lower() in RESERVED_SESSION_NAMES:
            return templates.TemplateResponse(
                request, "fragments/error.html", create_error_response("Invalid token")
            )

        session_path = get_config().session_directory / f"{existing_token}.session"
        if not session_path.exists():
            # Start new auth process with this token name
            await cleanup_stale_setup_sessions()

            setup_id = str(int(time.time() * 1000))
            temp_session_path = (
                get_config().session_directory
                / f"{SETUP_SESSION_PREFIX}{setup_id}.session"
            )

            # Create client for new session
            client = create_session_client(temp_session_path)
            await client.connect()

            _setup_sessions[setup_id] = {
                "desired_token": existing_token,  # Remember the desired token name
                "client": client,
                "session_path": str(temp_session_path),
                "authorized": False,
                "created_at": time.time(),
            }

            return templates.TemplateResponse(
                request,
                "fragments/reauthorize_phone.html",
                {"setup_id": setup_id},
            )

        # Check if session needs reauthorization
        try:
            client = create_session_client(session_path)
            await client.connect()
            is_authorized = await client.is_user_authorized()
            await client.disconnect()

            if is_authorized:
                return templates.TemplateResponse(
                    request,
                    "fragments/success.html",
                    {"message": "Your session is already authorized and working!"},
                )
        except Exception as e:
            return templates.TemplateResponse(
                request,
                "fragments/error.html",
                create_error_response(f"Error checking session: {e}"),
            )

        # Session needs reauthorization - create temp session for reauth
        setup_id = str(int(time.time() * 1000))
        temp_session_path = (
            get_config().session_directory
            / f"{REAUTH_SESSION_PREFIX}{setup_id}.session"
        )

        # Copy existing session to temp location
        shutil.copy2(session_path, temp_session_path)

        # Create client for reauthorization
        client = create_session_client(temp_session_path)
        await client.connect()

        try:
            _setup_sessions[setup_id] = {
                "existing_token": existing_token,
                "original_session_path": str(session_path),
                "temp_session_path": str(temp_session_path),
                "client": client,
                "reauthorizing": True,
                "created_at": time.time(),
            }

            # Ask for phone number since we can't extract it securely from session
            return templates.TemplateResponse(
                request, "fragments/reauthorize_phone.html", {"setup_id": setup_id}
            )

        except Exception as e:
            await client.disconnect()
            temp_session_path.unlink(missing_ok=True)
            return templates.TemplateResponse(
                request,
                "fragments/error.html",
                create_error_response(f"Failed to prepare reauthorization: {e}"),
            )

    @mcp_app.custom_route("/setup/reauthorize/phone", methods=["POST"])
    async def setup_reauthorize_phone(request: Request):
        form = await request.form()
        setup_id = str(form.get("setup_id", "")).strip()
        phone_raw = str(form.get("phone", "")).strip()

        state = validate_setup_session(setup_id)
        if not state:
            return templates.TemplateResponse(
                request,
                "fragments/error.html",
                create_error_response("Invalid setup session"),
            )

        client = state.get("client")

        try:
            await client.send_code_request(phone_raw)
        except PhoneNumberFloodError:
            return templates.TemplateResponse(
                request,
                "fragments/reauthorize_phone.html",
                {
                    "setup_id": setup_id,
                    "error": "Too many attempts. Please wait before retrying.",
                },
            )

        state["phone"] = phone_raw
        state["masked_phone"] = mask_phone_number(phone_raw)

        return templates.TemplateResponse(
            request,
            "fragments/code_form.html",
            {"masked_phone": state["masked_phone"], "setup_id": setup_id},
        )

    @mcp_app.custom_route("/download-config/{token}", methods=["GET"])
    async def download_config(request: Request):
        token = request.path_params.get("token")
        domain = get_config().domain
        # Web setup always uses HTTP_AUTH mode
        config_json = generate_mcp_config_json(
            ServerMode.HTTP_AUTH,
            session_name="",  # Not used for HTTP_AUTH
            bearer_token=token,
            domain=domain,
        )
        headers = {"Content-Disposition": "attachment; filename=mcp.json"}
        return PlainTextResponse(
            config_json, media_type="application/json", headers=headers
        )
