#!/usr/bin/env python3
"""
Decorator chain integration tests for Telegram MCP Server.

Tests that @mcp.tool, @with_auth_context, and @with_error_handling decorators
work together properly in the correct order.
"""

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from src.server_components.auth import with_auth_context
from src.server_components.errors import with_error_handling
from tests.conftest import create_auth_server


@pytest.mark.asyncio
async def test_decorator_chain_integration():
    """Test that all decorators work together: @mcp.tool + @with_auth_context + @with_error_handling"""

    # Import the actual decorators from the server module
    from src.client.connection import set_request_token

    # Create a server that uses the actual decorator chain
    mcp = create_auth_server("Decorator Chain Test Server")

    # Use the actual decorator chain order as in the real server
    @with_auth_context
    @with_error_handling("test_decorator_chain")
    @mcp.tool()
    async def test_decorator_tool(chat_id: str, message: str):
        """Test tool that uses the full decorator chain."""
        # This should succeed and return data
        return {"success": True, "chat_id": chat_id, "message": message}

    # Test 2: Tool works with authentication
    async with Client(mcp) as client:
        # Set authentication token
        set_request_token("test-token")

        # Call the tool
        result = await client.call_tool(
            "test_decorator_tool", {"chat_id": "test_chat", "message": "test message"}
        )

        # Verify the response
        assert result.data is not None
        assert isinstance(result.data, dict)
        assert result.data["success"] is True
        assert result.data["chat_id"] == "test_chat"
        assert result.data["message"] == "test message"


@pytest.mark.asyncio
async def test_decorator_chain_error_handling():
    """Test that error handling works through the full decorator chain."""

    from src.client.connection import set_request_token

    mcp = create_auth_server("Decorator Chain Error Test Server")

    @with_auth_context
    @with_error_handling("test_error_chain")
    @mcp.tool()
    async def failing_decorator_tool(chat_id: str):
        """Test tool that fails to test error handling in decorator chain."""
        # Simulate an error that should be caught by @with_error_handling
        raise ValueError(f"Test error in decorator chain for chat: {chat_id}")

    async with Client(mcp) as client:
        # Set authentication token
        set_request_token("test-token")

        # Call the tool that should fail - MCP client raises ToolError by default
        with pytest.raises(ToolError) as exc_info:
            await client.call_tool("failing_decorator_tool", {"chat_id": "error_test"})

        # Verify that our error message is in the ToolError
        error_message = str(exc_info.value)
        assert "Test error in decorator chain" in error_message
        assert "error_test" in error_message

        # Now test with call_tool_mcp to get the raw MCP result
        result = await client.call_tool_mcp(
            "failing_decorator_tool", {"chat_id": "error_test"}
        )

        # The MCP result should contain the error
        assert result.isError
        assert len(result.content) > 0

        # The content should be our formatted error response
        content = result.content[0]
        assert hasattr(content, "text")
        assert "Test error in decorator chain" in content.text


@pytest.mark.asyncio
async def test_authentication_in_decorator_chain():
    """Test that authentication works properly in the decorator chain."""

    from src.client.connection import set_request_token

    mcp = create_auth_server("Auth Chain Test Server")

    @with_auth_context
    @with_error_handling("test_auth_chain")
    @mcp.tool()
    async def auth_test_tool(value: int):
        """Test tool to verify authentication context."""
        return {"authenticated": True, "value": value}

    async with Client(mcp) as client:
        # Test 1: With authentication token
        set_request_token("test-token")

        result = await client.call_tool("auth_test_tool", {"value": 42})
        assert result.data is not None
        assert result.data["authenticated"] is True
        assert result.data["value"] == 42

        # Test 2: Without authentication token (should still work due to fallback)
        set_request_token(None)

        result = await client.call_tool("auth_test_tool", {"value": 100})
        assert result.data is not None
        assert result.data["authenticated"] is True
        assert result.data["value"] == 100
