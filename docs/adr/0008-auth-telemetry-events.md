# ADR 0008: Auth Telemetry Events

**Status:** accepted
**Date:** 2026-06-19
**Deciders:** Alexey, Case

## Context

Zero visibility into authorization flows. When a user runs `fast-mcp-telegram setup` (CLI) or interacts with the web setup UI, we don't know:
- If auth succeeded or failed
- What error they hit
- Which code path was used (phone, QR, bot token)
- How long the process took
- If they abandoned mid-flow

This is critical because auth is the #1 support burden — "I can't connect my bot" is the most common user complaint, and we have zero telemetry to diagnose it.

Auth events happen **before the server is fully operational** — the heartbeat (ADR 0005) only fires from a running, configured server. If auth fails, there's no heartbeat. We need a separate mechanism.

### Auth Flows

Four authorization paths exist in the codebase:

| Flow | Code | Description |
|------|------|-------------|
| Phone + code | `web_setup.py`, `cli_setup.py` | User provides phone number, receives SMS code, enters it |
| QR login | `web_setup.py`, `cli_setup.py` | User scans QR code with Telegram app |
| Bot token | `cli_setup.py` only | User provides bot token from BotFather |
| Reauthorize | `web_setup.py` only | Re-auth an existing session (e.g., after session file corruption) |

Each flow can branch into 2FA if the user has two-factor authentication enabled.

## Decision

**Buffered event-based auth telemetry.** Events accumulate in a list during the auth flow. A single HTTP POST sends all events on flow completion (success or failure). Same endpoint (`/v1/event`), same PostgreSQL table (JSONB), same retention.

### Why Buffered (Not Fire-and-Forget)

Fire-and-forget (one HTTP POST per event) was considered and rejected:
- **Bearer check telemetry was dropped entirely** — it runs on every tool call (high frequency, low signal), and there's no natural flow boundary to buffer against
- **No cooldown needed** — the cooldown mechanism had a `time.monotonic()` bug on fresh CI runners (monotonic time < cooldown window). Buffering eliminates this entirely
- **Single HTTP request per flow** — instead of 2-4 individual requests, one batched POST
- **Coherent event sequences** — the collector receives the complete flow (started → completed) as one payload

### Why Not Piggyback on Heartbeat

- Auth events happen before the server is operational. No heartbeat if auth fails.
- Auth flows are short-lived (seconds to minutes). Heartbeat interval is 6 hours.
- Buffer flush on completion gives immediate delivery without individual HTTP requests.

### Design

**Flow ID:** Each auth flow gets a UUID (`flow_id`) generated when the flow starts. All events in that flow carry the same `flow_id`. This is critical for concurrent users — multiple users logging in simultaneously on the same server have separate `flow_id`s, so the collector can group events per-flow and detect incomplete flows.

- **Web setup:** `flow_id` stored as a custom attribute on the Telethon client object. Each HTTP request handler reads it from the client. Buffer lives in a module-level dict keyed by `flow_id`.
- **CLI setup:** `flow_id` is a local variable. One flow per function call. Buffer is local.

**Event buffer:** A list of `dict[str, Any]` that accumulates during the auth flow. Each event has `ts` (unix seconds), `event` (the atomic event name), and `flow_id`. Optional `error` field when the event failed. Buffers are keyed by `flow_id` — each concurrent flow has its own buffer.

**Flush triggers:**
- Auth flow completed (session established) → flush that flow's buffer immediately
- Auth flow failed (error event) → flush that flow's buffer immediately
- Auth flow abandoned (QR expired, precondition failure) → flush that flow's buffer immediately

**Fire-and-forget:** The flush function spawns a daemon thread for the HTTP POST, matching the existing `send_heartbeat()` pattern. Never blocks the auth flow.

**No bearer check tracking:** Bearer token checks (`require_auth` decorator) run on every tool call. There's no natural flow boundary, and the signal-to-noise ratio is too low. If bearer auth is needed, it should be a separate heartbeat metric, not individual events.

### Event Model

```json
{
  "type": "auth",
  "iid": "a1b2c3d4-...",
  "flow_id": "f7e8d9c0-...",
  "ts": 1718030000,
  "ver": "0.38.0",
  "method": "qr",
  "branch": "qr_scan",
  "events": [
    {"ts": 1718030000, "event": "qr_session_created", "flow_id": "f7e8d9c0-..."},
    {"ts": 1718030002, "event": "user_scanned_qr", "flow_id": "f7e8d9c0-..."},
    {"ts": 1718030003, "event": "qr_login_confirmed", "flow_id": "f7e8d9c0-..."},
    {"ts": 1718030005, "event": "password_validated", "flow_id": "f7e8d9c0-..."},
    {"ts": 1718030006, "event": "session_established", "flow_id": "f7e8d9c0-...", "duration_ms": 6000}
  ]
}
```

The `events` array contains all atomic events from one auth flow. Each event is a single action by either the user or the system. The top-level `method` and `branch` identify the flow. The `flow_id` (UUID) groups events from the same flow — critical for concurrent users. Each concurrent auth flow has a unique `flow_id`, so the collector can reconstruct individual flows even when multiple users are logging in simultaneously.

### Atomic Events

Each event represents a single, indivisible action. Three categories: **user actions** (what the user did), **system actions** (what the system did), and **errors** (what went wrong).

#### User Actions

| Event | User action | Found in |
|-------|------------|----------|
| `user_submitted_phone` | Entered phone number | web_setup, cli_setup |
| `user_submitted_code` | Entered SMS code | web_setup, cli_setup |
| `user_submitted_password` | Entered 2FA password | web_setup, cli_setup |
| `user_scanned_qr` | Scanned QR code with Telegram app | web_setup, cli_setup |
| `user_reloaded_qr` | Requested new QR code after expiry | web_setup |
| `user_submitted_bot_token` | Pasted bot token from BotFather | cli_setup |
| `reauth_initiated` | Clicked reauthorize | web_setup |

#### System Actions

| Event | System action | Found in |
|-------|--------------|----------|
| `code_requested` | Sent code request to Telegram | web_setup, cli_setup |
| `code_validated` | Validated the SMS code | web_setup, cli_setup |
| `password_validated` | Validated 2FA password | web_setup, cli_setup |
| `qr_session_created` | Created QR login session | web_setup, cli_setup |
| `qr_login_confirmed` | Received QR scan confirmation | web_setup, cli_setup |
| `qr_expired` | QR code timed out (no scan) | web_setup, cli_setup |
| `session_established` | Auth session established | web_setup, cli_setup |
| `cleanup_completed` | Cleaned up stale sessions | web_setup |

#### Errors

Errors are carried as `error` fields on the event that failed. They are not separate events.

| Error | Exception | Meaning |
|-------|-----------|---------|
| `invalid_code` | `PhoneCodeInvalidError` | Wrong SMS code entered |
| `code_expired` | `PhoneCodeExpiredError` | SMS code expired (took too long) |
| `2fa_wrong_password` | `PasswordHashInvalidError` | Wrong 2FA password |
| `flood_wait` | `FloodWaitError` | Telegram rate limit |
| `phone_banned` | `PhoneNumberBannedError` | Phone number banned by Telegram |
| `phone_invalid` | `PhoneNumberInvalidError` | Invalid phone number format |
| `phone_unoccupied` | `PhoneNumberUnoccupiedError` | Phone number not registered on Telegram |
| `connect_failed` | `ConnectionError` | Can't reach Telegram servers |
| `timeout` | `TimeoutError`/`OSError` | Connection timeout |
| `reauth_password_required` | precondition | 2FA password not stored, can't reauth |
| `qr_session_error` | various | QR session creation failed |
| `already_authorized` | `UserAlreadyParticipantError` | Session already authorized |

### Methods

| Method | Where | Description |
|--------|-------|-------------|
| `phone` | web_setup, cli_setup | Phone number + SMS code |
| `qr` | web_setup, cli_setup | QR code scan |
| `bot` | cli_setup only | Bot token from BotFather |
| `reauth` | web_setup only | Re-authorize existing session |

### Branch Tags

| Branch | Method | Where | Description |
|--------|--------|-------|-------------|
| `phone_code` | phone | web_setup, cli_setup | Waiting for SMS code |
| `phone_2fa` | phone | web_setup, cli_setup | 2FA password needed after code |
| `qr_scan` | qr | web_setup, cli_setup | Waiting for QR scan |
| `qr_2fa` | qr | web_setup, cli_setup | 2FA password needed after QR |
| `bot_token` | bot | cli_setup | Bot token auth |
| `reauth_code` | reauth | web_setup | Reauth, sending code |
| `reauth_2fa` | reauth | web_setup | Reauth, 2FA password needed |

### Instrumentation Points

Each instrumentation point fires atomic events — user actions and system actions. Errors are attached to the event that failed.

#### web_setup.py

| Route | Events fired |
|-------|-------------|
| `POST /setup/phone` | `user_submitted_phone`, `code_requested` |
| `POST /setup/verify` | `user_submitted_code`, then `code_validated` or `code_validated(error=invalid_code)` or `code_validated(error=code_expired)` |
| If 2FA needed | `user_submitted_password`, then `password_validated` or `password_validated(error=2fa_wrong_password)` |
| `POST /setup/qr` | `qr_session_created` |
| `GET /setup/qr/status` | `user_scanned_qr` + `qr_login_confirmed` on success; `qr_expired` on timeout; `user_submitted_password` + `password_validated` on 2FA |
| `POST /setup/qr/2fa` | `user_submitted_password`, then `password_validated` or `password_validated(error=2fa_wrong_password)` |
| `POST /setup/reauth` | `reauth_initiated`, then `code_requested` (reauth_code) or `error=reauth_password_required`; if 2FA: `user_submitted_password` + `password_validated` |
| Final success | `session_established` (always last event on success) |

#### cli_setup.py

| Function | Events fired |
|----------|-------------|
| `setup_telegram_session` (phone) | `user_submitted_phone`, `code_requested`, `user_submitted_code`, `code_validated`; if 2FA: `user_submitted_password`, `password_validated`; final: `session_established` |
| `setup_telegram_session` (bot) | `user_submitted_bot_token`, `session_established` |
| `_qr_login_flow` | `qr_session_created`, `user_scanned_qr`, `qr_login_confirmed`; if 2FA: `user_submitted_password`, `password_validated`; final: `session_established` |
| `_wait_for_qr_scan` (timeout) | `qr_expired`, then `qr_session_created` (auto-recreate) |

### Collector Changes

**Same endpoint, same table.** The `type: "auth"` field discriminates auth events from heartbeats (ADR 0005) and abuse reports (ADR 0006). No schema migration needed — JSONB handles the nested `events` array.

`collector/app/auth_models.py` — new `AuthPayload` dataclass with validation. `collector/app/services.py` — type discrimination in `process_event()`. `collector/app/database.py` — `PgStorage.store()` accepts `TelemetryPayload | AuthPayload`.

## Consequences

**Positive:**
- First-ever visibility into auth flows
- Can detect: exceptions, abandoned flows, slow auth, which code path was used
- Same infrastructure as existing telemetry (endpoint, table, retention)
- No new dependencies
- Buffered flush: single HTTP request per flow, no cooldown bugs
- Fire-and-forget flush: never blocks auth

**Negative:**
- Auth events lost if process is killed before flush (SIGKILL, OOM)
- No bearer check telemetry (dropped due to high frequency, low signal)
- No real-time per-event streaming (events arrive as a batch on flow completion)

## References

- [ADR 0005: Anonymous Tool Telemetry](./0005-anonymous-tool-telemetry.md) — heartbeat telemetry (same endpoint, same table)
- [ADR 0004: QR Login Auth](./0004-qr-login-auth.md) — QR login flow instrumented by this ADR
- [ADR 0006: Abuse Prevention](./0006-abuse-prevention.md) — same endpoint, same rate limiting
- [ADR 0007: QR Login CLI Setup](./0007-qr-login-cli-setup.md) — CLI QR flow instrumented by this ADR
