#!/usr/bin/env python3
"""
Error handling tests for Telegram MCP Server.

Tests error handling decorators, parameter introspection, and error response formatting.
"""

import pytest
from fastmcp import Client, FastMCP

from src.client.connection import (
    SessionNotAuthorizedError,
    TelegramTransportError,
)
from src.server_components.errors import with_error_handling
from src.utils.error_handling import handle_telegram_errors, log_and_build_error


@pytest.fixture
def error_test_server():
    """Create a FastMCP server instance for error handling tests."""
    return FastMCP("Error Handling Test Server")


@pytest.mark.asyncio
async def test_error_handling_direct():
    """Test that @with_error_handling decorator works correctly (direct function test)."""

    @with_error_handling("direct_test")
    async def direct_test_func(x: int, y: str = "default"):
        """Test function that returns an error response."""
        return log_and_build_error(
            operation="direct_test",
            error_message="Simulated error for testing",
            params={"x": x, "y": y},
        )

    result = await direct_test_func(42, "test")

    assert isinstance(result, dict)
    assert "error" in result
    assert not result.get("ok", True)
    assert result["error"] == "Simulated error for testing"
    assert result["operation"] == "direct_test"
    assert result["params"] == {"x": 42, "y": "test"}


@pytest.mark.asyncio
async def test_error_handling_mcp(error_test_server):
    """Test that @with_error_handling decorator works with MCP tools."""

    @with_error_handling("mcp_tool_test")
    @error_test_server.tool()
    async def error_tool(chat_id: str, message: str):
        """Tool that returns an error response instead of raising exception."""
        return log_and_build_error(
            operation="mcp_tool_test",
            error_message=f"Simulated MCP error: chat_id={chat_id}, message={message}",
            params={"chat_id": chat_id, "message": message},
        )

    async with Client(error_test_server) as client:
        result = await client.call_tool(
            "error_tool", {"chat_id": "me", "message": "test error message"}
        )

        # Check if result is a proper error response
        assert hasattr(result, "data")
        assert isinstance(result.data, dict)

        data = result.data
        assert "error" in data
        assert not data.get("ok", True)
        assert "Simulated MCP error" in data["error"]
        assert data["operation"] == "mcp_tool_test"


@pytest.mark.asyncio
async def test_introspection():
    """Test that introspection captures parameters correctly."""

    # Test the decorator directly (not through MCP)
    @with_error_handling("test_operation")
    async def test_func(chat_id: str, message: str, limit: int = 10):
        """Test function for introspection."""
        return {"chat_id": chat_id, "message": message, "limit": limit}

    # Call the decorated function
    result = await test_func("me", "test message", limit=5)

    assert isinstance(result, dict)
    assert result["chat_id"] == "me"
    assert result["message"] == "test message"
    assert result["limit"] == 5


@pytest.mark.asyncio
async def test_error_response_formatting():
    """Test that error responses are properly formatted."""

    @with_error_handling("format_test")
    async def format_test_func():
        """Test function that returns a formatted error."""
        return log_and_build_error(
            operation="format_test",
            error_message="Test formatting error",
            params={"param1": "value1", "param2": 42},
            action="retry",
        )

    result = await format_test_func()

    assert isinstance(result, dict)
    assert result["ok"] is False
    assert result["error"] == "Test formatting error"
    assert result["operation"] == "format_test"
    assert result["action"] == "retry"
    assert result["params"] == {"param1": "value1", "param2": 42}


@pytest.mark.asyncio
async def test_introspection_with_complex_params():
    """Test parameter introspection with complex parameter types."""

    @with_error_handling("complex_test")
    async def complex_test_func(
        chat_id: str, message_ids: list[int], options: dict[str, str], flag: bool = True
    ):
        """Test function with complex parameter types."""
        return {
            "chat_id": chat_id,
            "message_ids": message_ids,
            "options": options,
            "flag": flag,
        }

    result = await complex_test_func(
        "test_chat", [1, 2, 3], {"key": "value"}, flag=False
    )

    assert isinstance(result, dict)
    assert result["chat_id"] == "test_chat"
    assert result["message_ids"] == [1, 2, 3]
    assert result["options"] == {"key": "value"}
    assert result["flag"] is False


@pytest.mark.asyncio
async def test_with_error_handling_unwraps_session_error_from_runtime_error():
    """Async generators may wrap SessionNotAuthorizedError in RuntimeError; normalize response."""

    @with_error_handling("unwrap_auth")
    async def failing_tool():
        try:
            raise SessionNotAuthorizedError("test")
        except SessionNotAuthorizedError as e:
            raise RuntimeError("wrapper") from e

    result = await failing_tool()
    assert result["ok"] is False
    assert "Session not authorized" in result["error"]
    assert result["action"] == "authenticate_session"


@pytest.mark.asyncio
async def test_with_error_handling_unwraps_transport_error_from_runtime_error():
    @with_error_handling("unwrap_transport")
    async def failing_tool():
        try:
            raise TelegramTransportError("proxy down")
        except TelegramTransportError as e:
            raise RuntimeError("wrapper") from e

    result = await failing_tool()
    assert result["ok"] is False
    assert result["error"] == "proxy down"
    assert result["action"] == "retry"


@pytest.mark.asyncio
async def test_handle_telegram_errors_unwraps_session_from_runtime_error():
    @handle_telegram_errors(operation="ht_unwrap_auth")
    async def failing_impl():
        try:
            raise SessionNotAuthorizedError("inner")
        except SessionNotAuthorizedError as e:
            raise RuntimeError("wrapper") from e

    result = await failing_impl()
    assert result["ok"] is False
    assert "Session not authorized" in result["error"]
    assert result["action"] == "authenticate_session"


@pytest.mark.asyncio
async def test_handle_telegram_errors_unwraps_transport_from_runtime_error():
    """Same __cause__ unwrap as with_error_handling, for @handle_telegram_errors."""

    @handle_telegram_errors(operation="ht_unwrap_transport")
    async def failing_impl():
        try:
            raise TelegramTransportError("mtproto blocked")
        except TelegramTransportError as e:
            raise RuntimeError("wrapper") from e

    result = await failing_impl()
    assert result["ok"] is False
    assert result["error"] == "mtproto blocked"
    assert result["action"] == "retry"
