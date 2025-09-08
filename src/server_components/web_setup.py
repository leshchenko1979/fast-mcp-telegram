import os
import time
from pathlib import Path

from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.templating import Jinja2Templates

from src.client.connection import generate_bearer_token
from src.config.server_config import get_config
from src.config.settings import API_HASH, API_ID

# Templates (Phase 1)
# Use the project-level templates directory: /app/src/templates
templates = Jinja2Templates(
    directory=os.path.join(os.path.dirname(__file__), "..", "templates")
)

# Simple in-memory setup session store for web setup flow
_setup_sessions: dict[str, dict] = {}
# Use unified config for TTL
SETUP_SESSION_TTL_SECONDS = get_config().setup_session_ttl_seconds


async def cleanup_stale_setup_sessions():
    now = time.time()
    stale_ids: list[str] = []

    for sid, state in list(_setup_sessions.items()):
        created_at = state.get("created_at") or 0
        if created_at and (now - float(created_at) > SETUP_SESSION_TTL_SECONDS):
            stale_ids.append(sid)

    for sid in stale_ids:
        state = _setup_sessions.pop(sid, None) or {}
        client = state.get("client")
        session_path = state.get("session_path")

        try:
            if client:
                try:
                    await client.disconnect()
                except Exception:
                    pass
        finally:
            try:
                if isinstance(session_path, str) and session_path:
                    p = Path(session_path)
                    if p.name.startswith("setup-") and p.exists():
                        p.unlink(missing_ok=True)
            except Exception:
                pass


def register_web_setup_routes(mcp_app):
    @mcp_app.custom_route("/setup", methods=["GET"])
    async def setup_get(request):
        await cleanup_stale_setup_sessions()
        return templates.TemplateResponse(request, "setup.html")

    @mcp_app.custom_route("/setup/phone", methods=["POST"])
    async def setup_phone(request: Request):
        form = await request.form()
        phone_raw = str(form.get("phone", "")).strip()

        def _mask_phone(p: str) -> str:
            if not p or len(p) < 4:
                return p
            first = p[:3]
            last = p[-2:]
            return f"{first}{'*' * max(0, len(p) - 5)}{last}"

        masked = _mask_phone(phone_raw)
        await cleanup_stale_setup_sessions()
        setup_id = str(int(time.time() * 1000))
        temp_session_name = f"setup-{setup_id}.session"
        session_dir = get_config().session_directory
        temp_session_path = session_dir / temp_session_name

        from telethon import TelegramClient
        from telethon.errors.rpcerrorlist import PhoneNumberFloodError

        client = TelegramClient(temp_session_path, API_ID, API_HASH)
        await client.connect()
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

        if not setup_id or setup_id not in _setup_sessions:
            return JSONResponse(
                {"ok": False, "error": "Invalid setup session."}, status_code=400
            )

        await cleanup_stale_setup_sessions()

        state = _setup_sessions.get(setup_id)
        client = state.get("client")
        phone = state.get("phone")
        masked_phone = state.get("masked_phone")

        from telethon.errors import SessionPasswordNeededError

        try:
            await client.sign_in(phone=phone, code=code)
            state["authorized"] = True
            return await setup_generate(request)
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

    def _generate_mcp_config_json(domain: str, token: str) -> str:
        import json

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

    @mcp_app.custom_route("/setup/generate", methods=["POST"])
    async def setup_generate(request: Request):
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

        token = generate_bearer_token()

        src = Path(temp_session_path)
        session_dir = get_config().session_directory
        dst = session_dir / f"{token}.session"

        try:
            try:
                await client.send_read_acknowledge(None)  # touch session
            except Exception:
                pass

            try:
                await client.disconnect()
            except Exception:
                pass

            if src.exists():
                src.rename(dst)
        except Exception as e:
            return JSONResponse(
                {"ok": False, "error": f"Failed to persist session: {e}"},
                status_code=500,
            )

        domain = get_config().domain
        config_json = _generate_mcp_config_json(domain, token)

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

    @mcp_app.custom_route("/download-config/{token}", methods=["GET"])
    async def download_config(request: Request):
        token = request.path_params.get("token")
        domain = get_config().domain
        config_json = _generate_mcp_config_json(domain, token)
        headers = {"Content-Disposition": "attachment; filename=mcp.json"}
        return PlainTextResponse(
            config_json, media_type="application/json", headers=headers
        )
