#!/usr/bin/env python3
"""
Pytest configuration and shared fixtures for Telegram MCP Server tests.

This module provides common fixtures and configuration used across all test files.
"""

import asyncio
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock

from fastmcp import FastMCP, Client
from fastmcp.server.auth.providers.jwt import StaticTokenVerifier

from src.server_components.errors import with_error_handling


class MockTelegramClient:
    """Mock Telegram client for testing without real API calls."""

    def __init__(self):
        self.is_connected_value = True
        self.messages = {
            "me": [
                {"id": 1, "text": "Test message 1", "date": "2024-01-01"},
                {"id": 2, "text": "Test message 2", "date": "2024-01-02"},
            ],
            "@test_channel": [
                {"id": 10, "text": "Channel message 1", "date": "2024-01-01"},
                {"id": 11, "text": "Channel message 2", "date": "2024-01-02"},
            ],
        }

    async def is_connected(self):
        return self.is_connected_value

    async def iter_messages(self, entity, limit=50, search=None):
        """Mock message iteration."""
        chat_id = (
            getattr(entity, "username", str(entity))
            if hasattr(entity, "username")
            else str(entity)
        )

        messages = self.messages.get(chat_id, [])
        if search:
            messages = [
                msg for msg in messages if search.lower() in msg["text"].lower()
            ]

        for msg in messages[:limit]:
            mock_msg = MagicMock()
            mock_msg.id = msg["id"]
            mock_msg.text = msg["text"]
            mock_msg.date = msg["date"]
            yield mock_msg

    async def send_message(self, chat_id, text, **kwargs):
        """Mock message sending."""
        return MagicMock(id=100, text=text)

    async def edit_message(self, chat_id, message_id, text, **kwargs):
        """Mock message editing."""
        return MagicMock(id=message_id, text=text)


@pytest.fixture
def mock_client():
    """Pytest fixture providing a mock Telegram client."""
    return MockTelegramClient()


@pytest.fixture
def test_server(mock_client):
    """Create a FastMCP server instance for testing with mock authentication."""

    # Use static token verification for testing (no real auth required)
    verifier = StaticTokenVerifier(
        tokens={
            "test-token": {
                "client_id": "test-user",
                "scopes": ["read", "write", "search"],
            }
        },
        required_scopes=["read"],
    )

    # Create server with mock auth
    mcp = FastMCP("Telegram MCP Test Server", auth=verifier)

    # Override the client in the connection module for testing
    import src.client.connection as conn

    conn._get_client = AsyncMock(return_value=mock_client)

    # Register the actual tool functions (we can't import them directly due to decorators)
    # Instead, we'll create simplified versions for testing
    @mcp.tool()
    async def search_messages(query: str, chat_id: str | None = None, limit: int = 50):
        """Search Telegram messages with advanced filtering."""
        return {"messages": mock_client.messages.get(chat_id or "me", [])[:limit]}

    @mcp.tool()
    async def send_or_edit_message(
        chat_id: str, message: str, message_id: int | None = None
    ):
        """Send new message or edit existing message in Telegram chat."""
        if message_id:
            return {"action": "edited", "message_id": message_id, "text": message}
        else:
            return {"action": "sent", "chat_id": chat_id, "text": message}

    @mcp.tool()
    async def read_messages(chat_id: str, message_ids: list[int]):
        """Read specific messages by their IDs from a Telegram chat."""
        messages = mock_client.messages.get(chat_id, [])
        found_messages = [msg for msg in messages if msg["id"] in message_ids]
        return {"messages": found_messages}

    return mcp


@pytest_asyncio.fixture
async def client_session(test_server):
    """Pytest fixture providing an MCP client session."""
    async with Client(test_server) as client:
        yield client


# Pytest configuration
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "asyncio: marks tests as async (using pytest-asyncio)"
    )
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "unit: marks tests as unit tests")


# Shared utilities for tests
def create_tool_server(name: str = "Test Server"):
    """Helper function to create a basic tool server for testing."""
    return FastMCP(name)


def create_auth_server(name: str = "Auth Test Server"):
    """Helper function to create a server with authentication."""
    verifier = StaticTokenVerifier(
        tokens={"test-token": {"client_id": "test-user", "scopes": ["read", "write"]}},
        required_scopes=["read"],
    )
    return FastMCP(name, auth=verifier)
