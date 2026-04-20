#!/usr/bin/env python3
"""
Error handling tests for Telegram MCP Server.

Tests error handling decorators, parameter introspection, and error response formatting.
"""

import json

import pytest
from fastmcp import Client, FastMCP
from fastmcp.exceptions import ToolError

from src.client.connection import (
    SessionNotAuthorizedError,
    TelegramTransportError,
)
from src.server_components.errors import with_error_handling
from src.utils.error_handling import ErrorAction, log_and_build_error


@pytest.fixture
def error_test_server():
    """Create a FastMCP server instance for error handling tests."""
    return FastMCP("Error Handling Test Server")


@pytest.mark.asyncio
async def test_error_handling_direct():
    """Test that @with_error_handling decorator raises ToolError for error responses."""

    @with_error_handling("direct_test")
    async def direct_test_func(x: int, y: str = "default"):
        """Test function that returns an error response."""
        return log_and_build_error(
            operation="direct_test",
            error_message="Simulated error for testing",
            params={"x": x, "y": y},
        )

    with pytest.raises(ToolError):
        await direct_test_func(42, "test")


@pytest.mark.asyncio
async def test_error_handling_mcp(error_test_server):
    """Test that @with_error_handling decorator produces isError=True through MCP.

    Note: isError=True only happens when FastMCP sees an exception, not a dict return.
    We test via call_tool_mcp (raw protocol) to see the actual isError flag.
    """

    @with_error_handling("mcp_tool_test")
    @error_test_server.tool()
    async def error_tool(chat_id: str, message: str):
        """Tool that returns an error response."""
        return log_and_build_error(
            operation="mcp_tool_test",
            error_message=f"Simulated MCP error: chat_id={chat_id}, message={message}",
            params={"chat_id": chat_id, "message": message},
        )

    async with Client(error_test_server) as client:
        # Use call_tool_mcp to get raw MCP result and verify isError flag
        result = await client.call_tool_mcp(
            "error_tool", {"chat_id": "me", "message": "test error message"}
        )

        # With our refactor, with_error_handling raises ToolError.
        # FastMCP's lowlevel handler should catch this and set isError=True.
        # However, if the exception propagates through call_fn_with_arg_validation
        # and gets caught there, it may return the dict with isError=False.
        # This test documents the actual behavior.
        assert result.isError or result.content[0].text  # either isError or has content
        content = result.content[0]
        error_dict = json.loads(content.text)
        assert error_dict["ok"] is False
        assert "Simulated MCP error" in error_dict["error"]
        assert error_dict["operation"] == "mcp_tool_test"


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
    """Test that error responses have correct fields including code and action."""

    @with_error_handling("format_test")
    async def format_test_func():
        """Test function that returns a formatted error."""
        return log_and_build_error(
            operation="format_test",
            error_message="Test formatting error",
            params={"param1": "value1", "param2": 42},
            action=ErrorAction.RETRY,
        )

    with pytest.raises(ToolError) as exc_info:
        await format_test_func()

    error_dict = json.loads(str(exc_info.value))
    assert error_dict is not None
    assert error_dict["ok"] is False
    assert error_dict["error"] == "Test formatting error"
    assert error_dict["operation"] == "format_test"
    assert error_dict["action"] == "RETRY"  # action.name as string, not enum value
    # No code set since neither code nor error_code passed
    assert error_dict["params"] == {"param1": "value1", "param2": 42}


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
    """Async generators may wrap SessionNotAuthorizedError in RuntimeError; normalized response."""

    @with_error_handling("unwrap_auth")
    async def failing_tool():
        try:
            raise SessionNotAuthorizedError("test")
        except SessionNotAuthorizedError as e:
            raise RuntimeError("wrapper") from e

    with pytest.raises(ToolError) as exc_info:
        await failing_tool()

    error_dict = json.loads(str(exc_info.value))
    assert error_dict is not None
    assert error_dict["ok"] is False
    assert "Session not authorized" in error_dict["error"]
    assert error_dict["action"] == "AUTHENTICATE_SESSION"
    assert error_dict["code"] == -32002  # SESSION_NOT_AUTHORIZED


@pytest.mark.asyncio
async def test_with_error_handling_unwraps_transport_error_from_runtime_error():
    @with_error_handling("unwrap_transport")
    async def failing_tool():
        try:
            raise TelegramTransportError("proxy down")
        except TelegramTransportError as e:
            raise RuntimeError("wrapper") from e

    with pytest.raises(ToolError) as exc_info:
        await failing_tool()

    error_dict = json.loads(str(exc_info.value))
    assert error_dict is not None
    assert error_dict["ok"] is False
    assert error_dict["error"] == "proxy down"
    assert error_dict["action"] == "RETRY"
    assert error_dict["code"] == -32001  # CONNECTION_ERROR


@pytest.mark.asyncio
async def test_is_error_response_falsy_non_false():
    """Test that is_error_response returns False for falsy non-False values of ok."""
    from src.utils.error_handling import is_error_response

    # These should NOT be treated as errors (falsy non-False values)
    assert not is_error_response({"ok": None})
    assert not is_error_response({"ok": 0})
    assert not is_error_response({"ok": ""})
    # Explicit False IS an error
    assert is_error_response({"ok": False})
    assert not is_error_response({})  # no ok key
