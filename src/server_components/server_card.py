"""/.well-known/mcp/ discovery endpoints (SEP-1649 + SEP-1960).

Two endpoints for MCP server discovery:

1. ``/.well-known/mcp/server-card.json`` (SEP-1649/SEP-2127) — rich server
   card with identity, tools, capabilities, and auth info.  Aimed at
   catalogs and humans browsing.

2. ``/.well-known/mcp`` (SEP-1960) — terse machine-readable manifest
   enumerating transport endpoints, capabilities, and auth methods.
   Aimed at clients deciding how to connect.

Both are served over HTTPS with ``application/json``, nosniff, cache,
and permissive CORS headers per the spec.

Tool definitions are extracted from the FastMCP server instance after all
tools are registered, eliminating drift between advertised and actual tools.
"""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from src._version import __version__

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

# Common headers per SEP-1960 / SEP-1649 spec
_SPEC_HEADERS = {
    "Cache-Control": "public, max-age=3600",
    "X-Content-Type-Options": "nosniff",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization",
}


def register_server_card_route(mcp_app: FastMCP) -> None:
    """Register both ``/.well-known/mcp/`` discovery HTTP routes.

    Available only in HTTP transport mode.  Smithery.ai and similar tools
    will discover them when connecting to a publicly reachable deployment.

    Must be called *after* ``register_tools(mcp_app)`` so all tools are
    available via ``mcp_app.list_tools()``.  Cards are built lazily on
    the first request and then cached for the lifetime of the process.
    """
    _card_cache: dict[str, tuple[dict, str]] = {}

    # ── SEP-1649: rich server card ────────────────────────────────────
    @mcp_app.custom_route("/.well-known/mcp/server-card.json", methods=["GET"])
    async def server_card(request: Request):
        cache_key = "card"
        if cache_key not in _card_cache:
            tools = await mcp_app.list_tools()
            card = {
                "$schema": "https://static.modelcontextprotocol.io/schemas/v1/server-card.schema.json",
                "name": "fast-mcp-telegram",
                "title": "Telegram MCP Server",
                "description": (
                    "Multi-tenant Telegram gateway for AI agents — "
                    "HTTP+stdio transport, 8 agent-optimized tools, "
                    "MTProto User API"
                ),
                "version": __version__,
                "websiteUrl": "https://github.com/leshchenko1979/fast-mcp-telegram",
                "repository": {
                    "url": "https://github.com/leshchenko1979/fast-mcp-telegram",
                    "source": "github",
                },
                "remotes": [
                    {
                        "transport": {
                            "type": "streamable-http",
                            "url": "/v1/mcp",
                        },
                    },
                    {
                        "transport": {
                            "type": "stdio",
                        },
                    },
                ],
                "capabilities": {
                    "tools": {"listChanged": True},
                    "resources": {"listChanged": False},
                    "prompts": {"listChanged": False},
                },
                "authentication": {
                    "required": False,
                    "schemes": ["bearer"],
                },
                "tools": [
                    {
                        k: v
                        for k, v in {
                            "name": t.name,
                            "description": t.description or "",
                            "inputSchema": t.parameters,
                            "outputSchema": t.output_schema,
                            "annotations": (
                                t.annotations.model_dump(exclude_none=True)
                                if t.annotations
                                else None
                            ),
                        }.items()
                        if v is not None
                    }
                    for t in tools
                ],
                "resources": [],
                "prompts": [],
            }
            _card_cache[cache_key] = (card, _compute_etag(card))

        card, etag = _card_cache[cache_key]

        if request.headers.get("if-none-match") == etag:
            return Response(status_code=304, headers={"ETag": etag})

        return JSONResponse(
            card,
            headers={**_SPEC_HEADERS, "ETag": etag},
        )

    # ── SEP-1960: machine-readable manifest ───────────────────────────
    @mcp_app.custom_route("/.well-known/mcp", methods=["GET"])
    async def mcp_manifest(request: Request):
        cache_key = "manifest"
        if cache_key not in _card_cache:
            tools = await mcp_app.list_tools()
            manifest = {
                "$schema": "https://static.modelcontextprotocol.io/schemas/v1/manifest.schema.json",
                "name": "fast-mcp-telegram",
                "version": __version__,
                "remotes": [
                    {
                        "transport": {
                            "type": "streamable-http",
                            "url": "/v1/mcp",
                        },
                        "authentication": {
                            "required": False,
                            "schemes": ["bearer"],
                        },
                    },
                    {
                        "transport": {
                            "type": "stdio",
                        },
                    },
                ],
                "capabilities": {
                    "tools": True,
                    "resources": False,
                    "prompts": False,
                },
                "protocolVersions": ["2025-03-26"],
                "toolCount": len(tools),
            }
            _card_cache[cache_key] = (manifest, _compute_etag(manifest))

        manifest, etag = _card_cache[cache_key]

        if request.headers.get("if-none-match") == etag:
            return Response(status_code=304, headers={"ETag": etag})

        return JSONResponse(
            manifest,
            headers={**_SPEC_HEADERS, "ETag": etag},
        )

    # ── OPTIONS handlers for CORS preflight ───────────────────────────
    @mcp_app.custom_route("/.well-known/mcp/server-card.json", methods=["OPTIONS"])
    async def cors_preflight_card(request: Request):
        return Response(status_code=204, headers=_SPEC_HEADERS)

    @mcp_app.custom_route("/.well-known/mcp", methods=["OPTIONS"])
    async def cors_preflight_manifest(request: Request):
        return Response(status_code=204, headers=_SPEC_HEADERS)


def _compute_etag(doc: dict) -> str:
    """Content-based ETag derived from the JSON representation."""
    raw = json.dumps(doc, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return f'"{hashlib.md5(raw, usedforsecurity=False).hexdigest()}"'
