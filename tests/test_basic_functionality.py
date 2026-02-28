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
    assert len(tools) == 4
    tool_names = [t.name for t in tools]
    assert "search_messages_globally" in tool_names
    assert "get_messages" in tool_names
    assert "send_message" in tool_names
    assert "edit_message" in tool_names


@pytest.mark.asyncio
async def test_get_messages_search(client_session):
    """Test get_messages search functionality with mock data."""
    result = await client_session.call_tool(
        "get_messages", {"query": "Test", "chat_id": "me", "limit": 10}
    )

    assert result.data is not None
    assert isinstance(result.data, dict)
    assert "messages" in result.data
    assert len(result.data["messages"]) == 2  # Mock data has 2 messages
    assert "has_more" in result.data
    assert (
        result.data["has_more"] is False
    )  # Should be False since we have exactly 2 messages and limit=10


@pytest.mark.asyncio
async def test_get_messages_has_more(client_session):
    """Test has_more flag logic when there are more messages than limit."""
    result = await client_session.call_tool(
        "get_messages", {"query": "Test", "chat_id": "me", "limit": 1}
    )

    assert result.data is not None
    assert isinstance(result.data, dict)
    assert "messages" in result.data
    assert (
        len(result.data["messages"]) == 1
    )  # Should return only 1 message due to limit
    assert "has_more" in result.data
    assert (
        result.data["has_more"] is True
    )  # Should be True since there are 2 messages but limit=1


@pytest.mark.asyncio
async def test_send_message(client_session):
    """Test send message functionality."""
    result = await client_session.call_tool(
        "send_message",
        {"chat_id": "me", "message": "Test message from MCP"},
    )

    assert result.data is not None
    assert isinstance(result.data, dict)
    assert result.data["action"] == "sent"
    assert result.data["chat_id"] == "me"
    assert result.data["text"] == "Test message from MCP"


@pytest.mark.asyncio
async def test_get_messages_by_ids(client_session):
    """Test get_messages with message_ids mode."""
    result = await client_session.call_tool(
        "get_messages", {"chat_id": "me", "message_ids": [1, 2]}
    )

    assert result.data is not None
    assert isinstance(result.data, dict)
    assert "messages" in result.data
    assert "has_more" in result.data
    assert len(result.data["messages"]) == 2  # Should find both messages
    assert result.data["has_more"] is False  # Unified format includes has_more


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
            "search_messages_globally", {"query": "test", "limit": 5}
        )

        assert result.data is not None
        assert isinstance(result.data, dict)
        assert "messages" in result.data
