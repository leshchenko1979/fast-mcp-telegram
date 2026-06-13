"""Tests for _parse_telegram_url helper in src.utils.entity.

Covers all supported URL formats and boundary cases.
The function is private but tested directly — it's a pure function with no side effects.
"""

import pytest

from src.utils.entity import _parse_telegram_url


# ── t.me URLs ──


def test_tme_username() -> None:
    assert _parse_telegram_url("https://t.me/durov") == "durov"


def test_tme_username_trailing_slash() -> None:
    assert _parse_telegram_url("https://t.me/durov/") == "durov"


def test_tme_username_with_message_id() -> None:
    assert _parse_telegram_url("https://t.me/durov/12345") == "durov"


def test_tme_username_deep_link() -> None:
    assert _parse_telegram_url("https://t.me/durov/12345?single") == "durov"


def test_tme_no_scheme() -> None:
    assert _parse_telegram_url("t.me/durov") == "durov"


def test_tme_http() -> None:
    assert _parse_telegram_url("http://t.me/durov") == "durov"


def test_tme_www_prefix() -> None:
    assert _parse_telegram_url("https://www.t.me/durov") == "durov"


def test_tme_channel_numeric_c() -> None:
    """https://t.me/c/1234567890 → Telethon channel ID -1001234567890."""
    assert _parse_telegram_url("https://t.me/c/1234567890") == "-1001234567890"


def test_tme_channel_numeric_c_trailing() -> None:
    assert _parse_telegram_url("https://t.me/c/1234567890/") == "-1001234567890"


def test_tme_channel_numeric_c_with_message() -> None:
    assert _parse_telegram_url("https://t.me/c/1234567890/999") == "-1001234567890"


def test_tme_invite_link() -> None:
    """Invite links (+XXXXXXXX) should be returned as-is for Telethon to handle."""
    url = "https://t.me/+AbCdEfGhIjKlMnOp"
    assert _parse_telegram_url(url) == url


def test_tme_joinchat() -> None:
    """Joinchat links should be returned as-is."""
    url = "https://t.me/joinchat/AbCdEfGhIjKlMnOp"
    assert _parse_telegram_url(url) == url


def test_tme_stories() -> None:
    """https://t.me/s/username → username (stories URL)."""
    assert _parse_telegram_url("https://t.me/s/durov") == "durov"


def test_tme_boost() -> None:
    """https://t.me/boost/username → username."""
    assert _parse_telegram_url("https://t.me/boost/durov") == "durov"


# ── telegram.me URLs ──


def test_telegram_me_username() -> None:
    assert _parse_telegram_url("https://telegram.me/durov") == "durov"


def test_telegram_me_no_scheme() -> None:
    assert _parse_telegram_url("telegram.me/durov") == "durov"


def test_telegram_me_www() -> None:
    assert _parse_telegram_url("https://www.telegram.me/durov") == "durov"


# ── telegram.dog URLs ──


def test_telegram_dog_username() -> None:
    """telegram.dog is an alternative domain (used by some forks)."""
    assert _parse_telegram_url("https://telegram.dog/durov") == "durov"


# ── Not Telegram URLs — should all return None ──


def test_non_telegram_url() -> None:
    assert _parse_telegram_url("https://example.com/durov") is None


def test_non_telegram_url_with_path() -> None:
    assert _parse_telegram_url("https://example.com/t.me/durov") is None


def test_plain_username() -> None:
    """Regular @username or bare username should NOT match."""
    assert _parse_telegram_url("durov") is None


def test_at_username() -> None:
    """@username is already handled by Telethon — no URL parsing needed."""
    assert _parse_telegram_url("@durov") is None


def test_numeric_string() -> None:
    assert _parse_telegram_url("123456789") is None


def test_empty_string() -> None:
    assert _parse_telegram_url("") is None


def test_whitespace_only() -> None:
    assert _parse_telegram_url("   ") is None


def test_just_domain_no_path() -> None:
    """https://t.me without a path should NOT match (requires /something)."""
    assert _parse_telegram_url("https://t.me") is None


def test_me_identifier() -> None:
    """Special 'me' identifier should not be altered."""
    assert _parse_telegram_url("me") is None


def test_self_identifier() -> None:
    assert _parse_telegram_url("self") is None


# ── Edge cases ──


def test_case_insensitive_domain() -> None:
    assert _parse_telegram_url("HTTPS://T.ME/Durov") == "Durov"


def test_username_with_dots() -> None:
    assert _parse_telegram_url("https://t.me/user.name") == "user.name"


def test_username_with_underscores() -> None:
    assert _parse_telegram_url("https://t.me/user_name") == "user_name"
