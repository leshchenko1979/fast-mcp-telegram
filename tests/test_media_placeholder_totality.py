"""#159: every known media class must yield a non-empty, typed placeholder.

The bug this guards against was a disagreement between two functions over the
same domain: `message_has_displayable_content()` (the display filter) claimed a
message had content because its media class was in `_KNOWN_MEDIA_CLASSES`, while
`_build_media_placeholder()` (the formatter) had a `case` branch for only 5 of
those classes and returned `None` for the rest. A contact card therefore passed
the filter and arrived with `text: null` and no `media` key at all.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.utils.message_format.core import (
    _KNOWN_MEDIA_CLASSES,
    _MEDIA_TYPES,
    _build_media_placeholder,
    message_has_displayable_content,
)


class _Message:
    """Minimal stand-in for a Telethon message carrying only `media`."""

    def __init__(self, media):
        self.media = media


def _stub(class_name: str, **attrs):
    """Build an object whose ``__class__.__name__`` is exactly ``class_name``."""
    obj = type(class_name, (), {})()
    for key, value in attrs.items():
        setattr(obj, key, value)
    return obj


def test_media_types_and_known_classes_are_the_same_set():
    """The table is the single source; the filter set is derived from it."""
    assert set(_MEDIA_TYPES) == set(_KNOWN_MEDIA_CLASSES)


def test_no_phantom_media_classes():
    """Names absent from telethon 1.45.0 must not be advertised as known."""
    phantom = {"MessageMediaVoice", "MessageMediaVideo", "MessageMediaAudio"}
    assert not (phantom & set(_MEDIA_TYPES))


@pytest.mark.parametrize("class_name", sorted(_KNOWN_MEDIA_CLASSES))
def test_every_known_class_yields_a_typed_placeholder(class_name):
    """THE structural guard.

    A class the filter accepts must always produce a placeholder carrying a type.
    This is exactly what failed for MessageMediaContact before the fix.
    """
    result = _build_media_placeholder(_Message(_stub(class_name)))
    assert result is not None, f"{class_name} produced an empty placeholder"
    assert result.get("type"), f"{class_name} produced a placeholder without a type"


def test_contact_card_is_typed_and_omits_phone_and_vcard():
    """The reported symptom: a vCard must not read as an empty message."""
    media = _stub(
        "MessageMediaContact",
        first_name="Anton",
        last_name="Lagun",
        user_id=12345,
        phone_number="+79001234567",
        vcard="BEGIN:VCARD\nVERSION:3.0\nEND:VCARD",
    )
    result = _build_media_placeholder(_Message(media))

    assert result["type"] == "contact"
    assert result["first_name"] == "Anton"
    assert result["last_name"] == "Lagun"
    assert result["user_id"] == 12345
    # Names only: phone data is stripped by default (see #156 / build_entity_dict).
    assert "phone_number" not in result
    assert "vcard" not in result


def test_geo_media_placeholder():
    geo = _stub("GeoPoint", lat=55.75, long=37.61)
    result = _build_media_placeholder(_Message(_stub("MessageMediaGeo", geo=geo)))

    assert result["type"] == "geo"
    assert result["latitude"] == 55.75
    assert result["longitude"] == 37.61


def test_geo_live_media_placeholder():
    geo = _stub("GeoPoint", lat=1.5, long=2.5)
    media = _stub("MessageMediaGeoLive", geo=geo, period=900)
    result = _build_media_placeholder(_Message(media))

    assert result["type"] == "geo_live"
    assert result["period_seconds"] == 900
    assert result["latitude"] == 1.5


def test_venue_media_placeholder():
    geo = _stub("GeoPoint", lat=1.0, long=2.0)
    media = _stub(
        "MessageMediaVenue",
        title="Cafe",
        address="Main St 1",
        provider="foursquare",
        venue_id="abc",
        venue_type="cafe",
        geo=geo,
    )
    result = _build_media_placeholder(_Message(media))

    assert result["type"] == "venue"
    assert result["title"] == "Cafe"
    assert result["address"] == "Main St 1"
    assert result["latitude"] == 1.0


def test_dice_media_placeholder():
    media = _stub("MessageMediaDice", emoticon="\U0001f3b2", value=4)
    result = _build_media_placeholder(_Message(media))

    assert result["type"] == "dice"
    assert result["value"] == 4


def test_game_media_placeholder():
    game = _stub("Game", title="Chess", short_name="chess")
    result = _build_media_placeholder(_Message(_stub("MessageMediaGame", game=game)))

    assert result["type"] == "game"
    assert result["title"] == "Chess"
    assert result["short_name"] == "chess"


def test_invoice_media_placeholder():
    media = _stub(
        "MessageMediaInvoice",
        title="Widget",
        description="A widget",
        currency="USD",
        total_amount=1999,
    )
    result = _build_media_placeholder(_Message(media))

    assert result["type"] == "invoice"
    assert result["title"] == "Widget"
    assert result["total_amount"] == 1999


def test_webpage_media_placeholder():
    page = _stub(
        "WebPage",
        url="https://example.com",
        display_url="example.com",
        title="Example",
        site_name="Example Site",
    )
    result = _build_media_placeholder(
        _Message(_stub("MessageMediaWebPage", webpage=page))
    )

    assert result["type"] == "webpage"
    assert result["url"] == "https://example.com"
    assert result["site_name"] == "Example Site"


def test_paid_media_and_story_placeholders():
    paid = _build_media_placeholder(
        _Message(_stub("MessageMediaPaidMedia", stars_amount=100))
    )
    assert paid["type"] == "paid_media"
    assert paid["stars_amount"] == 100

    story = _build_media_placeholder(_Message(_stub("MessageMediaStory", id=777)))
    assert story["type"] == "story"
    assert story["story_id"] == 777


def test_plain_document_defaults_to_document_type():
    """A PDF has no voice/round-video marker, so it must still carry a type."""
    doc = _stub("Document", mime_type="application/pdf", size=1024, attributes=[])
    result = _build_media_placeholder(
        _Message(_stub("MessageMediaDocument", document=doc))
    )

    assert result["type"] == "document"
    assert result["mime_type"] == "application/pdf"
    assert result["approx_size_bytes"] == 1024


def test_voice_document_refines_type_to_voice():
    attr = type("DocumentAttributeAudio", (), {"voice": True, "duration": 12})()
    doc = _stub("Document", mime_type="audio/ogg", size=512, attributes=[attr])
    result = _build_media_placeholder(
        _Message(_stub("MessageMediaDocument", document=doc))
    )

    assert result["type"] == "voice"
    assert result["duration_seconds"] == 12


def test_round_video_document_refines_type():
    attr = type("DocumentAttributeVideo", (), {"round_message": True, "duration": 7})()
    doc = _stub("Document", mime_type="video/mp4", size=2048, attributes=[attr])
    result = _build_media_placeholder(
        _Message(_stub("MessageMediaDocument", document=doc))
    )

    assert result["type"] == "round_video"
    assert result["duration_seconds"] == 7


def test_unknown_class_falls_back_to_raw_media_fields():
    """An unrecognised class still surfaces mime/size when the media carries them."""
    media = _stub("SomeFutureMedia", mime_type="video/mp4", size=2048)
    result = _build_media_placeholder(_Message(media))

    assert result == {"mime_type": "video/mp4", "approx_size_bytes": 2048}


def test_no_media_returns_none():
    assert _build_media_placeholder(_Message(None)) is None


# --- message-level boundary: the contract the owner reported -----------------


def _message_with(media, message_id=969497):
    """Telethon-message stand-in carrying `media` and no text."""
    msg = Mock()
    msg.id = message_id
    msg.text = None
    msg.message = None
    msg.caption = None
    msg.date = datetime(2026, 10, 6, 12, 45, 12, tzinfo=UTC)
    msg.media = media
    msg.reply_to_msg_id = None
    msg.reply_to = None
    msg.forum_topic = False
    msg.forward = None
    msg.rich_message = None
    msg.action = None
    return msg


def test_contact_only_message_passes_the_display_filter():
    """A vCard is content: it must not be filtered out of results."""
    media = _stub(
        "MessageMediaContact",
        first_name="Anton",
        last_name="Lagun",
        user_id=12345,
        phone_number="+79001234567",
        vcard="BEGIN:VCARD",
    )
    assert message_has_displayable_content(_message_with(media)) is True


def test_previously_dropped_classes_pass_the_display_filter():
    """These 6 classes were missing from _KNOWN_MEDIA_CLASSES entirely, so a
    message whose only content was one of them was dropped from results."""
    for class_name in (
        "MessageMediaStory",
        "MessageMediaGeoLive",
        "MessageMediaGiveaway",
        "MessageMediaGiveawayResults",
        "MessageMediaPaidMedia",
        "MessageMediaVideoStream",
    ):
        assert (
            message_has_displayable_content(_message_with(_stub(class_name))) is True
        ), f"{class_name} is still filtered out"


@pytest.mark.asyncio
async def test_contact_message_result_carries_typed_media_not_null():
    """The reported symptom, at the level the caller sees it.

    Before the fix this returned {"text": None} with NO "media" key -- identical
    to an empty or deleted message.
    """
    from src.utils.message_format import build_message_result

    media = _stub(
        "MessageMediaContact",
        first_name="Anton",
        last_name="Lagun",
        user_id=12345,
        phone_number="+79001234567",
        vcard="BEGIN:VCARD",
    )
    msg = _message_with(media)

    entity = Mock()
    entity.id = 509039504
    entity.title = "Anton Lagun"
    entity.username = "Anton_Lagun"

    with patch(
        "src.utils.message_format.core.get_sender_info",
        new=AsyncMock(return_value={"id": 12345, "title": "Anton Lagun"}),
    ):
        result = await build_message_result(
            msg, entity, link="https://t.me/Anton_Lagun/969497"
        )

    assert result["text"] is None
    assert "media" in result, "media key missing -- indistinguishable from empty"
    assert result["media"]["type"] == "contact"
    assert result["media"]["first_name"] == "Anton"
    assert "phone_number" not in result["media"]
