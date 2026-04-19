# Telegram OIDC + MCP OAuth Setup Design

**Date:** 2026-04-19
**Status:** Draft

---

## Overview

Add Telegram as an OIDC Authorization Server, enabling OAuth-based login directly from MCP clients that support it (Claude Desktop, Cursor). The existing phone→code→2FA web flow is preserved as fallback or for non-OAuth-capable clients.

**Goals:**
- Simplify UX: "Login with Telegram" button in OAuth-capable MCP clients
- Preserve phone-keyed sessions: same phone number = same session file across devices
- Preserve full 2FA support with password hint
- New users: OAuth → phone verification via MCP elicitation → session created
- Returning users: OAuth → session valid → done; session expired → re-auth via elicitation

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

Phone lookup:
  phone_e164 = normalize(phone_number)
  Look up token by phone_e164 (phone → token index):
    → Found: existing token → check if {token}.session is valid
    → Not found: generate new random bearer token

  → If valid session exists:
       Issue access token
       Return to MCP client

  → If session expired or missing:
       MCP Elicitation: "Telegram sent a verification code. Enter it below."
       User gets SMS → enters code via MCP prompt
       Server: client.sign_in(phone, code)
         → If SessionPasswordNeededError:
              Fetch hint via GetPasswordRequest()
              MCP Elicitation: "Enter your 2FA password (hint: {hint})"
              User enters password
              Server: client.sign_in(password=password)
         → On success:
              Save session as {random_token}.session
              Index phone_e164 → token (so same phone finds this session next time)
```

---

## Session Key: Phone Number — Index Only

- **Session file name**: `{random_bearer_token}.session` (unchanged from today)
- **Phone** is the **index key** (not hashed) — maps normalized phone → bearer token
- Same phone number from different MCP clients → same token → same `.session` file
- `tg_user_id` stored in the index for logging/debugging

**Phone normalization** (consistent with existing `_normalize_phone_number`):
- Strip spaces, dashes, parentheses
- Ensure leading `+`
- Digits only after `+`
- Validate 7-15 digits

**Phone → Token index (SQLite `phone_index.sqlite`):**
```sql
CREATE TABLE phone_to_token (
  phone_e164 TEXT PRIMARY KEY,       -- normalized phone, e.g. "+1234567890"
  token TEXT UNIQUE NOT NULL,        -- bearer token → .session filename
  tg_user_id INTEGER,
  auth_method TEXT NOT NULL DEFAULT 'oidc',
  created_at INTEGER NOT NULL,
  last_auth_at INTEGER NOT NULL,
  last_oidc_iat INTEGER
);
CREATE INDEX idx_token ON phone_to_token(token);
```

```
phone_e164: "+1234567890"  →  token: "abc123...xyz"  →  session file: abc123...xyz.session
```

On first OIDC login, the server inserts the index entry. Subsequent logins find it.

**Migration path for existing sessions:**
- Existing sessions are named `{bearer_token}.session`
- On first OIDC login, server inserts `phone_e164 → token` entry
- No forced migration; legacy tokens continue working

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

When OIDC succeeds but no valid session exists:

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
# These are used ONLY for the OIDC authentication flow.
# They are NOT used for Telegram Bot API calls (which use BOT_TOKEN env var).
BOT_ID: str              # Telegram Bot ID (numeric string, e.g. "123456789")
BOT_CLIENT_SECRET: str    # OIDC client secret (from BotFather web login settings)
```

**Existing Telegram API credentials remain unchanged:**
```python
API_ID: int     # From my.telegram.org — for MTProto user sessions
API_HASH: str   # From my.telegram.org — for MTProto user sessions
```

### Session metadata fields

```python
# In phone_index.sqlite (the index DB)
phone_e164: str            # normalized phone number (index key)
tg_user_id: int            # From OIDC id_token sub claim
auth_method: Literal["oidc", "phone"]  # How they authenticated
last_oidc_iat: int         # When they last re-authed via OIDC
```

### In-memory state (OIDC flow)

```python
# _oidc_state_store: maps state param → OIDC callback context
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
    # Fetch Telegram's public keys (cached)
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
│   │         Client redirects to Telegram → OIDC flow → phone lookup
│   │
│   └─ NO → Fall back to existing /setup web flow
             (browser-based manual auth)
```

---

## Backward Compatibility

- **Existing bearer tokens**: continue working (server validates and maps to session)
- **Non-OAuth MCP clients**: fall back to `/setup` web flow
- **Legacy sessions**: `token.session` continues to work; migration is gradual
- **Web setup users**: phone→code→2FA flow unchanged

---

## Security Considerations

1. **JWT validation**: Always verify Telegram's `id_token` signature using Telegram's JWKS
2. **state parameter**: CSRF protection — random state validated on callback
3. **PKCE**: Telegram OIDC supports S256 — use it for authorization code flow
4. **Short-lived code exchange**: Authorization code exchanged immediately, not stored long-term
5. **Phone as session key**: Users with same phone share session — intentional for multi-device use case
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

## Files to Modify

| File | Changes |
|------|---------|
| `src/config/server_config.py` | Add `BOT_ID`, `BOT_CLIENT_SECRET` fields |
| `src/server_components/phone_index.py` | New: `phone_index.sqlite` CRUD, phone normalization |
| `src/server_components/web_setup.py` | Add OIDC routes (`/oauth/*`, `/.well-known/*`) |
| `src/server_components/auth.py` | Add `validate_telegram_id_token()`, phone-to-token lookup |
| `src/client/connection.py` | Support phone-indexed sessions in session cache |
| `src/server_components/mcp_elicitation.py` | New: phone code + 2FA password elicitation handlers |
| `src/templates/setup.html` | Add "Login with Telegram" button (OAuth path) |
| `src/templates/fragments/oauth_button.html` | New: OIDC login button fragment |

---

## Implementation Order

1. **OIDC proxy endpoints**: `/.well-known/openid-configuration`, `/.well-known/jwks.json`
2. **OAuth callback handler**: `/oauth/callback` — validates Telegram JWT, extracts phone
3. **Phone-indexed session lookup**: Look up token by `phone_e164` index before creating new
4. **MCP elicitation for phone code**: Replace web form with MCP prompt
5. **2FA password elicitation**: With hint from `GetPasswordRequest()`
6. **Update `/setup` page**: Add OIDC login button as primary option
7. **OAuth-capable client detection**: Detect OAuth support from MCP client hello
8. **Bearer token migration**: Index existing `{token}.session` with `phone_e164 → token` on first OIDC login
