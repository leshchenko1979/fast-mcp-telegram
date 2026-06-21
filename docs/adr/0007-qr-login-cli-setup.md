# ADR 0007: QR Login in CLI Setup

## Status

Proposed (v4 — hardened after third review round)

## Date

2026-06-18

## Context

The CLI setup (`fast-mcp-telegram-setup`) only supports phone + code + 2FA for user accounts, and bot token for bots. QR login exists in the web setup but is absent from the CLI. The competitor `overpod/mcp-telegram` uses QR-only authentication in their CLI — scan QR in terminal, done.

## Decision

### Decision 1: QR-First by Inference (No New Flags)

Auth method is inferred from existing flags:

- `--bot-api-token` present → bot token auth
- `--phone-number` present → phone + code auth
- Neither → QR login (default, recommended)

When no flags are passed, an interactive prompt offers all three (QR default). No new fields on `SetupConfig`, no new CLI args.

### Decision 2: Terminal QR + Raw URL (Two-Tier)

Render the QR code directly in the terminal using `qrcode.print_ascii(invert=True)`. Always print the raw `tg://login?token=...` URL below as a universal fallback.

```
█████████████████████████████
██ ▄▄▄▄▄ █▄█▀█▀█▄█ ▄▄▄▄▄ ██
██ █   █ █ ▄▀▀▄▄▀█ █   █ ██
...

Scan with Telegram: Settings → Devices → Link Desktop Device
Waiting for scan... (60s timeout)
  Or open: tg://login?token=AAAA...
```

No SVG, no PNG, no terminal width check, no encoding check. The URL is always printed — that's the fallback for every failure mode.

### Decision 3: Direct Telethon QR API (No QrLoginManager)

Three Telethon calls, no web abstraction layer:

```python
qr_login = await client.qr_login()       # generate QR
# render qr_login.url in terminal
await qr_login.wait()                     # blocks until scan; returns User
```

If QR expires, auto-regenerate with `await qr_login.recreate()`. Cap retries at 5 to prevent `FloodWaitError`.

### Decision 4: Temp SQLiteSession + Rename

Use a temporary `SQLiteSession` at a temp path during QR auth. On success, disconnect client, rename to final path. On failure or interrupt, clean up the temp file.

Critical implementation details (found in review):
- **No suffix on temp name**: `tempfile.mkstemp()` (no suffix). Telethon appends `.session` itself. If you add `suffix='.session'` to `mkstemp`, the rename target becomes `foo.session.session` — `FileNotFoundError`.
- **Disconnect before rename**: `await client.disconnect()` before `os.rename()`. SQLite holds an open file handle; renaming while connected corrupts the database.
- **Move sidecar files**: SQLite creates `-journal` and `-wal` sidecar files alongside the main `.session` file. These must be moved too.
- **Temp session path**: Place temp file in `session_dir` (same filesystem as final path) to ensure atomic `os.rename()`.

```python
fd, temp_path = tempfile.mkstemp(dir=session_dir)  # no suffix
os.close(fd)
os.unlink(temp_path)  # Telethon will create its own .session file at this base
try:
    client = TelegramClient(temp_path, api_id, api_hash, receive_updates=True)
    # ... QR auth ...
    await client.get_me()  # validate auth succeeded
    await client.disconnect()
    # Move .session and sidecar files
    for ext in ('', '-journal', '-wal'):
        src = f"{temp_path}.session{ext}"
        dst = f"{session_path}.session{ext}"
        if os.path.exists(src):
            os.rename(src, dst)
finally:
    _cleanup_temp_session(temp_path)
```

### Decision 5: `receive_updates=True`

The Telethon client **must** be created with `receive_updates=True`. QR login's `wait()` depends on the `UpdateLoginToken` server push — without it, `wait()` silently times out even if the user scanned the QR.

Note: `receive_updates=True` is already the default in Telethon 1.43.2+, but we set it explicitly as a safeguard against future default changes.

### Decision 6: 2FA After QR Scan

If the account has two-step verification, `wait()` raises `SessionPasswordNeededError`. Flow:
1. Get password hint via `client(GetPasswordRequest())`
2. Prompt via `getpass.getpass()`
3. Call `client.sign_in(password=password)`
4. Retry on `PasswordHashInvalidError` — up to 3 attempts, then fail

Reuse existing `_print_2fa_password_hint()`.

### Decision 7: Non-TTY Detection

Before any interactive prompt or QR rendering:

```python
if not sys.stdin.isatty():
    raise SystemExit("Non-interactive terminal. Use --bot-api-token for CI setup.")
```

Runs before the auth method prompt. CI users get an immediate actionable error.

### Decision 8: No New Dependencies

`qrcode` is already a project dependency. `print_ascii()` is built-in. `tempfile` and `os.rename` are stdlib.

## Consequences

### Positive

- ✅ Simpler UX — scan QR, done. No phone, no code, no waiting.
- ✅ Works over SSH — terminal QR rendering, no browser needed.
- ✅ Competitive parity — matches `overpod/mcp-telegram`'s QR CLI.
- ✅ No new dependencies, no new config fields, no new CLI flags.
- ✅ Minimal code — ~30-40 lines, one new async function.
- ✅ Backward compatible — existing `--phone-number` and `--bot-api-token` unchanged.

### Negative

- ⚠️ QR requires Telegram mobile — the `tg://` deep link only works from Telegram's mobile app.
- ⚠️ 2FA still requires keyboard — QR replaces phone + code, but 2FA password needs manual input.
- ⚠️ Terminal QR may wrap on narrow terminals — mitigated by URL fallback.

## Alternatives Considered

### `--auth-method` Flag

Dropped in favor of inference. `--bot-api-token` already implies bot auth; `--phone-number` already implies phone auth. Adding `--auth-method` creates a redundant flag that can conflict.

### SVG / PNG Fallback

Dropped. Two tiers is enough — terminal QR + raw URL. If the terminal can't render QR, the URL handles it.

### StringSession

Dropped. `StringSession` cannot persist to `.session` SQLite file — formats are incompatible. Temp `SQLiteSession` + rename is simpler and matches web_setup's pattern.

## References

- [ADR 0004](./0004-qr-login-auth.md) — QR Login Auth (web setup)
- [ADR 0008](./0008-auth-telemetry-events.md) — Auth telemetry events (instrumented CLI QR flow)
- [QrLoginManager](../../src/server_components/qr_login.py) — existing QR login module (web only, not used by CLI)
- [cli_setup.py](../../src/cli_setup.py) — current CLI setup
- [overpod/mcp-telegram](https://glama.ai/mcp/servers/mcp-telegram/mcp-telegram) — competitor's QR-only CLI approach
