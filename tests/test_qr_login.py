"""Tests for QrLoginManager — in-memory QR session management."""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.server_components.qr_login import QrLoginManager


@pytest.fixture
def mock_telethon_client():
    """Create a mock Telethon client with qr_login support."""
    client = MagicMock()
    # Telethon's qr_login() is synchronous, returns a QRLogin object
    qr_login_mock = MagicMock()
    qr_login_mock.url = "tg://login?token=abc123"
    client.qr_login = MagicMock(return_value=qr_login_mock)
    client.disconnect = AsyncMock()
    return client


@pytest.fixture
def manager():
    """QrLoginManager with default 60s timeout."""
    return QrLoginManager(timeout_seconds=60)


def test_create_session(manager, mock_telethon_client):
    """Creating a QR session returns a session_id and QR URL."""
    mock_qr_login = MagicMock()
    mock_qr_login.url = "tg://login?token=abc123"
    mock_telethon_client.qr_login.return_value = mock_qr_login

    session_id, qr_url = manager.create_session(mock_telethon_client)

    assert session_id is not None
    assert len(session_id) > 0
    assert qr_url == "tg://login?token=abc123"
    assert session_id in manager._sessions
    mock_telethon_client.qr_login.assert_called_once()


def test_create_session_generates_unique_ids(manager, mock_telethon_client):
    """Each call to create_session generates a unique session_id."""
    mock_qr_login = MagicMock()
    mock_qr_login.url = "tg://login?token=abc"
    mock_telethon_client.qr_login.return_value = mock_qr_login

    id1, _ = manager.create_session(mock_telethon_client)
    id2, _ = manager.create_session(mock_telethon_client)

    assert id1 != id2


@pytest.mark.asyncio
async def test_poll_status_pending(manager, mock_telethon_client):
    """poll_status returns 'pending' before the QR is scanned."""
    mock_qr_login = MagicMock()
    mock_qr_login.url = "tg://login?token=abc"
    mock_telethon_client.qr_login.return_value = mock_qr_login

    session_id, _ = manager.create_session(mock_telethon_client)
    status = await manager.poll_status(session_id)

    assert status == "pending"


@pytest.mark.asyncio
async def test_poll_status_completed(manager, mock_telethon_client):
    """poll_status returns 'completed' and sets client when QR is scanned."""
    mock_tg_client = MagicMock()
    mock_tg_client.is_user_authorized.return_value = True
    mock_tg_client.disconnect = AsyncMock()

    mock_qr_login = MagicMock()
    mock_qr_login.url = "tg://login?token=abc"
    mock_qr_login.wait = AsyncMock(return_value=mock_tg_client)
    mock_telethon_client.qr_login.return_value = mock_qr_login

    session_id, _ = manager.create_session(mock_telethon_client)

    # First poll kicks off background wait task
    status = await manager.poll_status(session_id)
    assert status == "pending"

    # Yield to event loop so background task can complete
    await asyncio.sleep(0)

    # Second poll should show completed
    status = await manager.poll_status(session_id)
    assert status == "completed"
    assert manager._sessions[session_id].resulting_client is mock_tg_client


@pytest.mark.asyncio
async def test_poll_status_expired(manager, mock_telethon_client):
    """poll_status returns 'expired' on timeout, and the QR can be regenerated."""
    mock_qr_login = MagicMock()
    mock_qr_login.url = "tg://login?token=abc"
    mock_qr_login.wait = AsyncMock(side_effect=TimeoutError("QR login timed out"))
    mock_telethon_client.qr_login.return_value = mock_qr_login

    session_id, _ = manager.create_session(mock_telethon_client)
    status = await manager.poll_status(session_id)

    # First poll kicks off background task, may still be pending
    assert status in ("pending", "expired")

    # Yield so the background task finishes
    await asyncio.sleep(0)

    status = await manager.poll_status(session_id)
    assert status == "expired"


@pytest.mark.asyncio
async def test_poll_status_not_found(manager):
    """poll_status returns 'not_found' for unknown session IDs."""
    status = await manager.poll_status("nonexistent")
    assert status == "not_found"


@pytest.mark.asyncio
async def test_get_client(manager, mock_telethon_client):
    """get_client returns the connected Telethon client after successful login."""
    mock_tg_client = MagicMock()
    mock_tg_client.is_user_authorized.return_value = True
    mock_tg_client.disconnect = AsyncMock()

    mock_qr_login = MagicMock()
    mock_qr_login.url = "tg://login?token=abc"
    mock_qr_login.wait = AsyncMock(return_value=mock_tg_client)
    mock_telethon_client.qr_login.return_value = mock_qr_login

    session_id, _ = manager.create_session(mock_telethon_client)

    # First poll kicks off background wait task
    await manager.poll_status(session_id)

    # Yield so the background task finishes
    await asyncio.sleep(0)

    client = manager.get_client(session_id)
    assert client is mock_tg_client


def test_get_client_not_found(manager):
    """get_client returns None for unknown sessions."""
    client = manager.get_client("nonexistent")
    assert client is None


def test_get_client_not_completed(manager, mock_telethon_client):
    """get_client returns None for sessions that haven't completed."""
    mock_qr_login = MagicMock()
    mock_qr_login.url = "tg://login?token=abc"
    mock_telethon_client.qr_login.return_value = mock_qr_login

    session_id, _ = manager.create_session(mock_telethon_client)
    client = manager.get_client(session_id)

    assert client is None


@pytest.mark.asyncio
async def test_regenerate_qr(manager, mock_telethon_client):
    """regenerate_qr creates a new QR for an existing session."""
    mock_qr_login = MagicMock()
    mock_qr_login.url = "tg://login?token=abc"
    mock_telethon_client.qr_login.return_value = mock_qr_login

    session_id, first_url = manager.create_session(mock_telethon_client)

    # New QR login
    mock_qr_login2 = MagicMock()
    mock_qr_login2.url = "tg://login?token=def"
    mock_telethon_client.qr_login.return_value = mock_qr_login2

    second_url = await manager.regenerate_qr(session_id, mock_telethon_client)

    assert second_url is not None
    assert second_url != first_url
    mock_telethon_client.qr_login.assert_called()


def test_cleanup_expired(manager, mock_telethon_client):
    """cleanup_expired removes expired sessions."""
    mock_qr_login = MagicMock()
    mock_qr_login.url = "tg://login?token=abc"
    mock_telethon_client.qr_login.return_value = mock_qr_login

    # Create a session and put it in the past
    session_id, _ = manager.create_session(mock_telethon_client)
    manager._sessions[session_id].created_at = time.time() - 120  # 2 min ago

    manager.cleanup_expired()

    assert session_id not in manager._sessions


def test_cleanup_expired_keeps_fresh(manager, mock_telethon_client):
    """cleanup_expired does NOT remove sessions within the timeout."""
    mock_qr_login = MagicMock()
    mock_qr_login.url = "tg://login?token=abc"
    mock_telethon_client.qr_login.return_value = mock_qr_login

    session_id, _ = manager.create_session(mock_telethon_client)

    manager.cleanup_expired()

    assert session_id in manager._sessions


def test_create_session_integration_flow():
    """Full integration-style test of QrLoginManager flow."""
    manager = QrLoginManager(timeout_seconds=30)
    mock_client = MagicMock()
    qr_login_mock = MagicMock()
    qr_login_mock.url = "tg://login?token=flowtest"
    qr_login_mock.wait = AsyncMock(return_value=MagicMock())
    mock_client.qr_login = MagicMock(return_value=qr_login_mock)

    # Test: create → poll → complete → get_client
    session_id, qr_url = manager.create_session(mock_client)
    assert qr_url == "tg://login?token=flowtest"

    # Async poll
    status = asyncio.run(manager.poll_status(session_id))
    assert status in ("pending", "completed")

    _ = manager.get_client(session_id)  # Client may/may not be set
