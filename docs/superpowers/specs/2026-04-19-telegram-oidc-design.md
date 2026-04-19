# Telegram OIDC + MCP OAuth Setup Design

**Date:** 2026-04-19
**Status:** Draft

---

## Overview

Add Telegram as an OIDC Authorization Server, enabling OAuth-based login directly from MCP clients that support it (Claude Desktop, Cursor). The existing phone→code→2FA web flow is preserved as fallback or for non-OAuth-capable clients.

**Design principle:** Each OIDC login creates a new session. No session reuse, no index.

**Goals:**
- Simplify UX: "Login with Telegram" button in OAuth-capable MCP clients
- One-click setup per MCP client (no phone → SMS → 2FA web forms)
- Preserve full 2FA support with password hint
- New users: OAuth → MCP elicitation for phone code → session created
- Returning users: If session valid, done; if expired, re-auth via OAuth + elicitation

---

## Architecture

### Auth Flow (OAuth-capable MCP client)

```
MCP Client → server /mcp (no Bearer)
  → 401 + WWW-Authenticate: Bearer
       resource_metadata="https://oauth.telegram.org/...",
       scope="openid profile phone"

MCP Client opens system browser → https://oauth.telegram.org/auth
  ?client_id=BOT_ID
  &redirect_uri=https://tg-mcp.example.com/oauth/callback
  &scope=openid profile phone
  &response_type=code
  &state=random_state
  &code_challenge=...
  &code_challenge_method=S256

User authenticates in Telegram Login Widget (browser)
  → Telegram may send SMS code if account not verified recently
  → Telegram redirects to https://tg-mcp.example.com/oauth/callback?code=XXX&state=YYY

Server exchanges code → id_token (JWT)
Server validates id_token using Telegram JWKS (https://oauth.telegram.org/.well-known/jwks.json):
  - Verify signature (oauth.telegram.org RS256 public key)
  - Verify iss = "https://oauth.telegram.org"
  - Verify aud = BOT_ID
  - Verify exp not expired
  - Extract: sub (tg_user_id), phone_number, name, picture, preferred_username

Generate new bearer token → create new {token}.session
  → If MTProto session valid: done immediately
  → If MTProto session needs re-auth:
       MCP Elicitation: "Telegram sent a verification code. Enter it below."
       User gets SMS → enters code via MCP prompt
       Server: client.sign_in(phone, code)
         → If SessionPasswordNeededError:
              Fetch hint via GetPasswordRequest()
              MCP Elicitation: "Enter your 2FA password (hint: {hint})"
              User enters password
              Server: client.sign_in(password=password)
         → On success: session created, return mcp.json
```

**Result:** User downloads `mcp.json` with bearer token, same as existing flow.

---

## Session Model — No Index

- **Session file name**: `{random_bearer_token}.session` (unchanged)
- **No index** — each OIDC login creates a new independent session
- **No reuse** — if user loses mcp.json, they re-auth via OIDC → new session
- **Per-client sessions** — each MCP client installation has its own session (no concurrent access)

**Why no index:**
- Simplicity: no stateful lookup table to manage
- No concurrent access risk: each session is single-writer
- No "which session should I use?" ambiguity
- Telethon sessions are designed for single-writer access

### Stale Session Cleanup

Each OIDC login creates a new `.session` file. To prevent unbounded disk growth from accumulated orphaned sessions:

```
Background cleanup job (runs hourly):
  For each {token}.session file in session_directory:
    If last_accessed > 90 days ago:
      Delete file and log cleanup
```

- Uses Telethon's session `date_online` / `last_check` timestamp for last-access
- Configurable TTL via `session_ttl_days` config (default: 90)
- Cleanup is conservative — logs deletions for debugging
- Applies to ALL session files, not just OIDC-created ones
- Already-cleaned sessions from `cleanup_idle_sessions()` (in-memory cache eviction) are not affected — only disk files are cleaned

---

## New Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/.well-known/openid-configuration` | GET | OIDC discovery (proxied from Telegram) |
| `/.well-known/jwks.json` | GET | Telegram's public keys for JWT validation |
| `/oauth/authorize` | GET | Redirect to Telegram Login Widget (MCP client redirect) |
| `/oauth/callback` | GET | Telegram redirects here with `code` and `state` |
| `/oauth/token` | POST | Exchange code for tokens (server-side token exchange with Telegram) |
| `/oauth/userinfo` | GET | Return user profile from validated session |

### Callback redirect_uri

The `redirect_uri` registered with Telegram must be a public HTTPS URL controlled by the server:
```
https://tg-mcp.example.com/oauth/callback
```

This is BotFather → Bot Settings → Web Login → Allowed URLs.

---

## MCP Elicitation Steps

When OIDC succeeds but MTProto session needs re-authentication:

### Step 1: Phone Code
```
Server → MCP Client (Elicitation):
  "Telegram sent a verification code to {masked_phone}.
   Enter the code to complete authentication."
  [text input prompt]
```

### Step 2: 2FA Password (if needed)
```
Server → MCP Client (Elicitation):
  "Two-factor authentication is enabled.
   Enter your password (hint: {password_hint})."
  [text input prompt, secure=true]
```

On failure: return error via MCP error response, client retries elicitation.

---

## Data Model Changes

### New config fields (ServerConfig)

```python
# Telegram OIDC credentials (from BotFather → Bot Settings → Web Login)
# Used ONLY for the OIDC authentication flow.
# NOT used for Telegram Bot API calls (which use BOT_TOKEN env var).
BOT_ID: str              # Telegram Bot ID (numeric string, e.g. "123456789")
BOT_CLIENT_SECRET: str   # OIDC client secret (from BotFather web login settings)
```

**Existing Telegram API credentials remain unchanged:**
```python
API_ID: int     # From my.telegram.org — for MTProto user sessions
API_HASH: str   # From my.telegram.org — for MTProto user sessions
```

### In-memory state (OIDC flow only)

```python
# _oidc_state_store: maps state param → OIDC callback context
# Stored only for the duration of the OAuth flow (minutes).
# Not persisted after session is created.
{
    "state": "random_state_value",
    "tg_user_id": 987654321,
    "phone_number": "+1234567890",
    "name": "John Doe",
    "picture": "https://...",
    "created_at": timestamp,
}
```

---

## OIDC Token Validation

```python
import jwt
import httpx

async def validate_telegram_id_token(id_token: str, bot_id: str) -> dict | None:
    """Validate Telegram OIDC id_token and return claims."""
    # Fetch Telegram's public keys (cached, refreshed periodically)
    jwks = await fetch_telegram_jwks()  # GET https://oauth.telegram.org/.well-known/jwks.json

    # Decode header to get kid
    header = jwt.get_unverified_header(id_token)
    key = find_key_by_kid(jwks, header["kid"])

    # Verify
    claims = jwt.decode(
        id_token,
        key,
        algorithms=["RS256"],
        issuer="https://oauth.telegram.org",
        audience=bot_id,
    )
    return claims
```

---

## Two Auth Paths (Server Decision)

```
Request arrives (no Bearer token)
│
├─ Is MCP client OAuth-capable? (capabilities in MCP hello)
│   ├─ YES → Return 401 + WWW-Authenticate with Telegram OAuth metadata
│   │         Client redirects to Telegram → OIDC flow → new session
│   │
│   └─ NO → Fall back to existing /setup web flow
             (browser-based manual auth)
```

---

## Backward Compatibility

- **Existing bearer tokens**: continue working (server validates and finds session by token)
- **Non-OAuth MCP clients**: fall back to `/setup` web flow
- **Legacy sessions**: `token.session` continues to work unchanged
- **Web setup users**: phone→code→2FA flow unchanged

---

## Security Considerations

1. **JWT validation**: Always verify Telegram's `id_token` signature using Telegram's JWKS
2. **state parameter**: CSRF protection — random state validated on callback
3. **PKCE**: Telegram OIDC supports S256 — use it for authorization code flow
4. **Short-lived code exchange**: Authorization code exchanged immediately, not stored long-term
5. **Per-client sessions**: No shared state between MCP client installations
6. **2FA password elicitation**: Use `secure=true` in MCP elicitation to mask input

---

## New Dependencies

```python
# For JWT validation (already in Telethon deps)
PyJWT[cryptography]

# For HTTP OIDC calls to Telegram
httpx
```

---

## Files to Modify / Create

| File | Changes |
|------|---------|
| `src/config/server_config.py` | Add `BOT_ID`, `BOT_CLIENT_SECRET`, `session_ttl_days` fields |
| `src/server_components/oidc_auth.py` | New: OIDC validation, routes, Telegram JWT verification |
| `src/server_components/mcp_elicitation.py` | New: phone code + 2FA password elicitation handlers |
| `src/server_components/session_cleanup.py` | New: `cleanup_stale_session_files()` — disk-based TTL cleanup |
| `src/server_components/web_setup.py` | Add OIDC routes (`/oauth/*`, `/.well-known/*`) |
| `src/server.py` | Call `cleanup_stale_session_files()` in cleanup_loop |
| `src/templates/setup.html` | Add "Login with Telegram" button (OAuth path) |

---

## Implementation Order

1. **OIDC proxy endpoints**: `/.well-known/openid-configuration`, `/.well-known/jwks.json`
2. **OAuth callback handler**: `/oauth/callback` — validates Telegram JWT, extracts user info
3. **Bearer token + session creation**: Generate token, create session file
4. **MCP elicitation for phone code**: Replace web form with MCP prompt
5. **2FA password elicitation**: With hint from `GetPasswordRequest()`
6. **OAuth-capable client detection**: Return 401 + WWW-Authenticate with Telegram OAuth metadata
7. **Update `/setup` page**: Add OIDC login button as primary option
