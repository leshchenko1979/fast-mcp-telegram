# Telegram OIDC + MCP OAuth Setup Design

**Date:** 2026-04-19
**Status:** Draft

---

## Overview

Add Telegram as an OIDC Authorization Server, enabling OAuth-based login directly from MCP clients that support it (Claude Desktop, Cursor). The existing phone→code→2FA web flow is preserved as fallback.

**Single-instance deployment only** (v1). Multi-instance support is v2.

**Design decisions:**
- Our server serves OIDC discovery at `/.well-known/openid-configuration` on our host
- Discovery `issuer=https://tg-mcp.example.com`; `token_endpoint` and `jwks_uri` point to Telegram — this is a **known deviation** from strict OIDC issuer binding (documented in Deviations section)
- OAuth state is a **signed JWT** (stateless — no server-side storage needed)
- Each OIDC login creates a new independent session
- Max 10 sessions per Telegram user (oldest deleted on overflow)
- Telegram handles SMS/2FA brute-force protection on their end
- Client polls `/mcp` until auth completes; no mcp.json file needed

---

## Architecture

### Roles

| Component | Role |
|-----------|------|
| **Our server** (`tg-mcp.example.com`) | OIDC Resource Server + AS proxy |
| **Telegram** (`oauth.telegram.org`) | OIDC Authorization Server (issues id_tokens, hosts Login Widget) |
| **MCP Client** (Claude Desktop, etc.) | OIDC Relying Party |

### Discovery Document (served at `/.well-known/openid-configuration`)

```json
{
  "issuer": "https://tg-mcp.example.com",
  "authorization_endpoint": "https://tg-mcp.example.com/oauth/authorize",
  "token_endpoint": "https://oauth.telegram.org/token",
  "jwks_uri": "https://oauth.telegram.org/.well-known/jwks.json",
  "response_types_supported": ["code"],
  "subject_types_supported": ["public"],
  "id_token_signing_alg_values_supported": ["RS256"],
  "scopes_supported": ["openid", "profile", "phone"],
  "token_endpoint_auth_methods_supported": ["client_secret_post"]
}
```

### Known OIDC Deviations

| Field | In Our Discovery | In Telegram's id_token | Strict OIDC | Resolution |
|-------|-----------------|----------------------|------------|------------|
| `issuer` | `https://tg-mcp.example.com` | `https://oauth.telegram.org` | Must match | Known deviation. Clients must disable issuer binding check, or configure Telegram's AS URL directly. Document this. |
| `token_endpoint` | `https://oauth.telegram.org/token` | N/A | N/A | Points to Telegram directly — clients exchange code there. |

**For Claude Desktop / Cursor:** These MCP clients implement OAuth 2.1 with explicit `authorization_server` configuration. Set `authorization_server` to `https://oauth.telegram.org` directly, bypassing our discovery.

**For strict OIDC clients:** Our server's discovery can be used if the client disables issuer binding. This is an acceptable tradeoff for the simplified UX.

---

## Full End-to-End Flow

```
1. MCP Client → Our Server /mcp (no Bearer)
   Response: 401 Unauthorized
   Header:
     WWW-Authenticate: Bearer
       realm="mcp",
       resource_metadata="https://tg-mcp.example.com/.well-known/oauth-protected-resource",
       scope="openid profile phone"

   Client also STARTS POLLING /mcp with a session marker (e.g., ?pending_session=1)
   These requests return 202 Accepted until auth completes, then 200 with bearer token.

2. MCP Client opens browser → Our Server /oauth/authorize
   (this is the URL from WWW-Authenticate's authorization_server or from our discovery)
   Params: client_id, redirect_uri, scope, response_type, state (JWT), code_challenge, code_challenge_method
   Response: 302 Redirect to Telegram Login Widget

3. User authenticates in Telegram Login Widget (browser popup)
   Telegram may send SMS code if account not recently verified
   Telegram redirects to https://tg-mcp.example.com/oauth/callback?code=XXX&state=YYY

4. Our Server GET /oauth/callback?code=XXX&state=YYY
   a. Validate state JWT:
        - Signature valid (HMAC-SHA256 with STATE_SIGNING_KEY)
        - Not expired (max 10 min lifetime)
        - audience = BOT_ID
        - code_challenge and code_challenge_method stored in JWT
   b. POST https://oauth.telegram.org/token
        params: grant_type=authorization_code, code=XXX, redirect_uri,
                code_verifier, client_id=BOT_ID, client_secret=BOT_CLIENT_SECRET
   c. Validate returned id_token:
        - Fetch JWKS from https://oauth.telegram.org/.well-known/jwks.json (cached, 1hr TTL)
        - Verify RS256 signature against Telegram's public key
        - Verify iss = "https://oauth.telegram.org"
        - Verify aud = BOT_ID (string comparison)
        - Verify exp, iat (allow 30s clock skew)
        - Extract: sub (tg_user_id), phone_number, name, picture
   d. Generate bearer_token = random_urlsafe_base64(32)
   e. Create session file: {bearer_token}.session
   f. Attempt MTProto auth: client.sign_in(phone, code=None)
        - If session valid: DONE
        - If re-auth needed:
             i.   MCP Elicitation (via polling response): "Code sent to {masked_phone}"
             ii.  User enters code via MCP prompt
             iii. client.sign_in(phone, code)
                  - If SessionPasswordNeededError:
                       Fetch hint via GetPasswordRequest()
                       MCP Elicitation: "2FA. Password (hint: {hint}):"
                       client.sign_in(password=password)
             iv.  Session created
   g. Check session count for tg_user_id:
        - If >= 10 sessions: delete oldest by created_at
   h. Browser shows success page: "Authentication complete. Return to your MCP client."
   i. Client's next poll to /mcp receives 200 + bearer token in response body

5. MCP Client → Our Server /mcp (Authorization: Bearer {bearer_token})
   Server validates token, serves MCP tools
```

### Client Polling Mechanism

The MCP client polls `/mcp` while the browser OAuth flow is in progress:

```
Client → /mcp (no token, ?pending=true)
  → 202 Accepted (body: {"status": "pending", "message": "Complete authentication in browser"})
  → Client retries after 1s

After callback completes:
Client → /mcp (no token, ?pending=true)
  → 200 OK (body: {"status": "authenticated", "bearer_token": "xxx"})
  → Client stores bearer_token for subsequent requests
```

This avoids the need for URL-based token handoff. The client simply retries until it gets a 200.

---

## OAuth State: Signed JWT (Stateless)

The `state` parameter is a signed JWT (HS256). No server-side storage required. Any instance can validate.

**State JWT payload (at creation):**
```json
{
  "iss": "https://tg-mcp.example.com",
  "aud": "BOT_ID",
  "exp": 1745100000,
  "iat": 1745099400,
  "jti": "unique-id-for-this-flow",
  "code_challenge": "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM",
  "code_challenge_method": "S256",
  "redirect_uri": "https://tg-mcp.example.com/oauth/callback",
  "client_id": "BOT_ID",
  "pending_key": "session-marker-used-by-client-polling"
}
```

**Important:** No `tg_user_id` or `phone` in the state JWT — those are only available after Telegram validates the user and are not stored in the JWT (JWTs are immutable once signed).

**Signing key:** `STATE_SIGNING_KEY` env var (HMAC-SHA256 secret, at least 32 bytes).

---

## Session Creation and Storage

### Session File
```
session_directory/
  {bearer_token}.session    ← Telethon session file
```

### Sessions DB (local SQLite)
```sql
-- session_directory/sessions.db
CREATE TABLE sessions (
  bearer_token TEXT PRIMARY KEY,
  tg_user_id INTEGER NOT NULL,
  phone_e164 TEXT,
  created_at INTEGER NOT NULL,
  last_auth_at INTEGER NOT NULL,
  auth_method TEXT NOT NULL DEFAULT 'oidc',
  status TEXT NOT NULL DEFAULT 'active'  -- active | failed
);

CREATE INDEX idx_tg_user_id ON sessions(tg_user_id);
```

On callback: insert row, complete auth, update `status=active`.

---

## MCP Elicitation

The server responds to client polls with elicitation prompts:

### Step 1: Phone Code (via 202 poll response)
```
Server → Client poll (202 Accepted):
  {"status": "pending", "step": "phone_code", "masked_phone": "+1***5678", "prompt": "Telegram sent a code. Enter it."}

Client shows prompt to user → user enters code
Client → /mcp (POST, ?pending=true): {"code": "12345"}
  → If success: 200 + bearer_token
  → If wrong: 202 + {"step": "phone_code", "error": "Invalid code", "attempts_left": 4}
  → If SessionPasswordNeededError: 202 + step=2fa_password
```

### Step 2: 2FA Password
```
Server → Client poll (202 Accepted):
  {"status": "pending", "step": "2fa_password", "hint": "•••", "prompt": "2FA enabled. Enter password."}

Client → /mcp (POST, ?pending=true): {"password": "•••"}
  → If success: 200 + bearer_token
  → If wrong: 202 + {"step": "2fa_password", "error": "Invalid password", "attempts_left": 4}
```

**Brute-force protection:** Telegram handles SMS/2FA rate limiting. Our server tracks wrong attempts in-memory per pending session. After 5 wrong entries, the flow fails and the session is deleted.

**Code expiry:** Telegram codes expire ~5 min. If expired, server returns error and user restarts OIDC login.

---

## WWW-Authenticate Header (Exact Format)

```http
HTTP/1.1 401 Unauthorized
WWW-Authenticate: Bearer realm="mcp",
  resource_metadata="https://tg-mcp.example.com/.well-known/oauth-protected-resource",
  scope="openid profile phone"
```

**Protected Resource Metadata** (`/.well-known/oauth-protected-resource`):
```json
{
  "resource": "https://tg-mcp.example.com/mcp",
  "authorization_servers": ["https://oauth.telegram.org"],
  "scopes_supported": ["openid", "profile", "phone"]
}
```

Note: `authorization_servers` points to Telegram directly because that's where tokens are validated. Our server is the resource server only.

---

## OIDC Token Validation

```python
import json
import time
import httpx
import jwt
from functools import lru_cache

_jwks_cache: dict | None = None
_jwks_cache_time: float = 0
JWKS_CACHE_TTL = 3600  # 1 hour
CLOCK_SKEW = 30  # seconds

@lru_cache(maxsize=1)
def _fetch_telegram_jwks() -> dict:
    """Fetch and cache Telegram JWKS. Clears cache on kid-not-found."""
    response = httpx.get("https://oauth.telegram.org/.well-known/jwks.json", timeout=10)
    response.raise_for_status()
    return response.json()

def _get_jwks() -> dict:
    """Get JWKS with TTL-based caching."""
    global _jwks_cache, _jwks_cache_time
    if _jwks_cache is None or time.time() > _jwks_cache_time + JWKS_CACHE_TTL:
        _jwks_cache = _fetch_telegram_jwks()
        _jwks_cache_time = time.time()
    return _jwks_cache

def validate_telegram_id_token(id_token: str, bot_id: str) -> dict | None:
    """Validate Telegram OIDC id_token and return claims, or None if invalid."""
    try:
        header = jwt.get_unverified_header(id_token)
        kid = header.get("kid")
        if not kid:
            return None

        jwks = _get_jwks()
        key_data = next((k for k in jwks.get("keys", []) if k.get("kid") == kid), None)
        if not key_data:
            # Kid not in cache — refresh and try once
            _jwks_cache = _fetch_telegram_jwks()
            _jwks_cache_time = time.time()
            _fetch_telegram_jwks.cache_clear()
            key_data = next((k for k in _jwks_cache.get("keys", []) if k.get("kid") == kid), None)
            if not key_data:
                return None

        public_key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(key_data))
        claims = jwt.decode(
            id_token,
            public_key,
            algorithms=["RS256"],
            issuer="https://oauth.telegram.org",
            audience=bot_id,
            options={
                "verify_exp": True,
                "verify_iat": True,
                "verify_iss": True,
                "verify_aud": True,
                "require": ["sub", "iss", "aud", "exp", "iat"],
            },
            leeway=CLOCK_SKEW,
        )
        return claims
    except Exception:
        return None
```

**Validation requirements:**
1. `kid` header — must be present and found in JWKS
2. Signature — RS256 verified against Telegram's public key
3. `iss` — exactly `"https://oauth.telegram.org"`
4. `aud` — equals `BOT_ID` (string)
5. `exp` / `iat` — not expired, not future (30s leeway)
6. JWKS cached 1hr; on `kid` miss, fetch once more before failing

---

## Token Exchange (Exact Request)

```http
POST https://oauth.telegram.org/token
Content-Type: application/x-www-form-urlencoded

grant_type=authorization_code
&code=AUTH_CODE
&redirect_uri=https://tg-mcp.example.com/oauth/callback
&code_verifier=dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk
&client_id=123456789
&client_secret=BOT_CLIENT_SECRET
```

**Response:**
```json
{
  "access_token": "...",
  "id_token": "eyJhbGciOiJSUzI1NiIsInR5cCI...",
  "token_type": "Bearer",
  "expires_in": 3600
}
```

---

## Stale Session Cleanup

```
Background job: runs hourly
For each {token}.session in session_directory:
  1. Read Telethon session's last_check timestamp (from session SQLite)
  2. If last_check < now - SESSION_TTL_DAYS: delete file
  3. Delete corresponding row from sessions.db
```

**Telethon session fields:**
- `last_check` — updated on each API call; used as "last active" indicator
- `date_online` — set at creation; NOT used for cleanup (old but active sessions should survive)

**Race condition handling:**
- Cleanup skips sessions in `_session_cache` (currently in use)
- Failed deletions retried next cycle
- Log token prefix only (never log full token)

**Config:** `SESSION_TTL_DAYS=90` env var.

**Cache eviction (existing, unchanged):** `cleanup_idle_sessions()` evicts from in-memory cache after 30 min idle. Does NOT delete disk files.

---

## Max Sessions Per User

```
MAX_SESSIONS_PER_USER=10   # env var
```

On successful session creation:
```python
count = db.query("SELECT COUNT(*) FROM sessions WHERE tg_user_id = ?", tg_user_id)[0]
if count >= MAX_SESSIONS_PER_USER:
    oldest = db.query(
        "SELECT bearer_token FROM sessions WHERE tg_user_id = ? ORDER BY created_at ASC LIMIT 1",
        tg_user_id
    )[0]
    os.remove(session_dir / f"{oldest}.session")
    db.execute("DELETE FROM sessions WHERE bearer_token = ?", oldest)
```

---

## Error Handling Summary

| Error | Server response | Client action |
|-------|-----------------|---------------|
| Invalid state JWT | 400 + error | Restart OIDC flow |
| Token exchange fails | 502 + error | Retry from step 1 |
| id_token validation fails | 401 + error | Retry from step 1 |
| Wrong code (1-4x) | 202 + elicitation + attempts_left | User re-enters |
| Wrong code (5x) | 401 + "flow failed" | Restart OIDC flow |
| Wrong 2FA password (1-4x) | 202 + elicitation + attempts_left | User re-enters |
| Wrong 2FA password (5x) | 401 + "flow failed" | Restart OIDC flow |
| Code expired | 401 + "code expired" | Restart OIDC flow |
| Callback from wrong redirect_uri | 400 + error | Restart OIDC flow |

---

## Deployment Model (Single Instance)

- Single Python process
- State JWT validated locally with `STATE_SIGNING_KEY`
- Sessions DB is local SQLite at `session_directory/sessions.db`
- All cleanup jobs run in-process (existing `cleanup_loop()` in `server.py`)
- No external dependencies for auth state

**Limitations (v1 only):**
- Single-instance only (no horizontal scale)
- Sessions DB is local (file-based); restart mid-flow loses pending sessions
- If server restarts during OAuth flow, user must restart OIDC login

---

## Threat Model

| Threat | Mitigation |
|--------|-----------|
| Stolen bearer token | Full session access. Treat as password. |
| Replay of auth code | One-time use; exchanged immediately on callback. |
| CSRF on callback | State JWT signed with `STATE_SIGNING_KEY`; `redirect_uri` bound in JWT. |
| Session fixation | New random bearer token per OIDC login. |
| Brute force phone code | Telegram rate-limits SMS. Our side: 5 attempts, then fail. |
| JWT kid substitution | JWKS cached 1hr; refreshed on kid miss before failing. |
| Clock skew | 30s leeway on exp/iat validation. |
| `STATE_SIGNING_KEY` compromise | Game over — anyone can mint valid state. Rotate key immediately. |

---

## Backward Compatibility

- **Existing bearer tokens**: work unchanged (server looks up by token)
- **Non-OAuth MCP clients**: fall back to `/setup` web flow
- **Legacy sessions**: unchanged; `sessions.db` row created on first OIDC login
- **Web setup users**: phone→code→2FA flow unchanged

---

## Files to Create / Modify

| File | Changes |
|------|---------|
| `src/config/server_config.py` | Add `BOT_ID`, `BOT_CLIENT_SECRET`, `STATE_SIGNING_KEY`, `SESSION_TTL_DAYS`, `MAX_SESSIONS_PER_USER` |
| `src/server_components/oidc_auth.py` | New: discovery endpoint, authorize, callback, token exchange, id_token validation, client polling handler |
| `src/server_components/sessions_db.py` | New: sessions.db schema and CRUD |
| `src/server_components/mcp_elicitation.py` | New: phone code + 2FA password elicitation via 202 poll responses |
| `src/server_components/session_cleanup.py` | New: `cleanup_stale_session_files()` |
| `src/server_components/web_setup.py` | No changes (OIDC routes are separate from web setup routes) |
| `src/server.py` | Call `cleanup_stale_session_files()` in cleanup_loop; init sessions_db |
| `src/templates/setup.html` | Add "Login with Telegram" button |

---

## Implementation Order

1. **OIDC discovery**: `/.well-known/openid-configuration`, `/.well-known/oauth-protected-resource`
2. **State JWT**: sign and validate state JWT with code_challenge (HS256, `STATE_SIGNING_KEY`)
3. **Authorize endpoint**: generate state JWT, redirect to Telegram
4. **Callback endpoint**: validate state, exchange code with Telegram, validate id_token
5. **Client polling endpoint**: `POST /mcp?pending=true` returns 202 + pending status, or 200 + token
6. **Session creation**: generate token, create .session file + sessions.db row
7. **Elicitation**: phone code + 2FA password via 202 poll responses
8. **Max sessions**: count and evict oldest per tg_user_id
9. **Cleanup job**: `cleanup_stale_session_files()` with `last_check` field
10. **Setup page**: add OIDC login button
11. **End-to-end test** with real Telegram OIDC
