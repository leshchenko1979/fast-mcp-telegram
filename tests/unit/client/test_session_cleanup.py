"""Tests for mtime-based inactivity session cleanup."""

from pathlib import Path
from unittest.mock import patch

import pytest

from src.client.connection import _cleanup_inactive_sessions

_TOKEN = "abcdefghijklmnopqrstuvwxyz0123456789ABCDEFg"  # 43-char valid token

# Match the default in src/config/server_config.py
_DEFAULT_INACTIVE_DAYS = 30


def make_session_file(session_dir: Path, token: str) -> Path:
    """Create a fake Telethon .session file for *token* with known mtime."""
    path = session_dir / f"{token}.session"
    path.write_text("fake session data")
    return path


# ---------------------------------------------------------------------------
# _cleanup_inactive_sessions
# ---------------------------------------------------------------------------


class TestCleanupInactiveSessions:
    """Main cleanup — deletes .session files with old mtime."""

    @pytest.mark.asyncio
    async def test_deletes_when_mtime_older_than_cutoff(self, tmp_path):
        """Session file with mtime >inactive_session_days days ago is deleted."""
        now = 1_000_000_000.0
        old_mtime = now - _DEFAULT_INACTIVE_DAYS * 86400 - 100  # well before cutoff

        session_file = make_session_file(tmp_path, _TOKEN)
        # Set old mtime
        import os as _os

        _os.utime(str(session_file), (old_mtime, old_mtime))

        assert session_file.is_file()

        with (
            patch("src.client.connection.SESSION_DIR", tmp_path),
            patch("src.client.connection.time.time", return_value=now),
            patch("src.client.connection.get_config") as mock_get_config,
        ):
            mock_get_config.return_value.inactive_session_days = _DEFAULT_INACTIVE_DAYS
            deleted = await _cleanup_inactive_sessions()

        assert deleted == 1
        assert not session_file.is_file()

    @pytest.mark.asyncio
    async def test_keeps_when_mtime_recent(self, tmp_path):
        """Session file with mtime <inactive_session_days days ago is kept."""
        now = 1_000_000_000.0
        recent_mtime = now - 10  # 10 seconds ago

        session_file = make_session_file(tmp_path, _TOKEN)
        import os as _os

        _os.utime(str(session_file), (recent_mtime, recent_mtime))

        with (
            patch("src.client.connection.SESSION_DIR", tmp_path),
            patch("src.client.connection.time.time", return_value=now),
            patch("src.client.connection.get_config") as mock_get_config,
        ):
            mock_get_config.return_value.inactive_session_days = _DEFAULT_INACTIVE_DAYS
            deleted = await _cleanup_inactive_sessions()

        assert deleted == 0
        assert session_file.is_file()

    @pytest.mark.asyncio
    async def test_mixed_old_and_recent(self, tmp_path):
        """Multiple session files: old ones deleted, recent kept."""
        now = 1_000_000_000.0
        old_mtime = now - _DEFAULT_INACTIVE_DAYS * 86400 - 500
        recent_mtime = now - 10

        token_a = _TOKEN
        token_b = "abcdefghijklmnopqrstuvwxyz0123456789ABCDEFh"  # different token

        old_file = make_session_file(tmp_path, token_a)
        recent_file = make_session_file(tmp_path, token_b)

        import os as _os

        _os.utime(str(old_file), (old_mtime, old_mtime))
        _os.utime(str(recent_file), (recent_mtime, recent_mtime))

        with (
            patch("src.client.connection.SESSION_DIR", tmp_path),
            patch("src.client.connection.time.time", return_value=now),
            patch("src.client.connection.get_config") as mock_get_config,
        ):
            mock_get_config.return_value.inactive_session_days = _DEFAULT_INACTIVE_DAYS
            deleted = await _cleanup_inactive_sessions()

        assert deleted == 1
        assert not old_file.is_file()  # deleted
        assert recent_file.is_file()  # kept

    @pytest.mark.asyncio
    async def test_skips_nonexistent_file(self, tmp_path):
        """Non-existent directory doesn't crash."""
        with (
            patch("src.client.connection.SESSION_DIR", tmp_path / "does-not-exist"),
            patch("src.client.connection.time.time", return_value=1_000_000_000.0),
        ):
            deleted = await _cleanup_inactive_sessions()
        assert deleted == 0

    @pytest.mark.asyncio
    @pytest.mark.parametrize("days", [0, -1])
    async def test_disabled_when_non_positive(self, tmp_path, days):
        """When inactive_session_days <= 0, cleanup does nothing."""
        now = 1_000_000_000.0
        old_mtime = now - 86400 * 100  # 100 days ago

        session_file = make_session_file(tmp_path, _TOKEN)
        import os as _os

        _os.utime(str(session_file), (old_mtime, old_mtime))

        with (
            patch("src.client.connection.SESSION_DIR", tmp_path),
            patch("src.client.connection.time.time", return_value=now),
            patch("src.client.connection.get_config") as mock_get_config,
        ):
            mock_get_config.return_value.inactive_session_days = days
            deleted = await _cleanup_inactive_sessions()

        assert deleted == 0
        assert session_file.is_file()

    @pytest.mark.asyncio
    async def test_skips_non_session_files(self, tmp_path):
        """Files without .session suffix are ignored."""
        (tmp_path / "not_a_session.txt").write_text("ignore me")

        with (
            patch("src.client.connection.SESSION_DIR", tmp_path),
            patch("src.client.connection.time.time", return_value=1_000_000_000.0),
        ):
            deleted = await _cleanup_inactive_sessions()
        assert deleted == 0
        assert (tmp_path / "not_a_session.txt").is_file()
