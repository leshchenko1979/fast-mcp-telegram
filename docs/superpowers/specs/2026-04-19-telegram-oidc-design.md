# Telegram OIDC + MCP OAuth Setup Design

**Date:** 2026-04-19
**Status:** Draft

---

## Overview

Add Telegram as an OIDC Authorization Server, enabling OAuth-based login directly from MCP clients that support it (Claude Desktop, Cursor). The existing phone→code→2FA web flow is preserved as fallback.

**Design decisions:**
- Our server **proxies** Telegram's OIDC discovery at `/.well-known/openid-configuration` on our host
- Clients discover our server as the AS; our server redirects to Telegram Login Widget
- OAuth state is a **signed JWT** (stateless, multi-instance safe — no in-memory store)
- Each OIDC login creates a new independent session (no index, no reuse)
- Max 10 sessions per Telegram user (oldest deleted on overflow)
- Telegram handles SMS/2FA brute-force protection on their end

---

## Architecture

### Roles

| Component | Role |
|-----------|------|
| **Our server** (`tg-mcp.example.com`) | OIDC Resource Server + Authorization Server proxy |
| **Telegram** (`oauth.telegram.org`) | OIDC Authorization Server (issues id_tokens, hosts Login Widget) |
| **MCP Client** (Claude Desktop, etc.) | OIDC Relying Party / OAuth client |

### Discovery Document (served at `/.well-known/openid-configuration`)

Our server fetches and proxies Telegram's discovery, modifying `authorization_endpoint` to point through our server (for CSRF protection):

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
  "token_endpoint_auth_methods_supported": ["client_secret_post", "client_secret_basic"]
}
```

Note: `token_endpoint` and `jwks_uri` point to Telegram directly — only `authorization_endpoint` is proxied through our server.

### Full End-to-End Flow

```
1. MCP Client → Our Server /mcp (no Bearer)
   Response: 401 Unauthorized
   Header:
     WWW-Authenticate: Bearer
       realm="mcp",
       resource_metadata="https://tg-mcp.example.com/.well-known/oauth-protected-resource",
       scope="openid profile phone"

2. MCP Client → Our Server GET /oauth/authorize
   Params: client_id, redirect_uri, scope, response_type, state (JWT), code_challenge, code_challenge_method
   Response: 302 Redirect to Telegram Login Widget

3. User authenticates in Telegram Login Widget (browser popup)
   Telegram may send SMS code if account not recently verified
   Telegram redirects to https://tg-mcp.example.com/oauth/callback?code=XXX&state=YYY

4. Our Server GET /oauth/callback?code=XXX&state=YYY
   a. Validate state JWT:
        - Signature valid (our server's signing key)
        - Not expired (max 10 min lifetime)
        - audience = BOT_ID
        - code_challenge stored in state JWT
   b. POST https://oauth.telegram.org/token
        params: grant_type=authorization_code, code=XXX, redirect_uri, code_verifier (derived from code_challenge), client_id=BOT_ID, client_secret=BOT_CLIENT_SECRET
   c. Validate returned id_token:
        - Fetch JWKS from https://oauth.telegram.org/.well-known/jwks.json (cached, 1hr TTL, invalidate on kid miss)
        - Verify RS256 signature
        - Verify iss = "https://oauth.telegram.org"
        - Verify aud = BOT_ID (as string)
        - Verify exp, iat (allow 30s clock skew)
        - Extract: sub (tg_user_id), phone_number, name, picture
   d. Generate bearer_token = random_urlsafe_base64(32)
   e. Create session file: {bearer_token}.session
   f. Attempt MTProto auth: client.sign_in(phone, code=None)
        - If session valid (already authorized): DONE → return token to client
        - If re-auth needed:
             i.   MCP Elicitation: "Telegram sent a verification code to {masked_phone}. Enter it."
             ii.  User gets SMS → enters code
             iii. client.sign_in(phone, code)
                  - If SessionPasswordNeededError:
                       Fetch hint via GetPasswordRequest()
                       MCP Elicitation: "2FA enabled. Password (hint: {hint}):"
                       client.sign_in(password=password)
             iv.  Session created → return token to client
   g. Check session count for tg_user_id:
        - If >= 10 sessions exist for this tg_user_id: delete oldest by creation time
   h. Write session to shared DB (for multi-instance: callback writes, initiator reads)
   i. Return mcp.json to user

5. MCP Client → Our Server /mcp (Authorization: Bearer {bearer_token})
   Server validates token, serves MCP tools
```

---

## OAuth State: Signed JWT (Stateless)

The `state` parameter is a signed JWT (HS256), not an opaque random string. This eliminates server-side state storage and works across multiple instances.

**State JWT payload:**
```json
{
  "iss": "https://tg-mcp.example.com",
  "aud": "BOT_ID",
  "exp": 1745100000,          // max 10 min from creation
  "iat": 1745099400,
  "tg_user_id": null,         // null at creation — filled on callback
  "code_challenge": "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM",
  "code_challenge_method": "S256",
  "redirect_uri": "https://tg-mcp.example.com/oauth/callback",
  "client_id": "BOT_ID"
}
```

**Why no phone_number in state JWT at creation:** Phone is only available after Telegram authenticates the user. Storing it before validation leaks data to the callback handler before we've confirmed Telegram's signature.

**Signing key:** `state_signing_key` env var (HMAC-SHA256 secret). Same key on all instances.

**Multi-instance behavior:** Any instance can validate the state JWT. On callback, the receiving instance writes session info to shared DB (see below).

---

## Session Creation and Storage

### Session File
```
session_directory/
  {bearer_token}.session    ← Telethon session file
```

### Shared DB (for multi-instance coordination)
```python
# Shared SQLite at session_directory/sessions.db
CREATE TABLE sessions (
  bearer_token TEXT PRIMARY KEY,
  tg_user_id INTEGER NOT NULL,
  phone_e164 TEXT,           -- normalized, may be null if not yet complete
  created_at INTEGER NOT NULL,    -- unix timestamp
  last_auth_at INTEGER NOT NULL,
  auth_method TEXT NOT NULL DEFAULT 'oidc',
  status TEXT NOT NULL DEFAULT 'pending',  -- pending | active | failed
  instance_id TEXT          -- which instance created it (for debugging)
);

CREATE INDEX idx_tg_user_id ON sessions(tg_user_id);
```

**On callback (any instance):**
1. Insert session record with `status=pending`
2. Complete MTProto auth
3. Update `status=active`, `phone_e164`, `last_auth_at`
4. Other instances see the new session on next DB read

### Max Sessions Per User
```
MAX_SESSIONS_PER_USER=10   # env var, configurable
```
On new session creation: count sessions for `tg_user_id`. If count >= MAX_SESSIONS_PER_USER, delete oldest by `created_at`.

---

## MCP Elicitation

### Step 1: Phone Code
```
Server → MCP Client (Elicitation):
  prompt: "Telegram sent a verification code to {masked_phone}."
  [text input, required=true]
  timeout: 120 seconds

On code entry:
  client.sign_in(phone, code)
    → success: session complete
    → SessionPasswordNeededError: → Step 2
    → Exception: return error to client, client retries elicitation
```

### Step 2: 2FA Password (if needed)
```
Server → MCP Client (Elicitation):
  prompt: "Two-factor authentication is enabled. Password (hint: {hint}):"
  [text input, required=true, secure=true]
  timeout: 120 seconds

On password entry:
  client.sign_in(password=password)
    → success: session complete
    → PasswordHashInvalidError: return error, client retries
```

**Brute-force protection:** Telegram handles rate-limiting on their SMS/2FA delivery. Our server tracks attempt count per OIDC flow in-memory (not persisted — a restart just resets). After 5 wrong entries, the flow fails and user must restart OIDC login.

**Code expiry:** Telegram codes are short-lived (~5 min). If expired, return error and user restarts OIDC.

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
  "authorization_servers": ["https://tg-mcp.example.com"],
  "scopes_supported": ["openid", "profile", "phone"]
}
```

---

## OIDC Token Validation (Complete)

```python
import jwt
import httpx
from functools import lru_cache
from datetime import datetime, timezone

_jwks_cache: dict | None = None
_jwks_cache_ttl: float = 0
JWKS_CACHE_TTL_SECONDS = 3600  # 1 hour
CLOCK_SKEW_SECONDS = 30

@lru_cache(maxsize=1)
def _get_jwks() -> dict:
    """Fetch and cache Telegram JWKS. Invalidated on kid not found."""
    global _jwks_cache, _jwks_cache_ttl
    import time
    if _jwks_cache is None or time.time() > _jwks_cache_ttl:
        response = httpx.get("https://oauth.telegram.org/.well-known/jwks.json", timeout=10)
        response.raise_for_status()
        _jwks_cache = response.json()
        _jwks_cache_ttl = time.time() + JWKS_CACHE_TTL_SECONDS
    return _jwks_cache

def find_key(jwks: dict, kid: str):
    """Find key by kid in JWKS. Returns None if not found."""
    for key in jwks.get("keys", []):
        if key.get("kid") == kid:
            return key
    return None

def validate_telegram_id_token(id_token: str, bot_id: str) -> dict | None:
    """Validate Telegram OIDC id_token and return claims."""
    try:
        # Decode header to get kid (no verification yet)
        header = jwt.get_unverified_header(id_token)
        kid = header.get("kid")
        if not kid:
            return None

        # Fetch JWKS (cached, invalidated if kid not found)
        jwks = _get_jwks()
        key_data = find_key(jwks, kid)
        if not key_data:
            # Kid not found — refresh JWKS and try once more
            _get_jwks.cache_clear()
            jwks = _get_jwks()
            key_data = find_key(jwks, kid)
            if not key_data:
                return None

        # Build public key from JWK
        public_key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(key_data))

        # Verify and decode
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
            leeway=CLOCK_SKEW_SECONDS,
        )
        return claims
    except Exception:
        return None
```

**JWT validation requirements:**
1. `kid` header — must be present and found in JWKS
2. Signature — RS256, verified against Telegram's public key
3. `iss` — must be exactly `"https://oauth.telegram.org"`
4. `aud` — must equal `BOT_ID` (string comparison)
5. `exp` — not expired (allow 30s clock skew)
6. `iat` — not in the future (allow 30s clock skew)
7. JWKS cache TTL: 1 hour; on `kid` miss, immediate refresh before failing

---

## Token Exchange (Exact Request)

```http
POST https://oauth.telegram.org/token
Content-Type: application/x-www-form-urlencoded

grant_type=authorization_code
&code=AUTH_CODE_FROM_CALLBACK
&redirect_uri=https://tg-mcp.example.com/oauth/callback
&code_verifier=dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk
&client_id=123456789
&client_secret=telegram_bot_client_secret_from_botfather
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

`BOT_CLIENT_SECRET` never leaves our server. PKCE `code_verifier` is generated at authorization start, stored in the state JWT, and used here.

---

## Stale Session Cleanup

### Disk File Cleanup (separate from in-memory cache eviction)

```
Background job: runs hourly
For each {token}.session in session_directory:
  1. Open session SQLite (read date_online, last_check)
  2. If last_check < now - 90 days: delete file
  3. Also delete corresponding row from sessions.db
```

**Telethon session fields used:**
- `last_check` — updated on each successful API call (active use indicator)
- `date_online` — set when session first created

Using `last_check` (not `date_online`) because an actively-used session shouldn't be deleted even if old.

**Race condition handling:**
- Cleanup skips sessions that are currently in the active in-memory cache (`_session_cache`)
- If deletion fails due to file lock, retry on next cleanup cycle
- Deletion is logged with token prefix (not full token — security)

**Config:**
```
SESSION_TTL_DAYS=90   # env var
```

### Cache Eviction (existing behavior, unchanged)
`cleanup_idle_sessions()` evicts from in-memory cache after 30 min idle. It does NOT delete disk files.

---

## Max Sessions Per User (Enforcement)

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
    delete_session(oldest)   # delete file + db row
```

This prevents unbounded session accumulation per user while allowing legitimate multi-device use.

---

## Error Handling Summary

| Error | Server behavior | Client behavior |
|-------|----------------|-----------------|
| Invalid state JWT | 400 + error | Retry from step 1 |
| Token exchange fails | 502 + error | Retry from step 1 |
| id_token validation fails | 401 + error | Retry from step 1 |
| Wrong phone code (1-4x) | Elicit retry | User enters code |
| Wrong phone code (5x) | Flow fails, delete pending session | Restart OIDC login |
| Wrong 2FA password | Elicit retry | User enters password |
| SessionPasswordNeededError after code | Elicit 2FA password | User enters password |
| MTProto network error | Elicit retry | User retries |
| Callback from wrong redirect_uri | 400 + error | Restart OIDC login |

---

## Deployment Model

### Single Instance
- No special considerations
- State JWT validated locally
- Shared DB is local SQLite
- Callback instance = all instances (trivially)

### Multiple Instances (Horizontal Scale)
- State JWT signed with shared HMAC key (`STATE_SIGNING_KEY` env var — same on all instances)
- Shared DB: SQLite at shared path (NFS mount) OR migrate to shared DB (Postgres/Mysql) in future
- Callback can hit any instance — instance writes to shared DB
- Active sessions tracked in per-instance in-memory cache — evicted on idle (unchanged behavior)

**Sticky sessions NOT required:** Because state JWT is stateless and session write is to shared DB.

**Current limitation:** For v1, deploy as single instance or with shared filesystem for SQLite. Multi-instance with truly shared DB is v2.

---

## Threat Model

| Threat | Mitigation |
|--------|-----------|
| Stolen `mcp.json` | Bearer token gives full session access. Treat as password. Server does not track device. |
| Replay of authorization code | One-time use. Telegram's code is exchanged immediately. |
| CSRF on callback (state mismatch) | State JWT includes `redirect_uri` and is signature-validated. |
| Session fixation | New random bearer token on each OIDC login. Old session invalidated. |
| Brute force phone code | Telegram rate-limits SMS delivery. 5 attempt limit on our side. |
| JWT kid substitution | JWKS cached 1hr, refreshed on kid miss. |
| Clock skew | 30s leeway on exp/iat validation. |
| Multi-instance state tampering | State JWT signed with HMAC-SHA256. Signing key is server secret. |

---

## Backward Compatibility

- **Existing bearer tokens**: continue working (server looks up by token, unchanged)
- **Non-OAuth MCP clients**: fall back to `/setup` web flow
- **Legacy sessions**: `token.session` unchanged; sessions.db row created on first OIDC login
- **Web setup users**: phone→code→2FA flow unchanged
- **setup-*.session / reauth-*.session**: temporary setup files, managed by `cleanup_stale_setup_sessions()` as today

---

## Files to Modify / Create

| File | Changes |
|------|---------|
| `src/config/server_config.py` | Add `BOT_ID`, `BOT_CLIENT_SECRET`, `STATE_SIGNING_KEY`, `SESSION_TTL_DAYS`, `MAX_SESSIONS_PER_USER` fields |
| `src/server_components/oidc_auth.py` | New: OIDC routes, state JWT signing/validation, Telegram token exchange, id_token validation, callback handler |
| `src/server_components/sessions_db.py` | New: sessions.db schema and CRUD |
| `src/server_components/mcp_elicitation.py` | New: phone code + 2FA password elicitation handlers |
| `src/server_components/session_cleanup.py` | New: `cleanup_stale_session_files()` for disk-based TTL cleanup |
| `src/server_components/web_setup.py` | Add OIDC routes (`/oauth/*`, `/.well-known/*`, `/.well-known/oauth-protected-resource`) |
| `src/server.py` | Call `cleanup_stale_session_files()` in cleanup_loop; initialize sessions_db |
| `src/templates/setup.html` | Add "Login with Telegram" button (OAuth path) |

---

## Implementation Order

1. **OIDC proxy endpoints**: `/.well-known/openid-configuration`, `/.well-known/jwks.json` (proxy to Telegram), `/.well-known/oauth-protected-resource`
2. **State JWT signing/validation**: Create and validate state JWT with code_challenge
3. **OAuth callback handler**: Validate state, exchange code with Telegram, validate id_token
4. **Session creation**: Generate token, create .session file + sessions.db row
5. **Elicitation for phone code**: MCP prompt for SMS code, client.sign_in()
6. **Elicitation for 2FA password**: MCP prompt for password with hint
7. **Max sessions enforcement**: Count and delete oldest per tg_user_id
8. **Cleanup job**: `cleanup_stale_session_files()` using Telethon `last_check`
9. **Update `/setup` page**: Add OIDC login button
10. **Full end-to-end test** with real Telegram OIDC flow
