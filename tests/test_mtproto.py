#!/usr/bin/env python3
"""
Tests for MTProto tool: hash sanitization and RPC error normalization.
"""

from unittest.mock import AsyncMock, patch

import pytest
from telethon.errors import InviteHashExpiredError, UserAlreadyParticipantError

from src.tools.mtproto import (
    _normalize_rpc_error_code,
    _resolve_params,
    _sanitize_mtproto_params,
    invoke_mtproto_impl,
)
from src.utils.entity import is_ambiguous_peer_scalar


class TestSanitizeHash:
    """Tests for _sanitize_mtproto_params hash handling."""

    def test_sanitize_hash_preserves_string(self):
        """String hash is kept with whitespace stripped."""
        result = _sanitize_mtproto_params({"hash": "  ABC123xyz  "})
        assert result["hash"] == "ABC123xyz"

    def test_sanitize_hash_preserves_string_no_whitespace(self):
        """String hash without whitespace is preserved."""
        result = _sanitize_mtproto_params({"hash": "hlQ3QhNi6q05ZDIx"})
        assert result["hash"] == "hlQ3QhNi6q05ZDIx"

    def test_sanitize_hash_removes_empty_string(self):
        """Empty or whitespace-only string hash is removed."""
        result = _sanitize_mtproto_params({"hash": ""})
        assert "hash" not in result

        result = _sanitize_mtproto_params({"hash": "   \t  "})
        assert "hash" not in result

    def test_sanitize_hash_preserves_valid_int(self):
        """Integer hash in valid range is kept."""
        result = _sanitize_mtproto_params({"hash": 0})
        assert result["hash"] == 0

        result = _sanitize_mtproto_params({"hash": 0xFFFFFFFF})
        assert result["hash"] == 0xFFFFFFFF

        result = _sanitize_mtproto_params({"hash": 12345})
        assert result["hash"] == 12345

    def test_sanitize_hash_removes_out_of_bounds_int(self):
        """Integer hash out of 32-bit unsigned range is removed."""
        result = _sanitize_mtproto_params({"hash": -1})
        assert "hash" not in result

        result = _sanitize_mtproto_params({"hash": 0xFFFFFFFF + 1})
        assert "hash" not in result

    def test_sanitize_hash_removes_invalid(self):
        """Invalid hash types (list, dict, etc.) are removed."""
        result = _sanitize_mtproto_params({"hash": [1, 2, 3]})
        assert "hash" not in result

        result = _sanitize_mtproto_params({"hash": {"key": "value"}})
        assert "hash" not in result

        result = _sanitize_mtproto_params({"hash": None})
        assert "hash" not in result

        result = _sanitize_mtproto_params({"hash": 3.14})
        assert "hash" not in result

    def test_sanitize_hash_preserves_other_params(self):
        """Other params are unaffected by hash sanitization."""
        result = _sanitize_mtproto_params({"hash": "invite123", "peer": "user"})
        assert result["hash"] == "invite123"
        assert result["peer"] == "user"


class TestNormalizeRpcErrorCode:
    """Tests for _normalize_rpc_error_code using Telethon guts."""

    def test_user_already_participant(self):
        """UserAlreadyParticipantError maps to USER_ALREADY_PARTICIPANT."""
        e = UserAlreadyParticipantError(request=None)
        assert _normalize_rpc_error_code(e) == "USER_ALREADY_PARTICIPANT"

    def test_invite_hash_expired(self):
        """InviteHashExpiredError maps to INVITE_HASH_EXPIRED."""
        e = InviteHashExpiredError(request=None)
        assert _normalize_rpc_error_code(e) == "INVITE_HASH_EXPIRED"

    def test_non_rpc_error_returns_none(self):
        """Non-RPC exceptions return None."""
        assert _normalize_rpc_error_code(ValueError("test")) is None
        assert _normalize_rpc_error_code(TypeError("test")) is None


@pytest.mark.asyncio
async def test_invoke_mtproto_rpc_error_returns_error_code():
    """invoke_mtproto returns error_code in response when RPCError is raised."""
    mock_client = AsyncMock()
    mock_client.side_effect = UserAlreadyParticipantError(request=None)

    with patch(
        "src.tools.mtproto.get_connected_client", new_callable=AsyncMock
    ) as mock_get:
        mock_get.return_value = mock_client

        result = await invoke_mtproto_impl(
            "messages.ImportChatInvite",
            '{"hash": "testinvite123"}',
            resolve=False,
        )

    assert result.get("ok") is False
    assert "error" in result
    assert result.get("error_code") == "USER_ALREADY_PARTICIPANT"


class TestAmbiguousPeerScalar:
    """Bare int / numeric string detection for MTProto param resolution."""

    def test_int_is_ambiguous(self):
        assert is_ambiguous_peer_scalar(1660382870) is True

    def test_bool_is_not_ambiguous(self):
        assert is_ambiguous_peer_scalar(True) is False
        assert is_ambiguous_peer_scalar(False) is False

    def test_username_string_not_ambiguous(self):
        assert is_ambiguous_peer_scalar("telegram") is False
        assert is_ambiguous_peer_scalar("@channel") is False

    def test_numeric_strings_ambiguous(self):
        assert is_ambiguous_peer_scalar("1660382870") is True
        assert is_ambiguous_peer_scalar("-1001660382870") is True


@pytest.mark.asyncio
async def test_resolve_params_uses_get_entity_by_id_for_numeric_peer():
    """Numeric peer should resolve via get_entity_by_id then get_input_entity(entity)."""
    mock_entity = object()
    mock_input = object()

    mock_client = AsyncMock()
    mock_client.get_input_entity = AsyncMock(return_value=mock_input)
    mock_get_entity = AsyncMock(return_value=mock_entity)

    with (
        patch(
            "src.tools.mtproto.get_connected_client",
            new_callable=AsyncMock,
            return_value=mock_client,
        ),
        patch(
            "src.tools.mtproto.get_entity_by_id",
            new=mock_get_entity,
        ),
    ):
        out = await _resolve_params({"peer": 1660382870})

    assert out["peer"] is mock_input
    mock_get_entity.assert_awaited_once_with(1660382870, client=mock_client)
    mock_client.get_input_entity.assert_awaited_once_with(mock_entity)


@pytest.mark.asyncio
async def test_resolve_params_falls_back_when_get_entity_by_id_returns_none():
    mock_input = object()
    mock_client = AsyncMock()
    mock_client.get_input_entity = AsyncMock(return_value=mock_input)

    with (
        patch(
            "src.tools.mtproto.get_connected_client",
            new_callable=AsyncMock,
            return_value=mock_client,
        ),
        patch(
            "src.tools.mtproto.get_entity_by_id",
            new_callable=AsyncMock,
            return_value=None,
        ),
    ):
        out = await _resolve_params({"peer": 999})

    assert out["peer"] is mock_input
    mock_client.get_input_entity.assert_awaited_once_with(999)
