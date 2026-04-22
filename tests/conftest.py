#!/usr/bin/env python3
"""
Pytest configuration and shared fixtures for Telegram MCP Server tests.

This module provides common fixtures and configuration used across all test files.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from fastmcp import Client, FastMCP
from fastmcp.server.auth import AccessToken
from fastmcp.server.auth.providers.jwt import StaticTokenVerifier

from src.config.server_config import ServerConfig, ServerMode, set_config


def make_access_token(token: str) -> AccessToken:
    """Create AccessToken for tests (used when mocking get_access_token)."""
    return AccessToken(token=token, client_id="test", scopes=[])


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

    def is_connected(self):
        # Telethon's client.is_connected() is synchronous; keep mock signature aligned.
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

    conn._get_client_by_token = AsyncMock(return_value=mock_client)

    # Register simplified mock versions of tools for testing
    @mcp.tool()
    async def search_messages_globally(
        query: str, limit: int = 50, chat_type: str | None = None
    ):
        """Search across all Telegram chats."""
        all_messages = []
        for chat_messages in mock_client.messages.values():
            all_messages.extend(chat_messages)

        if query:
            all_messages = [
                msg for msg in all_messages if query.lower() in msg["text"].lower()
            ]
        window = all_messages[:limit]
        has_more = len(all_messages) > len(window)
        return {"messages": window, "has_more": has_more}

    @mcp.tool()
    async def get_messages(
        chat_id: str,
        query: str | None = None,
        message_ids: list[int] | None = None,
        reply_to_id: int | None = None,
        limit: int = 50,
    ):
        """Unified message retrieval - search, browse, read by IDs, or get replies."""
        messages = mock_client.messages.get(chat_id, [])

        # Mode: Read by IDs
        if message_ids:
            found_messages = [msg for msg in messages if msg["id"] in message_ids]
            return {"messages": found_messages, "has_more": False}

        # Mode: Get replies
        if reply_to_id:
            # Mock replies: messages with matching reply_to field
            reply_messages = [
                msg for msg in messages if msg.get("reply_to_msg_id") == reply_to_id
            ]
            if query:
                reply_messages = [
                    msg
                    for msg in reply_messages
                    if query.lower() in msg["text"].lower()
                ]
            window = reply_messages[:limit]
            has_more = len(reply_messages) > len(window)
            return {
                "messages": window,
                "has_more": has_more,
                "reply_to_id": reply_to_id,
            }

        # Mode: Search or browse
        if query:
            messages = [msg for msg in messages if query.lower() in msg["text"].lower()]
        window = messages[:limit]
        has_more = len(messages) > len(window)
        return {"messages": window, "has_more": has_more}

    @mcp.tool()
    async def send_message(chat_id: str, message: str, reply_to_id: int | None = None):
        """Send new message in Telegram chat."""
        return {"action": "sent", "chat_id": chat_id, "text": message}

    @mcp.tool()
    async def edit_message(chat_id: str, message_id: int, message: str):
        """Edit existing message in Telegram chat."""
        return {"action": "edited", "message_id": message_id, "text": message}

    return mcp


@pytest_asyncio.fixture
async def client_session(test_server):
    """Pytest fixture providing an MCP client session."""
    async with Client(test_server) as client:
        yield client


# Server Configuration Fixtures
@pytest.fixture
def http_auth_config():
    """Fixture providing HTTP auth mode server configuration."""
    config = ServerConfig()
    config.server_mode = ServerMode.HTTP_AUTH
    set_config(config)
    return config


@pytest.fixture
def http_no_auth_config():
    """Fixture providing HTTP no-auth mode server configuration."""
    config = ServerConfig()
    config.server_mode = ServerMode.HTTP_NO_AUTH
    set_config(config)
    return config


@pytest.fixture
def stdio_config():
    """Fixture providing STDIO mode server configuration."""
    config = ServerConfig()
    config.server_mode = ServerMode.STDIO
    set_config(config)
    return config


# Common test data and fixtures
@pytest.fixture
def test_token():
    """Common test token used across tests."""
    return "TestToken123456789"


@pytest.fixture
def valid_token():
    """Valid token for testing."""
    return "ValidTestToken123"


@pytest.fixture
def extraction_token():
    """Token used for extraction tests."""
    return "ExtractionTestToken123"


@pytest.fixture
def context_token():
    """Token used for context testing."""
    return "ContextTestToken123"


@pytest.fixture
def auth_headers(test_token):
    """Authorization headers with test token."""
    return {"authorization": f"Bearer {test_token}"}


@pytest.fixture
def empty_headers():
    """Empty HTTP headers."""
    return {}


@pytest.fixture
def invalid_auth_headers():
    """Invalid authorization headers (missing Bearer)."""
    return {"authorization": "Basic InvalidToken123"}


@pytest.fixture
def malformed_auth_headers():
    """Malformed authorization headers (missing space)."""
    return {"authorization": "BearerInvalidToken123"}


@pytest.fixture
def async_success_func():
    """Common async function that returns 'success'."""

    async def async_mock_func():
        return "success"

    return async_mock_func


@pytest.fixture
def async_success_func_decorated(async_success_func):
    """Async success function decorated with with_auth_context."""
    from src.server_components.auth import with_auth_context

    return with_auth_context(async_success_func)


# Token verification helpers
@pytest.fixture
def token_verifier():
    """Helper fixture for token verification."""

    def verify_token(expected_token=None, should_be_none=False):
        """Verify current token state."""
        from src.client.connection import _current_token

        current = _current_token.get()

        if should_be_none:
            assert current is None, f"Expected None, got {current}"
            return True

        if expected_token is not None:
            assert current == expected_token, (
                f"Expected {expected_token}, got {current}"
            )
            return True

        return current

    return verify_token


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


# ============== Shared Mock Entity Classes ==============
# Used across contacts tests for mocking Telegram entities (User, Chat, Channel, Dialog)


def make_user(id, first_name="", last_name="", username="", phone="", bot=False):
    """Create a mock entity that reports as class 'User'."""
    attrs = {
        "id": id,
        "first_name": first_name,
        "last_name": last_name,
        "username": username,
        "phone": phone,
        "bot": bot,
        "title": None,
    }
    return type("User", (), attrs)()


def make_chat(id, title="", username=""):
    """Create a mock entity that reports as class 'Chat'."""
    attrs = {
        "id": id,
        "title": title,
        "first_name": None,
        "last_name": None,
        "username": username,
        "phone": None,
    }
    return type("Chat", (), attrs)()


def make_channel(id, title="", username="", megagroup=False):
    """Create a mock entity that reports as class 'Channel'."""
    attrs = {
        "id": id,
        "title": title,
        "username": username,
        "megagroup": megagroup,
        "first_name": None,
        "last_name": None,
        "phone": None,
    }
    return type("Channel", (), attrs)()


class MockDialog:
    """Mock Dialog object for testing."""

    def __init__(self, entity, date=None, folder_id=None):
        self.entity = entity
        self.date = date
        self.folder_id = folder_id


# Aliases for backwards compatibility
MockUser = make_user
MockChat = make_chat
MockChannel = make_channel


# ============== Forum Channel Fixtures ==============


def make_forum_channel(chat_id, title, forum=True):
    """Mock Channel with forum/broadcast/megagroup attrs.

    Args:
        chat_id: The channel's ID
        title: The channel's title
        forum: True for forum channels, False for regular channels
    """
    attrs = {
        "id": chat_id,
        "title": title,
        "forum": forum,
        "broadcast": True,
        "megagroup": False,
        "first_name": None,
        "last_name": None,
        "username": None,
        "phone": None,
    }
    return type("Channel", (), attrs)()


# ============== Mock Message Fixtures ==============


def make_mock_message(
    id=1,
    text="",
    date=None,
    peer_id=None,
    media=None,
    reply_to_msg_id=None,
    forum_topic=False,
    reply_to=None,
    **kwargs,
):
    """Create a mock Message object.

    Args:
        id: Message ID
        text: Message text
        date: Message date (datetime or string)
        peer_id: Peer object (PeerUser, PeerChat, etc.)
        media: Message media (None for no media)
        reply_to_msg_id: ID of message being replied to
        forum_topic: Whether this is a forum topic message
        reply_to: Reply-to object with reply_to_top_id and reply_to_msg_id
        **kwargs: Additional attributes to set
    """
    msg = MagicMock()
    msg.id = id
    msg.text = text
    msg.message = text  # Some code uses .message instead of .text
    msg.date = date
    msg.media = media
    msg.reply_to_msg_id = reply_to_msg_id
    msg.forum_topic = forum_topic
    msg.peer_id = peer_id
    msg.reply_to = reply_to
    for k, v in kwargs.items():
        setattr(msg, k, v)
    return msg


def make_mock_reply_to(forum_topic, reply_to_top_id=None, reply_to_msg_id=None):
    """Mock reply_to object for forum topic tests."""
    return MagicMock(
        reply_to_top_id=reply_to_top_id,
        forum_topic=forum_topic,
        reply_to_msg_id=reply_to_msg_id,
    )


def make_topic_message(msg_id, text, reply_to_msg_id, reply_to_top_id, forum_topic):
    """Full message object with reply_to for forum topic tests.

    Args:
        msg_id: Message ID
        text: Message text
        reply_to_msg_id: Top-level reply message ID
        reply_to_top_id: Forum topic ID being replied to
        forum_topic: Whether this is in a forum topic
    """
    from datetime import datetime

    return make_mock_message(
        id=msg_id,
        text=text,
        date=datetime.now(),
        reply_to_msg_id=reply_to_msg_id,
        forum_topic=forum_topic,
        reply_to=make_mock_reply_to(forum_topic, reply_to_top_id, reply_to_msg_id),
    )


# ============== Folder Fixtures ==============


def make_folder(id, title_text):
    """Mock DialogFilter/Folder for dialog filter tests.

    Args:
        id: Folder ID
        title_text: Folder title text
    """
    folder = MagicMock()
    folder.id = id
    folder.title = type("obj", (object,), {"text": title_text})()
    return folder


# ============== Request Fixtures ==============


def make_mock_request(path, scheme="https", netloc="example.com", query=""):
    """Mock Starlette Request for middleware tests.

    Args:
        path: Request path
        scheme: URL scheme (default https)
        netloc: URL netloc (default example.com)
        query: URL query string (default empty)
    """
    from starlette.requests import Request

    request = MagicMock(spec=Request)
    request.scope = {"path": path, "headers": []}
    request.url = MagicMock()
    request.url.path = path
    request.url.scheme = scheme
    request.url.netloc = netloc
    request.url.query = query
    # Mock headers._list for injection
    request.headers.__dict__ = {"_list": []}
    return request


# ============== Cache Management Fixtures ==============


@pytest.fixture(autouse=True)
def clear_entity_cache():
    """Clear entity type and folder caches before each test to avoid cache pollution.

    This fixture runs automatically for every test via autouse=True.
    """
    from src.utils.entity import (
        _ENTITY_DICT_CACHE,
        _ENTITY_TYPE_CACHE,
        _FOLDER_LIST_CACHE,
    )

    _ENTITY_TYPE_CACHE.clear()
    _ENTITY_DICT_CACHE.clear()
    _FOLDER_LIST_CACHE.clear()
    yield
    _ENTITY_TYPE_CACHE.clear()
    _ENTITY_DICT_CACHE.clear()
    _FOLDER_LIST_CACHE.clear()
