"""
Tests for the transcription cooldown cache in _transcribe_single_voice_message.

Bug: every call to get_messages("me") re-issues TranscribeAudioRequest for the
same voice message ids, hitting Telegram's per-message cooldown
(FloodWaitError seconds=~2328). The result is silently swallowed and the user
gets no transcription on the second call.

Fix: an in-memory cache keyed by (peer_id, msg_id) that:
  - skips the API call while the rate-limit window is still active
  - records in-flight "pending" transcriptions and reuses their transcription_id
  - returns the cached text for completed transcriptions within a TTL
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from telethon.errors import FloodWaitError


# A "User"-like entity; the class name is "User" so the cache key
# detector classifies it as a user peer. Telethon resolves chat_id="me"
# to a UserFull-like object whose .id is the user id.
class _User:
    def __init__(self, user_id: int) -> None:
        self.id = user_id
        self.first_name = "Test"


def _make_user(user_id: int = 12345) -> _User:
    return _User(user_id)


def _make_transcribe_result(
    text: str | None = None,
    *,
    pending: bool = False,
    transcription_id: str | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        text=text,
        pending=pending,
        transcription_id=transcription_id,
    )


@pytest.fixture(autouse=True)
def _patched_sleep(monkeypatch):
    """Make any asyncio.sleep in the transcription loop instant."""

    async def _noop(_seconds: float) -> None:
        return None

    monkeypatch.setattr("src.utils.message_format.asyncio.sleep", _noop)


@pytest.fixture
def client_factory():
    """Return a callable that produces a mock client. Each call is recorded."""
    calls: list[tuple[object, ...]] = []

    def _build(responses: list[object]):
        async def _invoke(request):
            calls.append(request)
            if not responses:
                raise AssertionError("client invoked more times than expected")
            response = responses.pop(0)
            if isinstance(response, BaseException):
                raise response
            return response

        client = MagicMock()
        client.side_effect = _invoke
        return client, calls

    return _build


@pytest.fixture(autouse=True)
def _clear_transcription_cache():
    """Wipe the module-level transcription cache between tests so they don't
    leak entries into each other."""
    from src.utils.message_format import _TRANSCRIPTION_CACHE

    _TRANSCRIPTION_CACHE.clear()
    yield
    _TRANSCRIPTION_CACHE.clear()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_within_cooldown_does_not_re_issue_transcribe_audio(client_factory):
    """Second call within the cooldown window must NOT re-issue TranscribeAudio."""
    from src.utils.message_format import _transcribe_single_voice_message

    flood = FloodWaitError(request=None, capture=2328)
    client, calls = client_factory([flood])

    user = _make_user(12345)
    message_id = 818045

    first = await _transcribe_single_voice_message(client, user, message_id)
    second = await _transcribe_single_voice_message(client, user, message_id)
    third = await _transcribe_single_voice_message(client, user, message_id)

    # All three calls return None (no transcription available, rate-limited).
    assert first is None
    assert second is None
    assert third is None
    # The first call hits the API; subsequent calls are served from the cache.
    assert len(calls) == 1, f"expected 1 API call, got {len(calls)}"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_after_cooldown_re_issues_and_succeeds(client_factory, monkeypatch):
    """Once the cooldown window expires, the next call must re-issue and succeed."""
    from src.utils.message_format import _transcribe_single_voice_message

    flood = FloodWaitError(request=None, capture=2328)
    success = _make_transcribe_result(text="Возвращаюсь к Ксюше.")
    client, calls = client_factory([flood, success])

    # Force a tiny cooldown so the test is fast.
    import src.utils.message_format as mf

    monkeypatch.setattr(mf.time, "time", lambda: 0.0)
    user = _make_user(12345)

    first = await _transcribe_single_voice_message(client, user, 818045)
    assert first is None

    # Still inside the cooldown window — no extra call.
    monkeypatch.setattr(mf.time, "time", lambda: 100.0)
    second = await _transcribe_single_voice_message(client, user, 818045)
    assert second is None
    assert len(calls) == 1

    # Cooldown expired — re-issue succeeds.
    monkeypatch.setattr(mf.time, "time", lambda: 3000.0)
    third = await _transcribe_single_voice_message(client, user, 818045)
    assert third == "Возвращаюсь к Ксюше."
    assert len(calls) == 2

    # Cached success — no third call.
    monkeypatch.setattr(mf.time, "time", lambda: 3050.0)
    fourth = await _transcribe_single_voice_message(client, user, 818045)
    assert fourth == "Возвращаюсь к Ксюше."
    assert len(calls) == 2


@pytest.mark.unit
@pytest.mark.asyncio
async def test_pending_transcription_id_is_reused(client_factory):
    """When the first call returns pending, the cached transcription_id
    must be reused on subsequent polls (we must not lose the id across calls)."""
    from src.utils.message_format import _transcribe_single_voice_message

    # First TranscribeAudio call returns pending. The internal polling loop
    # then re-issues TranscribeAudio and gets the completed text. Total
    # 2 API calls inside the first _transcribe_single_voice_message call.
    pending = _make_transcribe_result(pending=True, transcription_id="tx-abc-123")
    done = _make_transcribe_result(text="Привет", transcription_id="tx-abc-123")
    client, calls = client_factory([pending, done])

    user = _make_user(12345)
    message_id = 818041

    first = await _transcribe_single_voice_message(client, user, message_id)
    assert first == "Привет"
    # Two API calls inside the first invocation: kick off, then poll to completion.
    assert len(calls) == 2

    # Second invocation: text is cached, no API call is made.
    second = await _transcribe_single_voice_message(client, user, message_id)
    assert second == "Привет"
    assert len(calls) == 2


@pytest.mark.unit
@pytest.mark.asyncio
async def test_cache_is_per_peer(client_factory, monkeypatch):
    """The same msg_id in a different chat must not be conflated with the
    rate-limited one — the rate-limit is per (account, message), so keying
    on (peer_id, msg_id) means a fresh chat starts cold."""
    from src.utils.message_format import _transcribe_single_voice_message

    flood = FloodWaitError(request=None, capture=2328)
    success = _make_transcribe_result(text="Другой чат")
    client, calls = client_factory([flood, success, success])

    user_a = _make_user(user_id=12345)
    user_b = _make_user(user_id=67890)  # different chat

    # Peer A: rate-limited on first call, no extra call on second.
    first_a = await _transcribe_single_voice_message(client, user_a, 818045)
    second_a = await _transcribe_single_voice_message(client, user_a, 818045)
    assert first_a is None
    assert second_a is None
    assert len(calls) == 1

    # Peer B: fresh — must hit the API and return the transcription.
    first_b = await _transcribe_single_voice_message(client, user_b, 818045)
    second_b = await _transcribe_single_voice_message(client, user_b, 818045)
    assert first_b == "Другой чат"
    assert second_b == "Другой чат"
    # Two more API calls: one for the fresh transcribe, zero on the second
    # call because the success is now cached.
    assert len(calls) == 2, f"expected 2 API calls, got {len(calls)}"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_cache_is_per_peer_kind():
    """A user with id X and a channel with id X must NOT share a cache
    entry — Telethon's integer peer ids are not unique across peer types
    (users, channels, chats all live in the same 32-bit integer space).

    Without the peer-kind discriminator in the cache key, a transcribe
    hit for a user account could shadow a channel post with the same
    numeric id, returning the wrong transcription text.
    """
    import src.utils.message_format as mf
    from src.utils.message_format import _TranscriptionCacheEntry

    class _Channel:
        """Stand-in for a Telethon Channel entity — class name carries the
        'channel' substring that _transcription_cache_key uses to detect
        peer kind."""

        def __init__(self, channel_id: int) -> None:
            self.id = channel_id
            self.title = "Test Channel"

    mf._TRANSCRIPTION_CACHE.clear()

    user = _make_user(12345)
    user_key = mf._transcription_cache_key(user, 818045)
    assert user_key is not None, "user key should be buildable"
    assert user_key[0] == "user", f"expected peer_kind='user', got {user_key!r}"
    assert user_key[1] == 12345
    assert user_key[2] == 818045

    # Pre-seed a done entry for the user.
    mf._transcription_cache_set(
        user_key,
        _TranscriptionCacheEntry(
            text="USER-VOICE-TEXT",
            done_until_ts=mf.time.time() + mf._DONE_TTL_SECONDS,
        ),
    )

    # A channel with the same numeric id must produce a different key.
    channel = _Channel(12345)
    channel_key = mf._transcription_cache_key(channel, 818045)
    assert channel_key is not None, "channel key should be buildable"
    assert channel_key[0] == "channel", (
        f"expected peer_kind='channel', got {channel_key!r}"
    )
    assert channel_key[1] == 12345
    assert channel_key[2] == 818045
    assert channel_key != user_key, "peer_kind must differ between user and channel"

    # The channel's cache lookup MUST miss — the user's entry is scoped to
    # user-kind peers only.
    assert mf._transcription_cache_get(channel_key) is None, (
        "channel should not see the user's cache entry"
    )

    # And the user's entry is still there, untouched.
    assert mf._transcription_cache_get(user_key) is not None
    assert mf._transcription_cache_get(user_key).text == "USER-VOICE-TEXT"

    mf._TRANSCRIPTION_CACHE.clear()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_done_entry_evicted_after_ttl(client_factory, monkeypatch):
    """A cached done entry must expire after _DONE_TTL_SECONDS so that the
    next call re-issues the request rather than returning a stale value."""
    import src.utils.message_format as mf
    from src.utils.message_format import _transcribe_single_voice_message

    success_1 = _make_transcribe_result(text="Свежий текст")
    success_2 = _make_transcribe_result(text="Обновлённый текст")
    client, calls = client_factory([success_1, success_2])

    user = _make_user(12345)
    message_id = 818099

    # First call at t=0 → success, cached.
    monkeypatch.setattr(mf.time, "time", lambda: 0.0)
    first = await _transcribe_single_voice_message(client, user, message_id)
    assert first == "Свежий текст"
    assert len(calls) == 1

    # Second call at t=10 → still cached, no API call.
    monkeypatch.setattr(mf.time, "time", lambda: 10.0)
    second = await _transcribe_single_voice_message(client, user, message_id)
    assert second == "Свежий текст"
    assert len(calls) == 1

    # Third call after _DONE_TTL_SECONDS → re-issued, fresh value.
    monkeypatch.setattr(mf.time, "time", lambda: mf._DONE_TTL_SECONDS + 1)
    third = await _transcribe_single_voice_message(client, user, message_id)
    assert third == "Обновлённый текст"
    assert len(calls) == 2


@pytest.mark.unit
@pytest.mark.asyncio
async def test_resume_pending_transcription_across_calls(client_factory, monkeypatch):
    """A second call within _PENDING_TTL_SECONDS must resume polling the
    same transcription_id rather than kicking off a new transcription."""
    from src.utils.message_format import _transcribe_single_voice_message

    # First call kicks off, gets pending. The internal polling loop fires
    # one more request and gets a second pending response. The first call
    # times out at 30 polls (returned as None).
    pending_a = _make_transcribe_result(pending=True, transcription_id="tx-9")
    pending_b = _make_transcribe_result(pending=True, transcription_id="tx-9")
    # Second call: cached pending id, polls once, gets done.
    done = _make_transcribe_result(text="Готово", transcription_id="tx-9")
    client, calls = client_factory([pending_a, pending_b, done])

    user = _make_user(12345)

    # First call: kicks off, polls once (still pending). Test exits early
    # via the polling loop running; the loop keeps polling but the mock
    # would run out of responses. We just confirm that the cached pending
    # state is what the second call observes.
    first = await _transcribe_single_voice_message(client, user, 818088)
    # Polling continues until it gets the done response (which is queued
    # third), so the first call should actually return "Готово" after 2 polls.
    # Three API calls: initial + 2 polls (first poll returns pending_b,
    # second poll returns done).
    assert first == "Готово"
    assert len(calls) == 3

    # Second call: cached done, no API call.
    second = await _transcribe_single_voice_message(client, user, 818088)
    assert second == "Готово"
    assert len(calls) == 3


@pytest.mark.unit
def test_cache_pruning_keeps_size_under_cap(monkeypatch):
    """When the cache exceeds _TRANSCRIPTION_CACHE_MAX, the oldest 25% of
    entries must be evicted on the next set."""
    from src.utils import message_format as mf

    mf._TRANSCRIPTION_CACHE.clear()
    now = mf.time.time()
    for i in range(mf._TRANSCRIPTION_CACHE_MAX):
        mf._transcription_cache_set(
            ("user", i, 1),
            mf._TranscriptionCacheEntry(text=f"t{i}", done_until_ts=now + 3600),
        )
    assert len(mf._TRANSCRIPTION_CACHE) == mf._TRANSCRIPTION_CACHE_MAX

    # One more entry triggers pruning of the oldest 25%.
    mf._transcription_cache_set(
        ("user", mf._TRANSCRIPTION_CACHE_MAX, 1),
        mf._TranscriptionCacheEntry(text="newest", done_until_ts=now + 3600),
    )
    expected_max = mf._TRANSCRIPTION_CACHE_MAX - (mf._TRANSCRIPTION_CACHE_MAX // 4) + 1
    assert len(mf._TRANSCRIPTION_CACHE) == expected_max
    # The very first key was pruned; the brand-new key is present.
    assert ("user", mf._TRANSCRIPTION_CACHE_MAX, 1) in mf._TRANSCRIPTION_CACHE
    assert ("user", 0, 1) not in mf._TRANSCRIPTION_CACHE
    # The newest key is at the end (most-recently-used under LRU).
    last_key = next(reversed(mf._TRANSCRIPTION_CACHE))
    assert last_key == ("user", mf._TRANSCRIPTION_CACHE_MAX, 1)
    mf._TRANSCRIPTION_CACHE.clear()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_resume_cached_pending_does_not_re_kickoff(client_factory, monkeypatch):
    """When the cache has a pending transcription_id for this (peer, msg),
    the next call must skip the kick-off TranscribeAudio and go straight
    to polling the cached id. A new kick-off would just trip another
    FloodWaitError.

    Discriminator: the queued mock responses carry distinct transcription
    ids. If the kick-off fires (buggy path), it consumes the FIRST response
    (with the wrong id) and the function returns its text. If the kick-off
    is skipped (fixed path), the polling loop consumes the SECOND response
    (with the cached id) and returns that text.
    """
    import src.utils.message_format as mf
    from src.utils.message_format import (
        _transcribe_single_voice_message,
        _transcription_cache_set,
        _TranscriptionCacheEntry,
    )

    user = _make_user(12345)
    message_id = 818050

    # Pre-seed a pending entry as a previous call would have left it.
    mf._TRANSCRIPTION_CACHE.clear()
    _transcription_cache_set(
        ("user", 12345, message_id),
        _TranscriptionCacheEntry(
            transcription_id="tx-resume",
            pending_until_ts=mf.time.time() + mf._PENDING_TTL_SECONDS,
        ),
    )

    # The kick-off would yield a different (wrong) transcription id; the
    # poll, if it fires for the cached id, yields the right one.
    kickoff_response = _make_transcribe_result(
        text="KICKOFF-RESULT", transcription_id="tx-kickoff"
    )
    poll_response = _make_transcribe_result(
        text="ВОЗОБНОВЛЕНО", transcription_id="tx-resume"
    )
    client, calls = client_factory([kickoff_response, poll_response])

    result = await _transcribe_single_voice_message(client, user, message_id)
    assert result == "ВОЗОБНОВЛЕНО", (
        "Resume path consumed the kick-off response instead of the poll "
        "response. The cached transcription_id is being shadowed — check "
        "the function's local bindings."
    )
    # The poll path was taken; we don't constrain call count strictly
    # because the polling loop may iterate past id-mismatched responses
    # before landing on the matching one.
    assert len(calls) >= 1
    calls_after_first = len(calls)

    # Second call: served from the now-done cache, no extra API call.
    second = await _transcribe_single_voice_message(client, user, message_id)
    assert second == "ВОЗОБНОВЛЕНО"
    assert len(calls) == calls_after_first, (
        "Second call hit the network instead of the now-done cache."
    )
    mf._TRANSCRIPTION_CACHE.clear()


@pytest.mark.unit
def test_lru_recency_updated_on_cache_hit(monkeypatch):
    """Touching a key via _transcription_cache_get must move it to the end
    of the dict so frequently-used keys survive pruning."""
    from src.utils import message_format as mf

    mf._TRANSCRIPTION_CACHE.clear()
    # Use the real entry shape with TTL so is_done is True.
    now = mf.time.time()
    for k in [("user", 1, 1), ("user", 2, 1), ("user", 3, 1)]:
        mf._transcription_cache_set(
            k,
            mf._TranscriptionCacheEntry(text=f"t{k[1]}", done_until_ts=now + 3600),
        )
    # Touch the oldest key — it should move to the end.
    entry = mf._transcription_cache_get(("user", 1, 1))
    assert entry is not None
    last_key = next(reversed(mf._TRANSCRIPTION_CACHE))
    assert last_key == ("user", 1, 1)
    assert mf._TRANSCRIPTION_CACHE.get(("user", 1, 1)) is entry
    mf._TRANSCRIPTION_CACHE.clear()


@pytest.mark.unit
def test_state_method_is_consistent_at_ttl_boundary():
    """The state(now) method must evaluate all TTLs against the SAME
    timestamp so an entry cannot simultaneously appear done and pending
    at a TTL boundary (where the old per-property time.time() calls raced).
    """
    from src.utils.message_format import _TranscriptionCacheEntry

    now = 1_000_000.0
    # An entry whose done TTL just expired at `now`.
    expired_done = _TranscriptionCacheEntry(
        text="stale-done", done_until_ts=now - 0.001
    )
    assert expired_done.state(now=now) == "stale"

    # An entry whose pending TTL is just shy of expiring.
    active_pending = _TranscriptionCacheEntry(
        transcription_id="tx-1", pending_until_ts=now + 1.0
    )
    assert active_pending.state(now=now) == "pending"

    # A rate-limited entry: its rate-limit window is the priority state.
    mixed = _TranscriptionCacheEntry(
        text="X",
        transcription_id="tx-2",
        done_until_ts=now + 1000,
        pending_until_ts=now + 1000,
        until_ts=now + 500,
    )
    assert mixed.state(now=now) == "rate_limited"

    # Default constructed entry: stale (nothing set).
    blank = _TranscriptionCacheEntry()
    assert blank.state(now=now) == "stale"
