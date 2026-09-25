#!/usr/bin/env python3
"""
Tests for MTProto tool: hash sanitization, RPC error normalization,
TL object construction, and peer type conversion.
"""

from unittest.mock import AsyncMock, patch

import pytest
from telethon.errors import InviteHashExpiredError, UserAlreadyParticipantError

from src.tools.mtproto import (
    _normalize_rpc_error_code,
    invoke_mtproto_impl,
)
from src.tools.mtproto_tl import (
    _construct_tl_params,
    _convert_peer_types,
    _resolve_params,
    _sanitize_mtproto_params,
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
            "src.tools.mtproto_tl.get_connected_client",
            new_callable=AsyncMock,
            return_value=mock_client,
        ),
        patch(
            "src.tools.mtproto_tl.get_entity_by_id",
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
            "src.tools.mtproto_tl.get_connected_client",
            new_callable=AsyncMock,
            return_value=mock_client,
        ),
        patch(
            "src.tools.mtproto_tl.get_entity_by_id",
            new_callable=AsyncMock,
            return_value=None,
        ),
    ):
        out = await _resolve_params({"peer": 999})

    assert out["peer"] is mock_input
    mock_client.get_input_entity.assert_awaited_once_with(999)


class TestConstructTlParams:
    """Tests for ``_construct_tl_params`` — TL dict → Telethon objects.

    Covers Bug #1: TL object construction from nested dicts with ``resolve=false``
    (``_construct_tl_params`` must run regardless of the resolve flag).
    """

    def test_converts_input_user_dict(self):
        """``{"_": "inputUser", ...}`` converts to ``InputUser``."""
        from telethon.tl.types import InputUser

        result = _construct_tl_params(
            {
                "user_id": {
                    "_": "inputUser",
                    "user_id": 8957744751,
                    "access_hash": 9876543210,
                },
            }
        )
        assert isinstance(result["user_id"], InputUser)
        assert result["user_id"].user_id == 8957744751
        assert result["user_id"].access_hash == 9876543210

    def test_preserves_int_params(self):
        """Non-dict int params pass through unchanged."""
        result = _construct_tl_params(
            {
                "chat_id": 5417489797,
                "fwd_limit": 50,
            }
        )
        assert result["chat_id"] == 5417489797
        assert result["fwd_limit"] == 50

    def test_preserves_string_hash(self):
        """String hash and other string params pass through unchanged."""
        result = _construct_tl_params({"hash": "invite123"})
        assert result["hash"] == "invite123"

    def test_empty_dict(self):
        """Empty params → empty result."""
        assert _construct_tl_params({}) == {}

    def test_list_of_tl_dicts(self):
        """Lists of TL dicts are also converted recursively."""
        from telethon.tl.types import InputUser

        result = _construct_tl_params(
            {
                "participants": [
                    {"_": "inputUser", "user_id": 1, "access_hash": 100},
                    {"_": "inputUser", "user_id": 2, "access_hash": 200},
                ],
            }
        )
        assert len(result["participants"]) == 2
        assert isinstance(result["participants"][0], InputUser)
        assert result["participants"][1].user_id == 2

    def test_unknown_tl_dict_passes_through(self):
        """Dict with unknown ``_`` key is kept as-is."""
        result = _construct_tl_params(
            {
                "chat_id": {"_": "NonExistentType", "id": 123},
            }
        )
        assert isinstance(result["chat_id"], dict)
        assert result["chat_id"]["_"] == "NonExistentType"

    def test_nested_tl_dict_in_resolve_false_flow(self):
        """Simulates the Bug #1 scenario: TL dict with ``resolve=False``.

        When the user passes an explicit TL dict and ``resolve=False``,
        ``_construct_tl_params`` should build the TL object so that it
        can then be processed by ``_convert_peer_types`` (int extraction)
        without hitting "Cannot cast dict to Peer".
        """
        from telethon.tl.types import InputUser

        result = _construct_tl_params(
            {
                "chat_id": {
                    "_": "inputUser",
                    "user_id": 5417489797,
                    "access_hash": 123,
                },
                "fwd_limit": 50,
            }
        )
        assert isinstance(result["chat_id"], InputUser)
        assert result["chat_id"].user_id == 5417489797
        assert result["fwd_limit"] == 50


class TestConvertPeerTypes:
    """Tests for ``_convert_peer_types`` — InputPeer* → int extraction.

    Covers Bug #2: when ``_resolve_params`` converts an int peer to
    ``InputPeer*`` (e.g. ``InputPeerChat``), but the method's signature
    expects ``int`` (e.g. ``AddChatUserRequest.__init__(chat_id: int)``),
    the raw ID must be extracted from the peer object.
    """

    @pytest.mark.asyncio
    async def test_input_peer_chat_to_int(self):
        """``InputPeerChat`` → raw ``chat_id`` for method expecting ``int``."""
        from unittest.mock import MagicMock

        from telethon.tl.functions.messages import AddChatUserRequest
        from telethon.tl.types import InputPeerChat, InputPeerUser

        mock_entity = MagicMock()
        mock_entity.id = 8957744751
        mock_entity.access_hash = 1234567890

        mock_client = AsyncMock()
        mock_client.get_entity = AsyncMock(return_value=mock_entity)

        params = {
            "chat_id": InputPeerChat(chat_id=5417489797),
            "user_id": InputPeerUser(user_id=8957744751, access_hash=1234567890),
            "fwd_limit": 50,
        }

        result = await _convert_peer_types(mock_client, params, AddChatUserRequest)

        # chat_id: int → extract from InputPeerChat
        assert result["chat_id"] == 5417489797
        assert isinstance(result["chat_id"], int)

        # user_id: 'TypeInputUser' → if entity is in client cache,
        # Case 2 converts InputPeerUser → InputUser (correct behavior).
        from telethon.tl.types import InputUser

        assert isinstance(result["user_id"], InputUser)
        assert result["user_id"].user_id == 8957744751

        # fwd_limit: already int, unchanged
        assert result["fwd_limit"] == 50

    @pytest.mark.asyncio
    async def test_int_params_unchanged(self):
        """Int params that are already int pass through unchanged."""
        from telethon.tl.functions.messages import AddChatUserRequest

        mock_client = AsyncMock()
        params = {"chat_id": 5417489797, "fwd_limit": 50}

        result = await _convert_peer_types(mock_client, params, AddChatUserRequest)

        assert result["chat_id"] == 5417489797
        assert result["fwd_limit"] == 50

    @pytest.mark.asyncio
    async def test_input_peer_user_to_int(self):
        """``InputPeerUser`` → raw ``user_id`` for method expecting ``int``."""
        from telethon.tl.types import InputPeerUser

        # Create a method that expects user_id: int
        class FakeRequest:
            def __init__(self, user_id: int):
                pass

        mock_client = AsyncMock()
        params = {"user_id": InputPeerUser(user_id=8957744751, access_hash=1234567890)}

        result = await _convert_peer_types(mock_client, params, FakeRequest)

        assert result["user_id"] == 8957744751
        assert isinstance(result["user_id"], int)


class TestInvokeMtprotoWithTlDict:
    """Integration: ``invoke_mtproto_impl`` with TL dict + ``resolve=False``.

    Covers Bug #1 + Bug #2 working together: the user passes an explicit TL
    dict for the user_id parameter, resolve=False, and the tool should
    construct the TL object, extract the raw int for methods expecting int,
    and invoke successfully.
    """

    @pytest.mark.asyncio
    async def test_tl_dict_with_resolve_false(self):
        """TL dict with resolve=False → constructs TL object, invokes successfully."""

        mock_client = AsyncMock()
        mock_client.return_value = {"_": "InvitedUsers", "users": [{"id": 1}]}

        with patch(
            "src.tools.mtproto.get_connected_client",
            new_callable=AsyncMock,
            return_value=mock_client,
        ):
            result = await invoke_mtproto_impl(
                "messages.AddChatUser",
                '{"chat_id": 5417489797, "user_id": {"_": "inputUser", "user_id": 8957744751, "access_hash": 1234567890}, "fwd_limit": 50}',
                resolve=False,
            )

        # Should invoke successfully (not crash with "Cannot cast dict to Peer")
        assert result is not None
        assert not isinstance(result, dict) or result.get("ok") is not False

    @pytest.mark.asyncio
    async def test_int_peer_with_resolve_true(self):
        """Int peer with resolve=True → resolves, extracts int, invokes.

        When resolve=True and chat_id=5417489797 (int),
        _resolve_params returns InputPeerChat, but _convert_peer_types
        extracts the int back for AddChatUserRequest which expects chat_id: int.
        """
        mock_input_chat = AsyncMock()
        mock_input_chat.__class__.__name__ = "InputPeerChat"
        mock_input_chat.chat_id = 5417489797

        mock_input_user = AsyncMock()
        mock_input_user.__class__.__name__ = "InputUserFromMessage"
        mock_input_user.user_id = 8957744751

        mock_client = AsyncMock()
        mock_client.get_input_entity.side_effect = [mock_input_chat, mock_input_user]
        mock_client.return_value = {"_": "InvitedUsers", "users": [{"id": 1}]}

        with (
            patch(
                "src.tools.mtproto_tl.get_connected_client",
                new_callable=AsyncMock,
                return_value=mock_client,
            ),
            patch(
                "src.tools.mtproto.get_connected_client",
                new_callable=AsyncMock,
                return_value=mock_client,
            ),
            patch(
                "src.tools.mtproto_tl.get_entity_by_id",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            result = await invoke_mtproto_impl(
                "messages.AddChatUser",
                '{"chat_id": 5417489797, "user_id": 8957744751, "fwd_limit": 50}',
                resolve=True,
            )

        # Should not crash with "required argument is not an integer"
        assert result is not None


class TestParameterPhaseErrors:
    """Phase-accurate labels for the construction vs entity-resolution split.

    Regression guard: ``invoke_mtproto`` used to wrap BOTH phases in one
    exception boundary and report every failure as "Failed to resolve
    parameters", so a client/session-store fault read as a parameter fault.
    """

    @pytest.mark.asyncio
    async def test_construction_failure_uses_construction_label(self):
        """A construction fault reports the construction phase, not resolution."""
        with patch(
            "src.tools.mtproto._construct_tl_params",
            side_effect=ValueError("construct-boom"),
        ):
            result = await invoke_mtproto_impl(
                "messages.GetHistory",
                '{"peer": {"_": "inputPeerSelf"}}',
                resolve=True,
            )

        assert result["ok"] is False
        assert "Failed to construct TL parameters" in result["error"]
        assert "Failed to resolve entity parameters" not in result["error"]
        assert result["operation"] == "invoke_mtproto"
        assert result["exception"]["type"] == "ValueError"
        assert result["exception"]["message"] == "construct-boom"

    @pytest.mark.asyncio
    async def test_resolution_failure_uses_resolution_label(self):
        """A client/session fault during resolution reports the resolution phase."""
        with (
            patch(
                "src.tools.mtproto._construct_tl_params",
                return_value={"peer": 1},
            ),
            patch(
                "src.tools.mtproto._resolve_params",
                new_callable=AsyncMock,
                side_effect=ValueError("resolve-boom"),
            ),
        ):
            result = await invoke_mtproto_impl(
                "messages.GetHistory",
                '{"peer": 1}',
                resolve=True,
            )

        assert result["ok"] is False
        assert "Failed to resolve entity parameters" in result["error"]
        assert "Failed to construct TL parameters" not in result["error"]
        assert result["operation"] == "invoke_mtproto"
        assert result["exception"]["type"] == "ValueError"
        assert result["exception"]["message"] == "resolve-boom"

    @pytest.mark.asyncio
    async def test_successful_construction_runs_both_phases(self):
        """Control: on the success path both phases run and no phase label appears."""
        mock_client = AsyncMock()
        mock_client.return_value = {"_": "Ok"}

        with (
            patch(
                "src.tools.mtproto._construct_tl_params",
                return_value={"peer": 1},
            ) as mock_construct,
            patch(
                "src.tools.mtproto._resolve_params",
                new_callable=AsyncMock,
                return_value={"peer": 1},
            ) as mock_resolve,
            patch(
                "src.tools.mtproto.get_connected_client",
                new_callable=AsyncMock,
                return_value=mock_client,
            ),
        ):
            result = await invoke_mtproto_impl(
                "messages.GetHistory",
                '{"peer": 1}',
                resolve=True,
            )

        mock_construct.assert_called_once()
        mock_resolve.assert_called_once()
        assert result is not None
        error = result.get("error", "") if isinstance(result, dict) else str(result)
        assert "Failed to construct TL parameters" not in error
        assert "Failed to resolve entity parameters" not in error

    @pytest.mark.asyncio
    async def test_resolve_false_skips_resolution_phase(self):
        """Phase 2 is opt-in: resolve=False must not call _resolve_params."""
        mock_client = AsyncMock()

        with (
            patch(
                "src.tools.mtproto._construct_tl_params",
                return_value={"peer": 1},
            ) as mock_construct,
            patch(
                "src.tools.mtproto._resolve_params",
                new_callable=AsyncMock,
            ) as mock_resolve,
            patch(
                "src.tools.mtproto.get_connected_client",
                new_callable=AsyncMock,
                return_value=mock_client,
            ),
        ):
            await invoke_mtproto_impl(
                "messages.GetHistory",
                '{"peer": 1}',
                resolve=False,
            )

        mock_construct.assert_called_once()
        mock_resolve.assert_not_called()


class TestScalarRpcResult:
    """Regression tests for issue #153.

    A method whose RPC result is a bare ``Bool`` (``messages.EditChatAbout`` is
    the confirmed instance) rendered as the Python literal ``"True"`` through
    ``str(result)``, and FastMCP rejected it with ``structured_content must be a
    dict or None. Got str: 'True'``. The call had SUCCEEDED, so the caller saw a
    hard error for a write that had already landed.
    """

    @pytest.mark.asyncio
    @pytest.mark.parametrize("raw", [True, False, 42, "ok"])
    async def test_scalar_result_is_wrapped_not_stringified(self, raw):
        """A non-object RPC result is wrapped so the success signal survives."""
        mock_client = AsyncMock(return_value=raw)

        with (
            patch(
                "src.tools.mtproto.get_connected_client",
                new_callable=AsyncMock,
                return_value=mock_client,
            ),
            patch(
                "src.tools.mtproto._convert_peer_types",
                new_callable=AsyncMock,
                side_effect=lambda _c, p, _m: p,
            ),
        ):
            result = await invoke_mtproto_impl(
                "messages.EditChatAbout",
                '{"peer": 1, "about": "x"}',
                resolve=False,
            )

        assert isinstance(result, dict), (
            "a scalar RPC result must still be a dict or FastMCP rejects it "
            "as structured_content (issue #153)"
        )
        assert result == {"result": raw}

    @pytest.mark.asyncio
    async def test_object_result_shape_is_unchanged(self):
        """Negative control: an object result keeps its own fields, unwrapped."""

        class _FakeTLObject:
            def to_dict(self):
                return {"_": "FakeTLObject", "value": 1}

        mock_client = AsyncMock(return_value=_FakeTLObject())

        with (
            patch(
                "src.tools.mtproto.get_connected_client",
                new_callable=AsyncMock,
                return_value=mock_client,
            ),
            patch(
                "src.tools.mtproto._convert_peer_types",
                new_callable=AsyncMock,
                side_effect=lambda _c, p, _m: p,
            ),
        ):
            result = await invoke_mtproto_impl(
                "messages.EditChatAbout",
                '{"peer": 1, "about": "x"}',
                resolve=False,
            )

        assert result == {"_": "FakeTLObject", "value": 1}
        assert "result" not in result

    @pytest.mark.asyncio
    async def test_registered_tool_reports_success_for_scalar_result(self):
        """The REGISTERED tool must not error on a successful scalar call.

        Driving the registered tool is load-bearing: the defect surfaced in
        FastMCP's structured_content validation, which the impl-level tests
        above cannot observe.
        """
        from fastmcp import Client, FastMCP

        from src.server_components.tools_register import register_tools

        temp_mcp = FastMCP("invoke_mtproto scalar result test")
        register_tools(temp_mcp)

        mock_client = AsyncMock(return_value=True)

        with (
            patch(
                "src.tools.mtproto.get_connected_client",
                new_callable=AsyncMock,
                return_value=mock_client,
            ),
            patch(
                "src.tools.mtproto._convert_peer_types",
                new_callable=AsyncMock,
                side_effect=lambda _c, p, _m: p,
            ),
        ):
            async with Client(temp_mcp) as client:
                result = await client.call_tool(
                    "invoke_mtproto",
                    {
                        "method_full_name": "messages.EditChatAbout",
                        "params_json": '{"peer": 1, "about": "x"}',
                        "resolve": False,
                    },
                )

        assert result.structured_content == {"result": True}
