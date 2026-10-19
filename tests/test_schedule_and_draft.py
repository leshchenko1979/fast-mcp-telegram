"""Tests for the schedule_date and save_as_draft params (issue #161).

Two Telegram capabilities are exercised here:

* **Scheduling** — ``schedule_date`` on ``messages.sendMessage`` /
  ``messages.sendMedia`` / ``messages.editMessage``. Every send path must carry
  it: plain text, files, and the rich-message TL path.
* **Drafts** — ``messages.saveDraft``. Not a message, so the payload is built
  directly; empty text clears the draft; it cannot be combined with a schedule,
  files or rich content.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastmcp import Client, FastMCP
from telethon.tl import functions, types

from src.server_components.tools_register import register_tools
from src.tools.messages.drafts import save_draft
from src.tools.messages.editing import edit_message_impl
from src.tools.messages.phone import send_message_to_phone_impl
from src.tools.messages.rich_send import _message_from_tl_result
from src.tools.messages.sending import _send_message_or_files, send_message_impl
from src.utils.datetime_parse import (
    parse_iso_datetime_utc,
    parse_schedule_date,
)

# A timestamp that is always in the future relative to any test run.
FUTURE_ISO = (datetime.now(UTC) + timedelta(days=30)).isoformat()
FUTURE_TS = int(parse_iso_datetime_utc(FUTURE_ISO).timestamp())


def _fake_message(msg_id: int = 1) -> SimpleNamespace:
    return SimpleNamespace(
        id=msg_id,
        date=datetime.now(UTC),
        message="",
        text="",
        rich_message=None,
        sender=None,
        reply_markup=None,
    )


class TestParseScheduleDate:
    def test_none_means_not_scheduled(self):
        assert parse_schedule_date(None) is None
        assert parse_schedule_date("") is None

    def test_future_iso_returns_unix_timestamp(self):
        assert parse_schedule_date("2030-01-01T00:00:00Z") == 1893456000

    def test_naive_datetime_is_treated_as_utc(self):
        assert parse_schedule_date("2030-01-01T00:00:00") == 1893456000

    def test_offset_datetime_is_converted(self):
        assert parse_schedule_date("2030-01-01T03:00:00+03:00") == 1893456000

    def test_invalid_string_raises(self):
        with pytest.raises(ValueError, match="not a valid ISO 8601"):
            parse_schedule_date("tomorrow-ish")

    def test_past_instant_raises(self):
        with pytest.raises(ValueError, match="not in the future"):
            parse_schedule_date("2020-01-01T00:00:00Z")


class TestSendPathsCarrySchedule:
    @pytest.mark.asyncio
    async def test_text_send_passes_schedule(self):
        client = AsyncMock()
        client.send_message = AsyncMock(return_value=SimpleNamespace(id=1))

        error, _ = await _send_message_or_files(
            client,
            entity=SimpleNamespace(id=1),
            message="hello",
            files=None,
            reply_to_msg_id=None,
            parse_mode=None,
            operation="send_message",
            params={},
            schedule_date=FUTURE_TS,
        )

        assert error is None
        assert client.send_message.await_args.kwargs["schedule"] == FUTURE_TS

    @pytest.mark.asyncio
    async def test_file_send_passes_schedule(self):
        client = AsyncMock()
        client.send_file = AsyncMock(return_value=SimpleNamespace(id=2))

        with (
            patch(
                "src.tools.messages.sending._validate_file_paths",
                return_value=(["https://example.com/a.pdf"], None),
            ),
            patch(
                "src.tools.messages.sending.prepare_files_for_send",
                new=AsyncMock(return_value=["https://example.com/a.pdf"]),
            ),
        ):
            error, _ = await _send_message_or_files(
                client,
                entity=SimpleNamespace(id=1),
                message="doc",
                files=["https://example.com/a.pdf"],
                reply_to_msg_id=None,
                parse_mode=None,
                operation="send_message",
                params={},
                schedule_date=FUTURE_TS,
            )

        assert error is None
        assert client.send_file.await_args.kwargs["schedule"] == FUTURE_TS

    @pytest.mark.asyncio
    async def test_rich_send_passes_schedule(self):
        client = MagicMock()
        with patch(
            "src.tools.messages.sending.send_rich_via_tl",
            new=AsyncMock(return_value=(SimpleNamespace(id=3), "markdown")),
        ) as mock_send:
            error, _ = await _send_message_or_files(
                client,
                entity=SimpleNamespace(id=1),
                message="## Hi",
                files=None,
                reply_to_msg_id=None,
                parse_mode="rich",
                operation="send_message",
                params={},
                schedule_date=FUTURE_TS,
            )

        assert error is None
        assert mock_send.await_args.kwargs["schedule_date"] == FUTURE_TS

    @pytest.mark.asyncio
    async def test_unscheduled_send_passes_none(self):
        client = AsyncMock()
        client.send_message = AsyncMock(return_value=SimpleNamespace(id=1))

        await _send_message_or_files(
            client,
            entity=SimpleNamespace(id=1),
            message="hello",
            files=None,
            reply_to_msg_id=None,
            parse_mode=None,
            operation="send_message",
            params={},
        )

        assert client.send_message.await_args.kwargs["schedule"] is None


class TestDraftRejections:
    @pytest.mark.asyncio
    async def test_draft_with_files_is_rejected(self):
        client = MagicMock()
        error, payload = await _send_message_or_files(
            client,
            entity=SimpleNamespace(id=1),
            message="x",
            files=["https://example.com/a.png"],
            reply_to_msg_id=None,
            parse_mode=None,
            operation="send_message",
            params={},
            save_as_draft=True,
        )

        assert payload is None
        assert error["ok"] is False
        assert "files" in error["error"]
        client.send_file.assert_not_called()

    @pytest.mark.asyncio
    async def test_draft_with_rich_is_rejected(self):
        client = MagicMock()
        error, payload = await _send_message_or_files(
            client,
            entity=SimpleNamespace(id=1),
            message="## Hi",
            files=None,
            reply_to_msg_id=None,
            parse_mode="rich",
            operation="send_message",
            params={},
            save_as_draft=True,
        )

        assert payload is None
        assert error["ok"] is False
        assert "rich" in error["error"]

    @pytest.mark.asyncio
    async def test_draft_with_schedule_is_rejected(self):
        client = MagicMock()
        error, payload = await _send_message_or_files(
            client,
            entity=SimpleNamespace(id=1),
            message="x",
            files=None,
            reply_to_msg_id=None,
            parse_mode=None,
            operation="send_message",
            params={},
            schedule_date=FUTURE_TS,
            save_as_draft=True,
        )

        assert payload is None
        assert error["ok"] is False
        assert "schedule" in error["error"].lower()


class TestSaveDraft:
    @pytest.mark.asyncio
    async def test_saves_text_and_reports_status(self):
        client = AsyncMock()
        client.get_input_entity = AsyncMock(return_value=object())

        result = await save_draft(client, SimpleNamespace(id=5), "draft text")

        assert result["status"] == "draft_saved"
        assert result["draft_saved"] is True
        assert result["text"] == "draft text"
        request = client.await_args.args[0]
        assert request.message == "draft text"
        assert request.reply_to is None

    @pytest.mark.asyncio
    async def test_empty_text_clears_draft(self):
        client = AsyncMock()
        client.get_input_entity = AsyncMock(return_value=object())

        result = await save_draft(client, SimpleNamespace(id=5), "")

        assert result["status"] == "draft_cleared"
        assert client.await_args.args[0].message == ""

    @pytest.mark.asyncio
    async def test_reply_target_becomes_input_reply_to(self):
        client = AsyncMock()
        client.get_input_entity = AsyncMock(return_value=object())

        result = await save_draft(
            client, SimpleNamespace(id=5), "x", reply_to_msg_id=42
        )

        assert result["reply_to_id"] == 42
        assert client.await_args.args[0].reply_to.reply_to_msg_id == 42


class TestSendMessageImplScheduling:
    @pytest.mark.asyncio
    async def test_scheduled_send_reports_scheduled_status(self):
        client = AsyncMock()
        client.send_message = AsyncMock(return_value=_fake_message(11))

        with (
            patch(
                "src.tools.messages.sending.get_connected_client",
                new=AsyncMock(return_value=client),
            ),
            patch(
                "src.tools.messages.sending.get_entity_by_id",
                new=AsyncMock(return_value=SimpleNamespace(id=7, title="Chat")),
            ),
        ):
            result = await send_message_impl("7", "hello", schedule_date=FUTURE_ISO)

        assert result["status"] == "scheduled"
        assert result["scheduled"] is True
        assert (
            result["schedule_date"]
            == datetime.fromtimestamp(FUTURE_TS, UTC).isoformat()
        )
        assert client.send_message.await_args.kwargs["schedule"] == FUTURE_TS

    @pytest.mark.asyncio
    async def test_plain_send_has_no_scheduled_fields(self):
        client = AsyncMock()
        client.send_message = AsyncMock(return_value=_fake_message(12))

        with (
            patch(
                "src.tools.messages.sending.get_connected_client",
                new=AsyncMock(return_value=client),
            ),
            patch(
                "src.tools.messages.sending.get_entity_by_id",
                new=AsyncMock(return_value=SimpleNamespace(id=7, title="Chat")),
            ),
        ):
            result = await send_message_impl("7", "hello")

        assert result["status"] == "sent"
        assert "scheduled" not in result
        assert "schedule_date" not in result

    @pytest.mark.asyncio
    async def test_invalid_schedule_date_is_a_structured_error(self):
        with patch(
            "src.tools.messages.sending.get_connected_client",
            new=AsyncMock(),
        ) as mock_client:
            result = await send_message_impl("7", "hello", schedule_date="not-a-date")

        assert result["ok"] is False
        assert "ISO 8601" in result["error"]
        mock_client.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_send_as_draft_returns_draft_payload(self):
        client = AsyncMock()
        client.get_input_entity = AsyncMock(return_value=object())

        with (
            patch(
                "src.tools.messages.sending.get_connected_client",
                new=AsyncMock(return_value=client),
            ),
            patch(
                "src.tools.messages.sending.get_entity_by_id",
                new=AsyncMock(return_value=SimpleNamespace(id=7, title="Chat")),
            ),
        ):
            result = await send_message_impl("7", "draft me", save_as_draft=True)

        assert result["status"] == "draft_saved"
        assert result["draft_saved"] is True
        client.send_message.assert_not_called()


class TestEditMessageScheduling:
    @pytest.mark.asyncio
    async def test_reschedule_passes_schedule_to_client(self):
        client = AsyncMock()
        client.edit_message = AsyncMock(return_value=_fake_message(11))

        with (
            patch(
                "src.tools.messages.editing.get_connected_client",
                new=AsyncMock(return_value=client),
            ),
            patch(
                "src.tools.messages.editing.get_entity_by_id",
                new=AsyncMock(return_value=SimpleNamespace(id=7, title="Chat")),
            ),
        ):
            result = await edit_message_impl(
                "7", 11, "new text", schedule_date=FUTURE_ISO
            )

        assert result["status"] == "scheduled"
        assert result["scheduled"] is True
        assert client.edit_message.await_args.kwargs["schedule"] == FUTURE_TS

    @pytest.mark.asyncio
    async def test_plain_edit_has_no_scheduled_fields(self):
        client = AsyncMock()
        client.edit_message = AsyncMock(return_value=_fake_message(11))

        with (
            patch(
                "src.tools.messages.editing.get_connected_client",
                new=AsyncMock(return_value=client),
            ),
            patch(
                "src.tools.messages.editing.get_entity_by_id",
                new=AsyncMock(return_value=SimpleNamespace(id=7, title="Chat")),
            ),
        ):
            result = await edit_message_impl("7", 11, "new text")

        assert result["status"] == "edited"
        assert "scheduled" not in result
        assert client.edit_message.await_args.kwargs["schedule"] is None

    @pytest.mark.asyncio
    async def test_missing_message_id_without_draft_is_rejected(self):
        result = await edit_message_impl("7", None, "text")

        assert result["ok"] is False
        assert "message_id is required" in result["error"]

    @pytest.mark.asyncio
    async def test_draft_mode_needs_no_message_id(self):
        client = AsyncMock()
        client.get_input_entity = AsyncMock(return_value=object())

        with (
            patch(
                "src.tools.messages.editing.get_connected_client",
                new=AsyncMock(return_value=client),
            ),
            patch(
                "src.tools.messages.editing.get_entity_by_id",
                new=AsyncMock(return_value=SimpleNamespace(id=7, title="Chat")),
            ),
        ):
            result = await edit_message_impl(
                "7", None, "draft text", save_as_draft=True
            )

        assert result["status"] == "draft_saved"
        client.edit_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_draft_plus_schedule_is_rejected(self):
        result = await edit_message_impl(
            "7", None, "x", schedule_date=FUTURE_ISO, save_as_draft=True
        )

        assert result["ok"] is False
        assert "schedule" in result["error"].lower()


# ---------------------------------------------------------------------------
# Registered signatures — a param missing from the tool surface is invisible to
# the impl-level tests above (same defect class as issue #150).
# ---------------------------------------------------------------------------

_SEND_EDIT_TOOLS = ("send_message", "edit_message", "send_message_to_phone")


def _schemas() -> dict[str, dict]:
    temp_mcp = FastMCP("schedule/draft signature test")
    register_tools(temp_mcp)

    async def _collect() -> dict[str, dict]:
        async with Client(temp_mcp) as client:
            tools = await client.list_tools()
            return {t.name: t.inputSchema for t in tools}

    return asyncio.run(_collect())


def test_every_send_tool_advertises_both_params():
    schemas = _schemas()

    for name in _SEND_EDIT_TOOLS:
        props = schemas[name]["properties"]
        assert "schedule_date" in props, f"{name} omits schedule_date"
        assert "save_as_draft" in props, f"{name} omits save_as_draft"
        assert props["save_as_draft"]["default"] is False


def test_edit_message_advertises_message_id_as_optional():
    """Draft mode has no message id, so the registered param must be optional."""
    props = _schemas()["edit_message"]["properties"]

    assert "message_id" in props
    assert props["message_id"].get("default") is None
    assert "message_id" not in _schemas()["edit_message"].get("required", [])


@pytest.mark.asyncio
async def test_registered_send_message_forwards_non_default_values():
    impl = AsyncMock(return_value={"message_id": 1, "status": "scheduled"})

    with patch("src.server_components.tools_register.send_message_impl", new=impl):
        temp_mcp = FastMCP("forward test")
        register_tools(temp_mcp)
        async with Client(temp_mcp) as client:
            await client.call_tool(
                "send_message",
                {
                    "chat_id": "me",
                    "message": "later",
                    "schedule_date": FUTURE_ISO,
                },
            )

    assert impl.await_args.kwargs["schedule_date"] == FUTURE_ISO
    assert impl.await_args.kwargs["save_as_draft"] is False


@pytest.mark.asyncio
async def test_registered_edit_message_forwards_draft_flag_without_id():
    impl = AsyncMock(return_value={"status": "draft_saved"})

    with patch("src.server_components.tools_register.edit_message_impl", new=impl):
        temp_mcp = FastMCP("forward test")
        register_tools(temp_mcp)
        async with Client(temp_mcp) as client:
            await client.call_tool(
                "edit_message",
                {"chat_id": "me", "message": "draft", "save_as_draft": True},
            )

    assert impl.await_args.kwargs["save_as_draft"] is True
    # message_id travels positionally: (chat_id, message_id, new_text, ...)
    assert impl.await_args.args[1] is None


class TestRescheduleMessageExtraction:
    """Rescheduling a queued message must survive Telethon returning ``None``.

    Telegram answers ``messages.editMessage`` carrying ``schedule_date`` with a
    lone ``UpdateNewScheduledMessage``: no ``UpdateMessageID``, so Telethon's
    ``_get_response_message`` has no ``random_id`` to map the update back to the
    request and returns ``None`` (issue #163).
    """

    @pytest.mark.asyncio
    async def test_scheduled_edit_refetches_from_the_scheduled_queue(self):
        refetched = _fake_message(11)
        refetched.text = "new text"
        client = AsyncMock()
        client.edit_message = AsyncMock(return_value=None)
        client.get_input_entity = AsyncMock(return_value=object())
        client.return_value = SimpleNamespace(messages=[refetched])

        with (
            patch(
                "src.tools.messages.editing.get_connected_client",
                new=AsyncMock(return_value=client),
            ),
            patch(
                "src.tools.messages.editing.get_entity_by_id",
                new=AsyncMock(return_value=SimpleNamespace(id=7, title="Chat")),
            ),
        ):
            result = await edit_message_impl(
                "7", 11, "new text", schedule_date=FUTURE_ISO
            )

        assert result.get("ok") is not False, result
        assert result["status"] == "scheduled"
        assert result["message_id"] == 11
        assert result["text"] == "new text"

        request = client.call_args.args[0]
        assert isinstance(request, functions.messages.GetScheduledMessagesRequest)
        assert request.id == [11]

    @pytest.mark.asyncio
    async def test_plain_edit_never_touches_the_scheduled_queue(self):
        client = AsyncMock()
        client.edit_message = AsyncMock(return_value=_fake_message(11))

        with (
            patch(
                "src.tools.messages.editing.get_connected_client",
                new=AsyncMock(return_value=client),
            ),
            patch(
                "src.tools.messages.editing.get_entity_by_id",
                new=AsyncMock(return_value=SimpleNamespace(id=7, title="Chat")),
            ),
        ):
            result = await edit_message_impl("7", 11, "new text")

        assert result["status"] == "edited"
        client.assert_not_called()

    @pytest.mark.asyncio
    async def test_rich_scheduled_result_uses_the_update_message(self):
        """A queued rich message is unreachable by messages.getMessages."""
        message = _fake_message(21)
        update = types.UpdateNewScheduledMessage(message=message)
        client = MagicMock()
        client._get_response_message = MagicMock(return_value=None)
        client.get_messages = AsyncMock(return_value=None)

        extracted = await _message_from_tl_result(
            client, object(), SimpleNamespace(updates=[update]), object()
        )

        assert extracted is message
        client.get_messages.assert_not_called()


class TestPhonePathCarriesScheduleAndDraft:
    """send_message_to_phone resolves a contact first, then delegates."""

    @pytest.mark.asyncio
    async def test_phone_send_forwards_schedule(self):
        client = AsyncMock()
        client.get_entity = AsyncMock(return_value=SimpleNamespace(id=99))
        delegated = AsyncMock(return_value=(None, _fake_message(31)))

        with (
            patch(
                "src.tools.messages.phone.get_connected_client",
                new=AsyncMock(return_value=client),
            ),
            patch("src.tools.messages.phone._send_message_or_files", new=delegated),
        ):
            result = await send_message_to_phone_impl(
                phone_number="+10000000000", message="hi", schedule_date=FUTURE_ISO
            )

        assert result.get("ok") is not False, result
        assert delegated.await_args.kwargs["schedule_date"] == FUTURE_TS
        assert delegated.await_args.kwargs["save_as_draft"] is False

    @pytest.mark.asyncio
    async def test_phone_send_forwards_draft_flag(self):
        client = AsyncMock()
        client.get_entity = AsyncMock(return_value=SimpleNamespace(id=99))
        delegated = AsyncMock(return_value=({"status": "draft_saved"}, None))

        with (
            patch(
                "src.tools.messages.phone.get_connected_client",
                new=AsyncMock(return_value=client),
            ),
            patch("src.tools.messages.phone._send_message_or_files", new=delegated),
        ):
            result = await send_message_to_phone_impl(
                phone_number="+10000000000", message="hi", save_as_draft=True
            )

        assert result["status"] == "draft_saved"
        assert delegated.await_args.kwargs["save_as_draft"] is True
        assert delegated.await_args.kwargs["schedule_date"] is None

    @pytest.mark.asyncio
    async def test_phone_draft_plus_schedule_is_rejected(self):
        """The combination is refused before any client is opened.

        Asserting only ``ok is False`` let this test pass while still building a
        real client — it failed in CI, where API_ID is absent, and would have
        reached the network locally. The patch makes the ordering the assertion.
        """

        def _no_client():
            raise AssertionError(
                "draft+schedule must be rejected before get_connected_client()"
            )

        with patch(
            "src.tools.messages.phone.get_connected_client",
            new=AsyncMock(side_effect=_no_client),
        ):
            result = await send_message_to_phone_impl(
                phone_number="+10000000000",
                message="hi",
                schedule_date=FUTURE_ISO,
                save_as_draft=True,
            )

        assert result["ok"] is False
        assert "draft_with_schedule" in str(result)

    @pytest.mark.asyncio
    async def test_send_message_draft_plus_schedule_is_rejected_without_client(self):
        """Same ordering guarantee on the send path."""

        def _no_client():
            raise AssertionError(
                "draft+schedule must be rejected before get_connected_client()"
            )

        with patch(
            "src.tools.messages.sending.get_connected_client",
            new=AsyncMock(side_effect=_no_client),
        ):
            result = await send_message_impl(
                chat_id="me",
                message="hi",
                schedule_date=FUTURE_ISO,
                save_as_draft=True,
            )

        assert result["ok"] is False
        assert "draft_with_schedule" in str(result)
