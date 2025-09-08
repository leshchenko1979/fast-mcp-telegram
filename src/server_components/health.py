import time
from pathlib import Path

from starlette.responses import JSONResponse

from src.client.connection import MAX_ACTIVE_SESSIONS, _session_cache
from src.config.settings import SESSION_DIR
from src.server_components.web_setup import _setup_sessions


def register_health_routes(mcp_app):
    @mcp_app.custom_route("/health", methods=["GET"])
    async def health_check(request):
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
                "session_files": sum(
                    1 for p in Path(SESSION_DIR).glob("*.session") if p.is_file()
                ),
                "setup_sessions": len(_setup_sessions),
                "sessions": session_info,
            }
        )
