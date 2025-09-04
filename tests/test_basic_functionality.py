#!/usr/bin/env python3
"""
Basic functionality tests for Telegram MCP Server.

Tests basic MCP server operations, tool registration, and client interactions.
"""

import pytest
from fastmcp import Client


@pytest.mark.asyncio
async def test_basic_functionality(client_session):
    """Test basic MCP server functionality without authentication."""
    # Test ping
    await client_session.ping()

    # Test tool listing
    tools = await client_session.list_tools()
    assert len(tools) == 3
    tool_names = [t.name for t in tools]
    assert "search_messages" in tool_names
    assert "send_or_edit_message" in tool_names
    assert "read_messages" in tool_names


@pytest.mark.asyncio
async def test_search_messages(client_session):
    """Test search messages functionality with mock data."""
    result = await client_session.call_tool(
        "search_messages", {"query": "Test", "chat_id": "me", "limit": 10}
    )

    assert result.data is not None
    assert isinstance(result.data, dict)
    assert "messages" in result.data
    assert len(result.data["messages"]) == 2  # Mock data has 2 messages


@pytest.mark.asyncio
async def test_send_message(client_session):
    """Test send message functionality."""
    result = await client_session.call_tool(
        "send_or_edit_message",
        {"chat_id": "me", "message": "Test message from MCP"},
    )

    assert result.data is not None
    assert isinstance(result.data, dict)
    assert result.data["action"] == "sent"
    assert result.data["chat_id"] == "me"
    assert result.data["text"] == "Test message from MCP"


@pytest.mark.asyncio
async def test_read_messages(client_session):
    """Test read messages functionality."""
    result = await client_session.call_tool(
        "read_messages", {"chat_id": "me", "message_ids": [1, 2]}
    )

    assert result.data is not None
    assert isinstance(result.data, dict)
    assert "messages" in result.data
    assert len(result.data["messages"]) == 2  # Should find both messages


@pytest.mark.asyncio
async def test_with_bearer_token(test_server):
    """Test with proper Bearer token authentication."""
    # For FastMCP in-memory testing, we need to set up authentication differently
    # The StaticTokenVerifier should handle this automatically
    async with Client(test_server) as client:
        # Set the request token in the context before making calls
        from src.client.connection import set_request_token

        set_request_token("test-token")

        result = await client.call_tool(
            "search_messages", {"query": "test", "limit": 5}
        )

        assert result.data is not None
        assert isinstance(result.data, dict)
        assert "messages" in result.data
