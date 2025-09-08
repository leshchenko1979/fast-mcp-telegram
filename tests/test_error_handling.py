#!/usr/bin/env python3
"""
Error handling tests for Telegram MCP Server.

Tests error handling decorators, parameter introspection, and error response formatting.
"""

import pytest
from fastmcp import FastMCP, Client

from src.server_components.errors import with_error_handling
from src.utils.error_handling import log_and_build_error


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
