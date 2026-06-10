"""Tests for the @require_auth decorator.

The decorator is the central auth gate for all MCP tools. It:
- Returns structured guidance (not 401) when unauthenticated
- Passes through when auth is disabled (stdio mode)
- Validates bearer token format and session file existence
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.server_components.auth import (
    _auth_guidance_response,
    require_auth,
)
from src.server_components.session_token_validation import InvalidSessionTokenError

# ---------------------------------------------------------------------------
# require_auth decorator
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_require_auth_disabled_passthrough():
    """When auth is disabled, the tool runs without any auth check."""
    mock_func = AsyncMock(return_value={"result": "ok"})
    decorated = require_auth(mock_func)

    config = MagicMock()
    config.disable_auth = True

    with patch("src.server_components.auth.cfg", return_value=config):
        result = await decorated()

    assert result == {"result": "ok"}
    mock_func.assert_called_once()


@pytest.mark.asyncio
async def test_require_auth_no_token_returns_guidance():
    """When no bearer token is present, return auth guidance."""
    mock_func = AsyncMock()
    decorated = require_auth(mock_func)

    config = MagicMock()
    config.disable_auth = False

    with (
        patch("src.server_components.auth.cfg", return_value=config),
        patch(
            "src.server_components.auth._get_bearer_token_from_http",
            return_value=None,
        ),
    ):
        result = await decorated()

    assert result["isError"] is True
    guidance = result["content"][0]["text"]
    assert "Authentication Required" in guidance
    assert "/setup" in guidance
    mock_func.assert_not_called()


@pytest.mark.asyncio
async def test_require_auth_invalid_token_returns_guidance():
    """When the bearer token format is invalid, return auth guidance."""
    mock_func = AsyncMock()
    decorated = require_auth(mock_func)

    config = MagicMock()
    config.disable_auth = False

    with (
        patch("src.server_components.auth.cfg", return_value=config),
        patch(
            "src.server_components.auth._get_bearer_token_from_http",
            return_value="bad-token",
        ),
        patch(
            "src.server_components.auth.validate_session_token",
            side_effect=InvalidSessionTokenError("bad format"),
        ),
    ):
        result = await decorated()

    assert result["isError"] is True
    assert "Invalid bearer token format" in result["content"][0]["text"]
    mock_func.assert_not_called()


@pytest.mark.asyncio
async def test_require_auth_no_session_file_returns_guidance():
    """When the token is valid but no session file exists, return auth guidance."""
    mock_func = AsyncMock()
    decorated = require_auth(mock_func)

    config = MagicMock()
    config.disable_auth = False
    config.session_directory = "/tmp/sessions"

    mock_path = MagicMock()
    mock_path.exists.return_value = False

    with (
        patch("src.server_components.auth.cfg", return_value=config),
        patch(
            "src.server_components.auth._get_bearer_token_from_http",
            return_value="ok-token",
        ),
        patch(
            "src.server_components.auth.validate_session_token",
            return_value="validated-id",
        ),
        patch("src.server_components.auth.session_file_path", return_value=mock_path),
    ):
        result = await decorated()

    assert result["isError"] is True
    assert "not registered" in result["content"][0]["text"]
    mock_func.assert_not_called()


@pytest.mark.asyncio
async def test_require_auth_valid_token_calls_tool():
    """When token is valid and session file exists, call the tool function."""
    mock_func = AsyncMock(return_value={"result": "ok"})
    decorated = require_auth(mock_func)

    config = MagicMock()
    config.disable_auth = False
    config.session_directory = "/tmp/sessions"

    mock_path = MagicMock()
    mock_path.exists.return_value = True

    with (
        patch("src.server_components.auth.cfg", return_value=config),
        patch(
            "src.server_components.auth._get_bearer_token_from_http",
            return_value="ok-token",
        ),
        patch(
            "src.server_components.auth.validate_session_token",
            return_value="validated-id",
        ),
        patch("src.server_components.auth.session_file_path", return_value=mock_path),
        patch("src.server_components.auth.set_request_token") as mock_set_token,
    ):
        result = await decorated()

    assert result == {"result": "ok"}
    mock_func.assert_called_once()
    mock_set_token.assert_called_once_with("validated-id")


# ---------------------------------------------------------------------------
# _auth_guidance_response helper
# ---------------------------------------------------------------------------


def test_auth_guidance_response_default():
    """Default guidance message explains all auth options."""
    result = _auth_guidance_response()
    assert result["isError"] is True
    text = result["content"][0]["text"]
    assert "Authentication Required" in text
    assert "/setup" in text
    assert "Bearer" in text
    assert "QR" in text or "qr" in text


def test_auth_guidance_response_custom_message():
    """Custom message is used when provided."""
    result = _auth_guidance_response("Custom auth message")
    assert result["isError"] is True
    assert result["content"][0]["text"] == "Custom auth message"
