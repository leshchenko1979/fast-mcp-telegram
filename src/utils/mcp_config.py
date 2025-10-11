"""
MCP configuration generation utilities.

Shared functions for generating MCP client configuration JSON
used by both CLI setup and web setup.
"""

import json

from ..config.server_config import ServerMode


def generate_mcp_config(
    mode: ServerMode,
    session_name: str,
    bearer_token: str | None,
    domain: str | None = None,
    api_id: str = "",
    api_hash: str = "",
) -> dict:
    """
    Generate MCP configuration for the given server mode.

    Args:
        mode: Server mode (STDIO, HTTP_NO_AUTH, HTTP_AUTH)
        session_name: Session name for STDIO mode
        bearer_token: Bearer token for HTTP_AUTH mode
        domain: Domain for HTTP_AUTH mode (optional)
        api_id: Telegram API ID for STDIO mode
        api_hash: Telegram API Hash for STDIO mode

    Returns:
        Dictionary with MCP configuration ready for JSON serialization
    """
    if mode == ServerMode.HTTP_AUTH:
        # Production HTTP mode with bearer token authentication
        domain_url = domain or "your-server.com"
        return {
            "mcpServers": {
                "telegram": {
                    "url": f"https://{domain_url}/mcp",
                    "headers": {"Authorization": f"Bearer {bearer_token}"},
                }
            }
        }

    if mode == ServerMode.HTTP_NO_AUTH:
        # Development HTTP mode without authentication
        return {
            "mcpServers": {
                "telegram": {
                    "url": "http://localhost:8000/mcp",
                }
            }
        }

    # STDIO mode with command and environment variables
    config = {
        "mcpServers": {
            "telegram": {
                "command": "fast-mcp-telegram",
                "env": {
                    "API_ID": api_id or "your_api_id",
                    "API_HASH": api_hash or "your_api_hash",
                },
            }
        }
    }
    # Add SESSION_NAME if it's not the default
    if session_name != "telegram":
        config["mcpServers"]["telegram"]["env"]["SESSION_NAME"] = session_name
    return config


def generate_mcp_config_json(
    mode: ServerMode,
    session_name: str,
    bearer_token: str | None,
    domain: str | None = None,
    api_id: str = "",
    api_hash: str = "",
) -> str:
    """
    Generate MCP configuration JSON string for the given server mode.

    Args:
        mode: Server mode (STDIO, HTTP_NO_AUTH, HTTP_AUTH)
        session_name: Session name for STDIO mode
        bearer_token: Bearer token for HTTP_AUTH mode
        domain: Domain for HTTP_AUTH mode (optional)
        api_id: Telegram API ID for STDIO mode
        api_hash: Telegram API Hash for STDIO mode

    Returns:
        JSON string with formatted MCP configuration
    """
    config = generate_mcp_config(
        mode, session_name, bearer_token, domain, api_id, api_hash
    )
    return json.dumps(config, indent=2)
