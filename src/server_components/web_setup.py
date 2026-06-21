import base64
import contextlib
import json
import logging
import os
import shutil
import time
import uuid
from io import BytesIO
from pathlib import Path
from typing import Any

import qrcode
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.templating import Jinja2Templates
from telethon import TelegramClient
from telethon.errors import PasswordHashInvalidError, SessionPasswordNeededError
from telethon.errors.rpcerrorlist import PhoneNumberFloodError
from telethon.tl.functions.account import GetPasswordRequest

from src.client.connection import (
    disconnect_and_evict_session,
    generate_bearer_token,
    is_s3_enabled,
)
from src.config.server_config import ServerMode, cfg
from src.server_components.auth_middleware import generate_url_based_config
from src.server_components.qr_login import QrLoginError, QrLoginManager
from src.server_components.session_token_validation import (
    InvalidSessionTokenError,
    session_file_path,
    validate_session_token,
)
from src.telemetry import flush_auth_events, send_auth_event
from src.utils.logging_utils import mask_phone_number
from src.utils.mcp_config import generate_mcp_config_json
from src.utils.proxy import build_mtproto_client_args

# Constants
SETUP_SESSION_PREFIX = "setup-"
REAUTH_SESSION_PREFIX = "reauth-"

REAUTHORIZE_NO_SESSION_MESSAGE = (
    "This token is not registered on this server yet. To use a new token, choose "
    "Create New Session. To refresh an existing one, enter the same bearer token "
    "you already use with this server."
)

REAUTH_SETUP_EXPIRED_MESSAGE = (
    "This setup step has expired or is no longer valid. Open Reauthorize Existing "
    "Session and enter your bearer token again to continue."
)

REAUTH_SESSION_CHECK_FAILED_MESSAGE = (
    "Unable to read or verify this session. Check your bearer token and try again."
)

REAUTH_PREPARE_FAILED_MESSAGE = "Unable to start reauthorization. Please try again."

DELETE_SESSION_FAILED_MESSAGE = (
    "Could not delete the session. Try again or contact the administrator."
)

INVALID_SETUP_SESSION_MESSAGE = "Invalid setup session."
NOT_AUTHORIZED_MESSAGE = "Not authorized yet."
INVALID_SETUP_STATE_MESSAGE = "Invalid setup state."
PHONE_INVALID_MESSAGE = (
    "Enter a valid phone number in international format, e.g. +1234567890."
)
PHONE_FLOOD_MESSAGE = "Too many attempts. Please wait before retrying."
BEARER_TOKEN_REQUIRED_MESSAGE = "Bearer token is required."
INVALID_BEARER_TOKEN_FORMAT_MESSAGE = (
    "Invalid bearer token. Use the token from setup or a URL-safe token from the CLI."
)
SESSION_PATH_ACCESS_ERROR_MESSAGE = (
    "Unable to access the session directory. Please contact the administrator."
)
SESSION_NOT_FOUND_MESSAGE = "Session not found. Please check your bearer token."
REAUTH_COMPLETE_FAILED_MESSAGE = (
    "Failed to complete reauthorization. Please try again from setup."
)

# Project templates directory (resolved from this package)
templates = Jinja2Templates(
    directory=os.path.join(os.path.dirname(__file__), "..", "templates")
)

# Simple in-memory setup session store for web setup flow
_setup_sessions: dict[str, dict] = {}
# SETUP_SESSION_TTL_SECONDS is resolved at call time via cfg() to honor
# test overrides and dynamic config changes (not bound at import time).

logger = logging.getLogger(__name__)


# Helper functions
def _normalize_phone_number(phone: str) -> str:
    """Normalize phone input to Telegram-compatible E.164-like form."""
    raw = (phone or "").strip()
    if not raw:
        return ""
    if raw.startswith("+"):
        digits = "".join(ch for ch in raw[1:] if ch.isdigit())
        return f"+{digits}" if digits else ""
    digits = "".join(ch for ch in raw if ch.isdigit())
    return f"+{digits}" if digits else ""


def _is_valid_phone_number(phone: str) -> bool:
    """Validate normalized Telegram phone number format."""
    if not phone.startswith("+"):
        return False
    digits = phone[1:]
    # Country code must not start with 0 and total digits should fit E.164.
    return (
        digits.isdigit() and len(digits) >= 7 and len(digits) <= 15 and digits[0] != "0"
    )


def validate_setup_session(setup_id: str) -> dict[str, Any] | None:
    """Validate setup session exists and return state, or None if invalid."""
    if not setup_id or setup_id not in _setup_sessions:
        return None
    return _setup_sessions[setup_id]


def _fragment(request: Request, template: str, context: dict[str, Any] | None = None):
    """Render an HTML fragment or full page template."""
    return templates.TemplateResponse(request, template, context or {})


def _setup_error_fragment(request: Request, error: str):
    """Return HTML error fragment for setup flow."""
    return _fragment(request, "fragments/error.html", {"error": error})


def _bearer_token_and_session_path(
    session_dir: Path, raw_token: str
) -> tuple[str, Path]:
    """Validate bearer token and return confined session file path."""
    token = validate_session_token(raw_token)
    return token, session_file_path(session_dir, token)


def _setup_token_path_error_fragment(
    request: Request,
    template: str,
    exc: BaseException,
) -> Any:
    """Map token/path resolution errors to setup HTML fragments."""
    if isinstance(exc, InvalidSessionTokenError):
        return _fragment(
            request, template, {"error": INVALID_BEARER_TOKEN_FORMAT_MESSAGE}
        )
    if isinstance(exc, OSError):
        logger.warning("Session path access failed: %s", exc)
        return _fragment(
            request, template, {"error": SESSION_PATH_ACCESS_ERROR_MESSAGE}
        )
    raise exc


def _2fa_form_context(
    setup_id: str,
    masked_phone: str,
    *,
    error: str | None = None,
    hint: str | None = None,
) -> dict:
    """Build template context for 2FA form fragment."""
    ctx: dict[str, Any] = {"setup_id": setup_id, "masked_phone": masked_phone}
    if error:
        ctx["error"] = error
    if hint:
        ctx["hint"] = hint
    return ctx


def create_session_client(session_path: Path) -> TelegramClient:
    """Create and return a configured TelegramClient."""
    config = cfg()
    client_kwargs = {
        "session": session_path,
        "api_id": int(config.api_id),
        "api_hash": config.api_hash,
        "entity_cache_limit": config.entity_cache_limit,
    }
    client_kwargs |= build_mtproto_client_args(config.mtproto_proxy, logger.info)
    return TelegramClient(**client_kwargs)


async def cleanup_stale_setup_sessions():
    """Clean up expired setup sessions, their temporary files, and QR sessions."""
    now = time.time()
    stale_ids: list[str] = []

    for sid, state in list(_setup_sessions.items()):
        created_at = state.get("created_at") or 0
        if created_at and (now - float(created_at) > cfg().setup_session_ttl_seconds):
            stale_ids.append(sid)

    for sid in stale_ids:
        state = _setup_sessions.pop(sid, None) or {}
        await _cleanup_session_state(state)

    # Also clean up expired QR sessions
    with contextlib.suppress(Exception):
        _get_qr_manager().cleanup_expired()


async def _cleanup_session_state(state: dict[str, Any]):
    """Clean up a single session state (client and temp files)."""
    client = state.get("client")
    session_path = state.get("session_path")

    # Flush any buffered auth telemetry for this flow
    fid = state.get("flow_id")
    if fid:
        flush_auth_events(fid)

    # Disconnect client
    if client:
        with contextlib.suppress(Exception):
            await client.disconnect()

    # Remove temporary session files
    with contextlib.suppress(Exception):
        if isinstance(session_path, str) and session_path:
            p = Path(session_path)
            if (
                p.name.startswith(SETUP_SESSION_PREFIX)
                or p.name.startswith(REAUTH_SESSION_PREFIX)
            ) and p.exists():
                p.unlink(missing_ok=True)


async def _safe_finish_client(client: Any) -> None:
    """Send read acknowledge and safely disconnect a Telegram client."""
    with contextlib.suppress(Exception):
        await client.send_read_acknowledge(None)
    with contextlib.suppress(Exception):
        await client.disconnect()


async def _persist_session_and_generate_config(
    request: Request,
    client: Any,
    temp_session_path: str | Path,
    setup_id: str,
    *,
    desired_token: str | None = None,
    state: dict[str, Any] | None = None,
) -> Any:
    """Persist a temporary session file, generate bearer token, and return a config fragment.

    Steps: finish client → resolve token → rename session file → generate configs.

    When *state* is provided (a mutable dict), it is updated with the generated
    token, header config, and URL config for HTMX re-entry protection.

    Returns:
        A Starlette response with ``fragments/config.html`` (success) or an error fragment.
    """
    src = Path(temp_session_path)
    await _safe_finish_client(client)

    session_dir = cfg().session_directory
    try:
        if desired_token:
            token, dst = _bearer_token_and_session_path(session_dir, desired_token)
        else:
            token = generate_bearer_token()
            dst = session_file_path(session_dir, token)
    except (InvalidSessionTokenError, OSError) as e:
        return _setup_token_path_error_fragment(request, "fragments/error.html", e)

    if desired_token and dst.exists():
        return _setup_error_fragment(
            request, f"Session with token '{token}' already exists"
        )

    try:
        if src.exists():
            src.rename(dst)
    except Exception as e:
        return _setup_error_fragment(request, f"Failed to persist session: {e}")

    # S3: checkpoint + upload newly created session
    if is_s3_enabled():
        from src import s3_session

        try:
            if not await s3_session.checkpoint_and_upload(token, dst):
                return _setup_error_fragment(
                    request,
                    "Session created but WAL checkpoint failed. "
                    "Session will work now but won't survive container restart.",
                )
        except Exception as e:
            logger.error("S3 upload after /setup failed for %s...: %s", token[:8], e)
            return _setup_error_fragment(
                request,
                f"Session created but S3 backup failed: {e}. "
                "Session will work now but won't survive container restart.",
            )

    domain = cfg().domain
    header_config_json = generate_mcp_config_json(
        ServerMode.HTTP_AUTH,
        session_name="",
        bearer_token=token,
        domain=domain,
    )
    url_config = generate_url_based_config(domain or "your-server.com", token)
    url_config_json = json.dumps(url_config, indent=2)

    # Update state for HTMX re-entry guard (used by QR login flow)
    if state is not None:
        state.update(
            token=token,
            _header_config_json=header_config_json,
            _url_config_json=url_config_json,
        )

    return _fragment(
        request,
        "fragments/config.html",
        {
            "setup_id": setup_id,
            "token": token,
            "header_config_json": header_config_json,
            "url_config_json": url_config_json,
        },
    )


# Global QR login manager for in-memory QR sessions.
_qr_manager: QrLoginManager | None = None


def _get_qr_manager() -> QrLoginManager:
    """Get or create the global QR login manager singleton."""
    global _qr_manager
    if _qr_manager is None:
        _qr_manager = QrLoginManager(timeout_seconds=60)
    return _qr_manager


async def _complete_qr_login(
    request: Request,
    state: dict[str, Any],
    qr_session_id: str,
    setup_id: str,
    authorized_client: Any = None,
) -> Any:
    """Finalise a QR login: persist session file and generate bearer token.

    Args:
        authorized_client: Optional pre-authorized Telethon client (for 2FA flow).
            If None, the client is fetched from the QR manager (direct scan flow).
    """
    qr_mgr = _get_qr_manager()
    if authorized_client is None:
        authorized_client = qr_mgr.get_client(qr_session_id)

    response = await _persist_session_and_generate_config(
        request,
        authorized_client,
        state["session_path"],
        setup_id,
        state=state,
    )

    # HTMX re-entry guard: store completed state so duplicate polls
    # don't re-execute the (now-persisted) session
    state.update(created_at=time.time(), _finalized=True)
    return response


async def setup_complete_reauth(request: Request):
    """Complete reauthorization by replacing the original session file with reauthorized version."""
    form = await request.form()
    setup_id = str(form.get("setup_id", "")).strip()

    if not setup_id or setup_id not in _setup_sessions:
        return _setup_error_fragment(request, INVALID_SETUP_SESSION_MESSAGE)

    state = _setup_sessions[setup_id]
    if not state.get("authorized"):
        return _setup_error_fragment(request, NOT_AUTHORIZED_MESSAGE)

    client = state.get("client")
    original_path_val = state.get("original_session_path")
    temp_path_val = state.get("temp_session_path")
    existing_token = state.get("existing_token")

    if not original_path_val or not temp_path_val or not client or not existing_token:
        return _setup_error_fragment(request, INVALID_SETUP_STATE_MESSAGE)

    original_path = Path(original_path_val)
    temp_path = Path(temp_path_val)

    try:
        await _safe_finish_client(client)

        # Replace original session with reauthorized one
        temp_path.replace(original_path)

        # S3: checkpoint + upload reauthorized session
        if is_s3_enabled():
            from src import s3_session

            try:
                await s3_session.checkpoint_and_upload(existing_token, original_path)
                logger.info(
                    "S3: uploaded reauthorized session for %s...", existing_token[:8]
                )
            except Exception as e:
                logger.warning(
                    "S3 upload failed for reauth %s...: %s", existing_token[:8], e
                )

        # Clean up
        state.clear()

        return _fragment(
            request,
            "fragments/success.html",
            {
                "message": f"Session reauthorized successfully! Your token {existing_token[:8]}... is now active.",
                "token": existing_token,
            },
        )

    except Exception as e:
        logger.warning("Failed to complete reauthorization: %s", e)
        return _setup_error_fragment(request, REAUTH_COMPLETE_FAILED_MESSAGE)


async def setup_generate(request: Request):
    """Complete new session setup by generating token and config."""
    form = await request.form()
    setup_id = str(form.get("setup_id", "")).strip()

    if not setup_id or setup_id not in _setup_sessions:
        return _setup_error_fragment(request, INVALID_SETUP_SESSION_MESSAGE)

    state = _setup_sessions[setup_id]
    if not state.get("authorized"):
        return _setup_error_fragment(request, NOT_AUTHORIZED_MESSAGE)

    client = state.get("client")
    temp_session_path = state.get("session_path")

    if not client or not temp_session_path:
        return _setup_error_fragment(request, INVALID_SETUP_STATE_MESSAGE)

    desired_token = state.get("desired_token")
    response = await _persist_session_and_generate_config(
        request,
        client,
        temp_session_path,
        setup_id,
        desired_token=desired_token,
    )

    state.update(created_at=time.time())
    return response


async def _complete_authentication(request: Request, state: dict[str, Any]):
    """Complete authentication flow based on session type."""
    if state.get("reauthorizing"):
        return await setup_complete_reauth(request)
    return await setup_generate(request)


def _categorize_web_error(exc: BaseException) -> str:
    """Map Telethon/runtime exceptions to ADR 0008 error categories."""
    from telethon.errors import (
        FloodWaitError,
        PasswordHashInvalidError,
        PhoneCodeExpiredError,
        PhoneCodeInvalidError,
        PhoneNumberBannedError,
        PhoneNumberInvalidError,
        PhoneNumberUnoccupiedError,
    )

    if isinstance(exc, PasswordHashInvalidError):
        return "2fa_wrong_password"
    if isinstance(exc, PhoneCodeInvalidError):
        return "invalid_code"
    if isinstance(exc, PhoneCodeExpiredError):
        return "code_expired"
    if isinstance(exc, FloodWaitError):
        return "flood_wait"
    if isinstance(exc, PhoneNumberBannedError):
        return "phone_banned"
    if isinstance(exc, PhoneNumberInvalidError):
        return "phone_invalid"
    if isinstance(exc, PhoneNumberUnoccupiedError):
        return "phone_unoccupied"
    if isinstance(exc, ConnectionError):
        return "connect_failed"
    if isinstance(exc, (TimeoutError, OSError)):
        return "timeout"
    return "unknown"


def register_web_setup_routes(mcp_app):
    @mcp_app.custom_route("/setup", methods=["GET"])
    async def setup_get(request):
        await cleanup_stale_setup_sessions()
        return _fragment(request, "setup.html")

    @mcp_app.custom_route("/setup/phone", methods=["POST"])
    async def setup_phone(request: Request):
        form = await request.form()
        phone_raw = _normalize_phone_number(str(form.get("phone", "")))
        if not _is_valid_phone_number(phone_raw):
            return _fragment(
                request,
                "fragments/new_session_phone_form.html",
                {"error": PHONE_INVALID_MESSAGE},
            )

        masked = mask_phone_number(phone_raw)
        await cleanup_stale_setup_sessions()

        setup_id = str(int(time.time() * 1000))
        temp_session_path = (
            cfg().session_directory / f"{SETUP_SESSION_PREFIX}{setup_id}.session"
        )

        client = create_session_client(temp_session_path)
        try:
            await client.connect()
            logger.info("Connected setup client for phone %s", masked)
        except Exception as e:
            logger.error("Failed to connect setup client for phone %s: %s", masked, e)
            await client.disconnect()
            temp_session_path.unlink(missing_ok=True)
            return _setup_error_fragment(request, f"Failed to connect: {e}")

        try:
            sent = await client.send_code_request(phone_raw)
            logger.info(
                "Code sent for phone %s: type=%s, phone_code_hash=%s, timeout=%s",
                masked,
                getattr(sent, "type", None),
                getattr(sent, "phone_code_hash", None),
                getattr(sent, "timeout", None),
            )
        except PhoneNumberFloodError:
            await client.disconnect()
            temp_session_path.unlink(missing_ok=True)
            return _fragment(
                request,
                "fragments/new_session_phone_form.html",
                {"error": PHONE_FLOOD_MESSAGE},
            )

        _setup_sessions[setup_id] = {
            "phone": phone_raw,
            "masked_phone": masked,
            "client": client,
            "session_path": str(temp_session_path),
            "authorized": False,
            "created_at": time.time(),
            "flow_id": str(uuid.uuid4()),
        }

        # Auth telemetry: user submitted phone, code requested
        fid = _setup_sessions[setup_id]["flow_id"]
        send_auth_event(
            event="user_submitted_phone",
            flow_id=fid,
            method="phone",
            branch="phone_code",
        )
        send_auth_event(
            event="code_requested", flow_id=fid, method="phone", branch="phone_code"
        )

        return _fragment(
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
            return _setup_error_fragment(request, INVALID_SETUP_SESSION_MESSAGE)

        await cleanup_stale_setup_sessions()

        client = state.get("client")
        phone = state.get("phone")
        masked_phone = state.get("masked_phone") or ""

        if not client or not phone:
            return _setup_error_fragment(request, INVALID_SETUP_SESSION_MESSAGE)

        fid = state.get("flow_id", "")
        is_reauth = state.get("reauthorizing", False)
        method = "reauth" if is_reauth else "phone"
        branch = "reauth_code" if is_reauth else "phone_code"
        send_auth_event(
            event="user_submitted_code", flow_id=fid, method=method, branch=branch
        )

        try:
            await client.sign_in(phone=phone, code=code)
            state["authorized"] = True
            logger.info("Phone %s verified successfully", masked_phone)
            send_auth_event(
                event="code_validated", flow_id=fid, method=method, branch=branch
            )
            send_auth_event(
                event="session_established", flow_id=fid, method=method, branch=branch
            )
            flush_auth_events(fid)
            return await _complete_authentication(request, state)
        except SessionPasswordNeededError:
            send_auth_event(
                event="code_validated", flow_id=fid, method=method, branch=branch
            )
            hint = ""
            with contextlib.suppress(Exception):
                pw = await client(GetPasswordRequest())
                hint = (pw.hint or "").strip()
            state["hint"] = hint
            ctx = _2fa_form_context(setup_id, masked_phone, hint=hint or "")
            return _fragment(request, "fragments/2fa_form.html", ctx)
        except Exception as e:
            logger.warning("Verification failed for phone %s: %s", masked_phone, e)
            send_auth_event(
                event="code_validated",
                flow_id=fid,
                method=method,
                branch=branch,
                error=_categorize_web_error(e),
            )
            flush_auth_events(fid)
            return _fragment(
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
            return _setup_error_fragment(request, INVALID_SETUP_SESSION_MESSAGE)

        await cleanup_stale_setup_sessions()

        client = state.get("client")
        masked_phone = state.get("masked_phone") or ""

        if not client:
            return _setup_error_fragment(request, INVALID_SETUP_SESSION_MESSAGE)

        fid = state.get("flow_id", "")
        is_reauth = state.get("reauthorizing", False)
        method = "reauth" if is_reauth else "phone"
        branch = "reauth_2fa" if is_reauth else "phone_2fa"
        send_auth_event(
            event="user_submitted_password", flow_id=fid, method=method, branch=branch
        )

        try:
            await client.sign_in(password=password)
            state["authorized"] = True
            send_auth_event(
                event="password_validated", flow_id=fid, method=method, branch=branch
            )
            send_auth_event(
                event="session_established", flow_id=fid, method=method, branch=branch
            )
            flush_auth_events(fid)
            return await _complete_authentication(request, state)
        except PasswordHashInvalidError:
            send_auth_event(
                event="password_validated",
                flow_id=fid,
                method=method,
                branch=branch,
                error="2fa_wrong_password",
            )
            hint = state.get("hint") or ""
            return _fragment(
                request,
                "fragments/2fa_form.html",
                _2fa_form_context(
                    setup_id,
                    masked_phone,
                    error="Invalid password. Please try again.",
                    hint=hint or None,
                ),
            )
        except Exception as e:
            logger.warning("2FA failed: %s", e)
            send_auth_event(
                event="password_validated",
                flow_id=fid,
                method=method,
                branch=branch,
                error=_categorize_web_error(e),
            )
            flush_auth_events(fid)
            hint = state.get("hint") or ""
            return _fragment(
                request,
                "fragments/2fa_form.html",
                _2fa_form_context(
                    setup_id,
                    masked_phone,
                    error=f"Authentication failed: {e}",
                    hint=hint or None,
                ),
            )

    @mcp_app.custom_route("/setup/reauthorize", methods=["POST"])
    async def setup_reauthorize(request: Request):
        form = await request.form()
        existing_token = str(form.get("token", "")).strip()

        if not existing_token:
            return _fragment(
                request,
                "fragments/reauthorize_token_form.html",
                {"error": BEARER_TOKEN_REQUIRED_MESSAGE},
            )

        try:
            _, session_path = _bearer_token_and_session_path(
                cfg().session_directory, existing_token
            )
        except (InvalidSessionTokenError, OSError) as e:
            return _setup_token_path_error_fragment(
                request, "fragments/reauthorize_token_form.html", e
            )
        # S3 fallback: try downloading session from S3 if local file is missing
        if not session_path.exists() and is_s3_enabled():
            from src import s3_session

            try:
                if await s3_session.download(existing_token, session_path):
                    logger.info(
                        "S3: downloaded session for reauthorize %s...",
                        existing_token[:8],
                    )
            except Exception as e:
                logger.warning(
                    "S3 download failed for reauthorize %s...: %s",
                    existing_token[:8],
                    e,
                )

        if not session_path.exists():
            return _fragment(
                request,
                "fragments/reauthorize_token_form.html",
                {"error": REAUTHORIZE_NO_SESSION_MESSAGE},
            )

        # Check if session needs reauthorization
        try:
            client = create_session_client(session_path)
            await client.connect()
            is_authorized = await client.is_user_authorized()
            await client.disconnect()

            if is_authorized:
                return _fragment(
                    request,
                    "fragments/success.html",
                    {"message": "Your session is already authorized and working!"},
                )
        except Exception as e:
            logger.warning("Error checking session for reauthorize: %s", e)
            return _fragment(
                request,
                "fragments/reauthorize_token_form.html",
                {"error": REAUTH_SESSION_CHECK_FAILED_MESSAGE},
            )

        # Session needs reauthorization - create temp session for reauth
        setup_id = str(int(time.time() * 1000))
        temp_session_path = (
            cfg().session_directory / f"{REAUTH_SESSION_PREFIX}{setup_id}.session"
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
                "flow_id": str(uuid.uuid4()),
            }

            # Auth telemetry: reauth flow initiated
            fid = _setup_sessions[setup_id]["flow_id"]
            send_auth_event(
                event="reauth_initiated",
                flow_id=fid,
                method="reauth",
                branch="reauth_code",
            )

            # Ask for phone number since we can't extract it securely from session
            return _fragment(
                request, "fragments/reauthorize_phone.html", {"setup_id": setup_id}
            )

        except Exception as e:
            logger.warning("Failed to prepare reauthorization: %s", e)
            await client.disconnect()
            temp_session_path.unlink(missing_ok=True)
            return _fragment(
                request,
                "fragments/reauthorize_token_form.html",
                {"error": REAUTH_PREPARE_FAILED_MESSAGE},
            )

    @mcp_app.custom_route("/setup/reauthorize/phone", methods=["POST"])
    async def setup_reauthorize_phone(request: Request):
        form = await request.form()
        setup_id = str(form.get("setup_id", "")).strip()
        phone_raw = _normalize_phone_number(str(form.get("phone", "")))
        if not _is_valid_phone_number(phone_raw):
            return _fragment(
                request,
                "fragments/reauthorize_phone.html",
                {"setup_id": setup_id, "error": PHONE_INVALID_MESSAGE},
            )

        state = validate_setup_session(setup_id)
        if not state:
            return _fragment(
                request,
                "fragments/reauthorize_token_form.html",
                {"error": REAUTH_SETUP_EXPIRED_MESSAGE},
            )

        client = state.get("client")
        if not client:
            return _fragment(
                request,
                "fragments/reauthorize_token_form.html",
                {"error": REAUTH_SETUP_EXPIRED_MESSAGE},
            )

        try:
            sent = await client.send_code_request(phone_raw)
            logger.info(
                "Reauthorization code sent for phone %s: type=%s, phone_code_hash=%s, timeout=%s",
                mask_phone_number(phone_raw),
                getattr(sent, "type", None),
                getattr(sent, "phone_code_hash", None),
                getattr(sent, "timeout", None),
            )
        except PhoneNumberFloodError:
            return _fragment(
                request,
                "fragments/reauthorize_phone.html",
                {"setup_id": setup_id, "error": PHONE_FLOOD_MESSAGE},
            )
        except Exception as e:
            logger.warning("Failed to send reauthorization code: %s", e)
            return _fragment(
                request,
                "fragments/reauthorize_phone.html",
                {
                    "setup_id": setup_id,
                    "error": f"Failed to send code: {e}",
                },
            )

        state["phone"] = phone_raw
        state["masked_phone"] = mask_phone_number(phone_raw)

        # Auth telemetry: user submitted phone for reauth, code requested
        fid = state.get("flow_id", "")
        send_auth_event(
            event="user_submitted_phone",
            flow_id=fid,
            method="reauth",
            branch="reauth_code",
        )
        send_auth_event(
            event="code_requested", flow_id=fid, method="reauth", branch="reauth_code"
        )

        return _fragment(
            request,
            "fragments/code_form.html",
            {"masked_phone": state["masked_phone"], "setup_id": setup_id},
        )

    @mcp_app.custom_route("/setup/delete", methods=["POST"])
    async def setup_delete(request: Request):
        """Delete a session file by bearer token."""
        form = await request.form()
        token = str(form.get("token", "")).strip()

        if not token:
            return _fragment(
                request,
                "fragments/delete_session_form.html",
                {"error": BEARER_TOKEN_REQUIRED_MESSAGE},
            )

        try:
            token, session_path = _bearer_token_and_session_path(
                cfg().session_directory, token
            )
        except (InvalidSessionTokenError, OSError) as e:
            return _setup_token_path_error_fragment(
                request, "fragments/delete_session_form.html", e
            )
        # S3 mode: local file may be evicted — skip existence check
        if not is_s3_enabled() and not session_path.exists():
            return _fragment(
                request,
                "fragments/delete_session_form.html",
                {"error": SESSION_NOT_FOUND_MESSAGE},
            )

        try:
            # Evict from cache (checkpoint + disconnect + upload to preserve state)
            await disconnect_and_evict_session(token)

            # S3: delete session from S3 BEFORE local unlink
            if is_s3_enabled():
                from src import s3_session

                await s3_session.delete(token)
                logger.info("S3: deleted session for %s...", token[:8])

            # Delete local file (may already be gone if S3 mode evicted it)
            session_path.unlink(missing_ok=True)

            return _fragment(
                request,
                "fragments/success.html",
                {
                    "message": f"Session successfully deleted. Token {token[:8]}... is no longer valid."
                },
            )

        except Exception as e:
            logger.warning("Failed to delete session: %s", e)
            return _fragment(
                request,
                "fragments/delete_session_form.html",
                {"error": DELETE_SESSION_FAILED_MESSAGE},
            )

    @mcp_app.custom_route("/download-config/{token}", methods=["GET"])
    async def download_config(request: Request):
        token = request.path_params.get("token")
        domain = cfg().domain
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

    # ------------------------------------------------------------------
    # QR login routes
    # ------------------------------------------------------------------

    @mcp_app.custom_route("/setup/qr", methods=["POST"])
    async def setup_qr(request: Request):
        """Create a QR login session and return the QR code image.

        Returns an HTML fragment that displays the QR code and starts
        polling for scan completion.
        """
        await cleanup_stale_setup_sessions()

        setup_id = str(int(time.time() * 1000))
        temp_session_path = (
            cfg().session_directory / f"{SETUP_SESSION_PREFIX}{setup_id}.session"
        )

        client = create_session_client(temp_session_path)
        try:
            await client.connect()
        except Exception as e:
            await client.disconnect()
            temp_session_path.unlink(missing_ok=True)
            return _setup_error_fragment(request, f"Failed to connect: {e}")

        qr_mgr = _get_qr_manager()
        try:
            qr_session_id, qr_url = await qr_mgr.create_session(client)
        except QrLoginError as e:
            await client.disconnect()
            temp_session_path.unlink(missing_ok=True)
            return _setup_error_fragment(request, str(e))

        # Generate QR code image as base64 PNG
        qr = qrcode.QRCode(box_size=10, border=2)
        qr.add_data(qr_url)
        qr.make(fit=True)
        img = qr.make_image()
        buf = BytesIO()
        img.save(buf, format="PNG")
        qr_b64 = base64.b64encode(buf.getvalue()).decode()

        # Store setup session state
        _setup_sessions[setup_id] = {
            "qr_session_id": qr_session_id,
            "session_path": str(temp_session_path),
            "client": client,
            "authorized": False,
            "created_at": time.time(),
            "flow_id": str(uuid.uuid4()),
        }

        # Auth telemetry: QR session created
        fid = _setup_sessions[setup_id]["flow_id"]
        send_auth_event(
            event="qr_session_created", flow_id=fid, method="qr", branch="qr_scan"
        )

        return _fragment(
            request,
            "fragments/qr_display.html",
            {
                "setup_id": setup_id,
                "qr_image": qr_b64,
            },
        )

    @mcp_app.custom_route("/setup/qr/status", methods=["GET"])
    async def setup_qr_status(request: Request):
        """Poll QR login status.

        Returns an HTML fragment:
        - ``qr_polling.html`` while waiting (keeps HTMX polling alive)
        - ``qr_2fa.html`` when the scanned account requires a 2FA password
        - ``config.html`` when the QR is scanned (token + MCP config)
        - ``qr_expired.html`` when the QR expires
        """
        setup_id = request.query_params.get("setup_id", "")
        state = _setup_sessions.get(setup_id)

        if not state:
            return _fragment(
                request, "fragments/error.html", {"error": "Session not found."}
            )

        # Guard: prevent re-entering completion for already-finalized sessions
        # (HTMX can send duplicate requests for the same completed status)
        if state.get("_finalized"):
            return _fragment(
                request,
                "fragments/config.html",
                {
                    "setup_id": setup_id,
                    "token": state.get("token", ""),
                    "header_config_json": state.get("_header_config_json", "{}"),
                    "url_config_json": state.get("_url_config_json", "{}"),
                },
            )

        qr_session_id = state.get("qr_session_id")
        if not qr_session_id:
            return _fragment(
                request,
                "fragments/error.html",
                {"error": "No QR session in progress."},
            )

        qr_mgr = _get_qr_manager()
        status = await qr_mgr.poll_status(qr_session_id)

        fid = state.get("flow_id", "")

        if status == "completed":
            state["authorized"] = True
            send_auth_event(
                event="user_scanned_qr", flow_id=fid, method="qr", branch="qr_scan"
            )
            send_auth_event(
                event="qr_login_confirmed", flow_id=fid, method="qr", branch="qr_scan"
            )
            send_auth_event(
                event="session_established", flow_id=fid, method="qr", branch="qr_scan"
            )
            flush_auth_events(fid)
            return await _complete_qr_login(request, state, qr_session_id, setup_id)

        if status == "expired":
            send_auth_event(
                event="qr_expired", flow_id=fid, method="qr", branch="qr_scan"
            )
            flush_auth_events(fid)
            return _fragment(
                request,
                "fragments/qr_expired.html",
                {"setup_id": setup_id},
            )

        if status == "2fa_required":
            send_auth_event(
                event="user_scanned_qr", flow_id=fid, method="qr", branch="qr_2fa"
            )
            hint = qr_mgr.get_password_hint(qr_session_id)
            response = _fragment(
                request,
                "fragments/qr_2fa.html",
                {"setup_id": setup_id, "hint": hint},
            )
            response.headers["HX-Reswap"] = "outerHTML"
            return response

        # Still pending — keep polling
        return _fragment(
            request,
            "fragments/qr_polling.html",
            {"setup_id": setup_id},
        )

    @mcp_app.custom_route("/setup/qr/2fa", methods=["POST"])
    async def setup_qr_2fa(request: Request):
        """Complete QR login by providing the 2FA password.

        Called when the scanned Telegram account requires two-step verification.
        """
        form = await request.form()
        setup_id = str(form.get("setup_id", "")).strip()
        password = str(form.get("password", "")).strip()

        state = _setup_sessions.get(setup_id)
        if not state:
            return _fragment(
                request, "fragments/error.html", {"error": "Session not found."}
            )

        client = state.get("client")
        if not client:
            return _fragment(
                request,
                "fragments/error.html",
                {"error": "Login session expired. Please try again."},
            )

        qr_session_id = state.get("qr_session_id")
        if not qr_session_id:
            return _fragment(
                request,
                "fragments/error.html",
                {"error": "No QR session in progress."},
            )

        qr_mgr = _get_qr_manager()
        hint = qr_mgr.get_password_hint(qr_session_id)

        fid = state.get("flow_id", "")
        send_auth_event(
            event="user_submitted_password", flow_id=fid, method="qr", branch="qr_2fa"
        )

        try:
            await client.sign_in(password=password)
            state["authorized"] = True
            logger.info("QR login 2FA completed for session %s", setup_id)
            send_auth_event(
                event="password_validated", flow_id=fid, method="qr", branch="qr_2fa"
            )
            send_auth_event(
                event="session_established", flow_id=fid, method="qr", branch="qr_2fa"
            )
            flush_auth_events(fid)
        except PasswordHashInvalidError:
            send_auth_event(
                event="password_validated",
                flow_id=fid,
                method="qr",
                branch="qr_2fa",
                error="2fa_wrong_password",
            )
            return _fragment(
                request,
                "fragments/qr_2fa.html",
                {
                    "setup_id": setup_id,
                    "hint": hint,
                    "error": "Invalid password. Please try again.",
                },
            )
        except Exception as e:
            logger.warning("QR 2FA failed for session %s: %s", setup_id, e)
            send_auth_event(
                event="password_validated",
                flow_id=fid,
                method="qr",
                branch="qr_2fa",
                error=_categorize_web_error(e),
            )
            flush_auth_events(fid)
            return _fragment(
                request,
                "fragments/qr_2fa.html",
                {
                    "setup_id": setup_id,
                    "hint": hint,
                    "error": f"Authentication failed: {e}",
                },
            )

        # Password accepted — persist session and generate token
        return await _complete_qr_login(
            request, state, qr_session_id, setup_id, authorized_client=client
        )
