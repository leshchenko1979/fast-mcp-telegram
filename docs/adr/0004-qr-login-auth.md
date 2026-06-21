# ADR 0004: QR Login Auth — Simplified Self-Service Onboarding

## Status

Accepted — Implemented and deployed (v0.30.0, live at tg-mcp.l1979.ru)

## Date

2026-06-09

## Context

The OIDC + elicitation approach (ADR 0002, ADR 0003) was over-engineered for the actual use case. Research revealed:

1. **Elicitation protocol support is scarce** — The most popular MCP clients (Claude Desktop, Cline, Continue.dev) do NOT support form-mode elicitation. Only Cursor 2.0+, VS Code Insiders, and Claude Code CLI support it. This makes an elicitation-dependent auth path effectively client-locked.

2. **Telethon has built-in QR login** — `client.qr_login()` generates a `tg://login?token=...` URL. User scans it from Telegram mobile → MTProto session created. No phone number, no verification code, no 2FA input needed. This eliminates the entire elicitation state machine.

3. **Telegram has a proper OIDC provider** — `https://oauth.telegram.org/.well-known/openid-configuration` supports Authorization Code + PKCE, RS256 JWTs, and issues `id_token` with `sub` (Telegram user_id). This can serve as the OIDC provider, removing the need for external Auth0/Clerk.

4. **External OIDC providers add friction without benefit** — Users of a Telegram MCP server are already on Telegram. Making them also log in via Google/GitHub/Auth0 before accessing Telegram tools is pointless indirection.

5. **The JWT has no value for the web setup path** — Web setup (`/setup`) is already public. Anyone can visit, enter phone/code/2FA, and get a bearer token. The OIDC JWT doesn't gate this path.

### MCP Session Support: Considered and Rejected

MCP session management (the `Mcp-Session-Id` header in the 2025-11-25 Streamable HTTP spec) was evaluated for a "no-paste" QR login flow — embedding the session ID in the QR callback URL so the client session is authenticated automatically without token pasting.

**This was rejected because:**

1. **Sessions are being removed from the protocol** — the 2025-06-18 DRAFT spec explicitly removes all session management: "None of these mechanisms are part of this revision." SEP-2567 formalizes this as a clean break — no deprecation window, sessions are deleted from the next spec version.

2. **Bearer tokens + URL path auth already cover all cases** — the "explicit state handle" pattern that SEP-2567 proposes as the replacement for sessions is exactly what bearer tokens already provide. The token is the handle.

3. **The marginal value is near-zero** — the optional no-paste flow saves one paste in one specific scenario (first auth of a live MCP session). The bearer token is already presented on the success page. Pasting it once is acceptable UX overhead for eliminating an entire protocol-version dependency.

**Result:** Architecture is 100% session-independent. No `Mcp-Session-Id` logic, no `ctx.get_state()` / `ctx.set_state()` for identity storage, no session-ID-in-URL encoding. Everything goes through explicit credentials.

## Decision

Scrap the OIDC + elicitation approach entirely. Replace with Telethon QR login as the primary auth path, with web setup (phone/code/2FA) and URL path auth as fallbacks.

### Decision 1: No OIDC, No Elicitation Tools, No Setup Tool

Remove all OIDC-related code:
- `TG_OIDC_ISSUER`, `TG_OIDC_AUDIENCE` env vars
- `OidcTokenVerifier`, `JWTVerifier` integration
- Elicitation state machine (`setup_state` transitions, TTL enforcement, retry tracking)
- Elicitation MCP tools (`oidc_setup_start`, `oidc_setup_phone`, `oidc_setup_code`, `oidc_setup_password`)
- `oidc_identity` table and `setup_state` table in SQLite
- `register_elicitation_tools()` and `create_oidc_verifier()` paths in server.py
- `principal_resolver.py` (OIDC sub → Telegram identity mapping)
- All related test files

The `feature/oidc-phase1-storage` branch is archived for reference.

### Decision 2: QR Login as Primary Auth Path

When an unauthenticated user calls any MCP tool:

1. The tool detects no auth context (no valid bearer token / no Telethon session).
2. The tool returns a response containing both:
   - **QR login URL**: a server endpoint that renders a QR code (Telethon `qr_login().url`).
   - **Web setup URL**: the existing `/setup` page.
3. User scans the QR from Telegram mobile → Telethon creates a MTProto session → `.session` file saved.
4. Server generates a bearer token bound to this session.
5. Bearer token is returned to the user (via web page, bot DM, or URL callback).
6. User configures the bearer token (or URL path auth link) in their MCP client.
7. Subsequent requests include the credential → server validates → full access.

### Decision 3: No Dedicated `setup` Tool

The elicitation/auth flow is embedded in every tool via a **shared middleware or decorator** (`require_auth`). This decorator:

1. Checks whether the request has a valid authenticated session (bearer token → Telethon session).
2. If not authenticated: returns a structured response with auth guidance — the QR login URL and web setup URL — instead of executing the tool's logic.
3. If authenticated but the Telethon session needs re-auth (expired, disconnected): triggers the same auto-auth flow (returns QR URL + web setup URL).
4. If fully authenticated: passes through to the tool's actual handler.

Pattern:
```python
@mcp.tool()
@require_auth
async def send_message(chat_id: str, text: str, ctx: Context) -> str:
    # Only reached if user is authenticated
    ...
```

### Decision 4: 3-Tier Auth Capacity Spectrum

All tools are always visible in the tool list, regardless of auth state. Unauthenticated users see the full capability set (advertising). Each tool returns auth guidance when called without credentials.

The three tiers, from least to most capable client:

| Tier | Mechanism | How it works | For whom |
|------|-----------|-------------|----------|
| **3 — URL path auth** | Token embedded in URL | Server rewrites `/v1/url_auth/{token}/mcp/...` → injects `Authorization: Bearer {token}` header | Clients that can't set HTTP headers but can manipulate URLs (SSE, basic HTTP, curl). Token pre-obtained via web setup. |
| **2 — Bearer token** | `Authorization: Bearer {token}` header | User completes web setup (phone/code/2FA) → gets bearer token → configures it in MCP client | Any HTTP-capable MCP client. Existing flow, unchanged. |
| **1 — QR login** | Scan QR from Telegram mobile | User calls any tool → gets QR URL → scans from phone → session created → bearer token generated → reconnects with token | Simplest UX. No phone typing, no code entry, no 2FA. Requires Telegram mobile app. |

### Decision 5: Unified QR/Form Web Setup Page + URL Path Auth Enhancement

The existing web setup flow (`/setup`) is replaced with a single unified page that shows both auth methods:

- **QR code display** (Telethon `qr_login().url` rendered as QR image)
- **Phone input** (existing phone/code/2FA form, for users without Telegram mobile)

Both paths are presented on the same page. The user chooses whichever is most convenient.

On successful auth completion (QR scan or phone form), the success page shows:
- The bearer token (existing)
- A URL path auth link: `/v1/url_auth/{token}/mcp/...` (new)
- Instructions for configuring the MCP client

The unified page ensures even the least capable clients can connect, and the QR path gets maximum exposure.

### Decision 6: Session Re-Auth Detection

The `require_auth` decorator also checks whether the Telethon session is still valid (connected, not expired). If a previously authenticated user's session has expired or disconnected:

- The tool returns the same auth guidance (QR URL + web setup URL) as for unauthenticated users.
- No distinction between "never authed" and "session expired" at the UX level — both get the same redirect to re-auth.

### Decision 7: Keep Dual Auth, Pre-Release Version

- Bearer token support stays (no drop).
- Web setup stays (no retirement, not deprecated).
- Version stays pre-release (0.30.0, not 1.0.0).

### Decision 8: No Changes to URL Path Auth Middleware

The existing middleware at `auth_middleware.py` (rewriting `/v1/url_auth/{token}/mcp/...` → `/v1/mcp/...` with Bearer header injection) works as-is. No changes needed.

### Decision 9: No Bot DM for Token Delivery

Sending the bearer token via Telegram bot DM was considered but rejected:

- **User would need to start the bot first** — the bot can't initiate a DM with an unknown user. A deep link (`tg://resolve?domain=...`) adds extra steps.
- **Web page is sufficient** — the success page shows the token after QR/phone auth. Token delivery has one reliable channel — no need for a second.
- **QR login doesn't reveal user identity** — the QR callback gives us a Telethon session, but we don't know the user's Telegram handle to DM them. We'd need to ask the API which adds latency and complexity.

Decision: No bot DM. Token delivery is exclusively through the unified web setup page.

## Consequences

### Positive

- ✅ **Radically simpler architecture** — no JWT verifier, no JWKS, no OIDC provider, no elicitation state machine, no OIDC tables, no 4 MCP tools. Just: check auth → QR or web setup → done.
- ✅ **Fewer env vars** — no `TG_OIDC_ISSUER`, no `TG_OIDC_AUDIENCE`, no `TG_DATABASE_URL`. The server needs nothing beyond existing config.
- ✅ **No elicitation protocol dependency** — QR login works through URL-mode elicitation or a direct web page. Any MCP client that can open a URL works.
- ✅ **No phone/code/2FA input for QR path** — user scans QR from phone. That's it. 2FA is handled transparently by Telegram mobile.
- ✅ **All tools advertise server capabilities** — unauthenticated users see the full tool list (8+ tools) in their client's tool explorer.
- ✅ **3-tier spectrum covers every client type** — from the most basic (URL path auth) to the most streamlined (QR login).
- ✅ **Backward compatible** — existing bearer token deployments continue working. Existing web setup flow unchanged.

### Negative

- ⚠️ **QR login requires Telegram mobile app** — the QR URL is a `tg://` deep link that only works from Telegram's mobile app. Users on Telegram Desktop need to open their phone.
- ⚠️ **QR login is async user-interaction** — the Telethon client must stay connected waiting for the QR scan. Requires a polling or callback mechanism.
- ⚠️ **No SSO/enterprise integration** — if someone wants Auth0/Google/GitHub auth, they don't get it. This can be added later as a separate path if demand surfaces.

### Neutral

- The current `feature/oidc-phase1-storage` branch contains working OIDC storage code. If the OIDC path is ever revisited, it's archived at commit `e07ca62`.
- Telethon sessions continue to use `.session` files — no change to session storage.
- ACL system is unaffected — still uses `@username`/`+phone`/`user_id` principals.

## Alternatives Considered

### Keep OIDC as Optional Enterprise Path

Rejected: Maintains N+1 auth mechanisms. The current implementation only covers storage (Phase 1) — verifier, elicitation, and tools are incomplete. Adding an "optional OIDC" path later would be cleaner than maintaining two unfinished auth branches.

### Single `setup` MCP Tool Instead of In-Tool Auth

Rejected earlier in the design process. The user decided that all tools should surface auth guidance (the tool list advertises capabilities), making a dedicated `setup` tool redundant.

### Continue with 4 Elicitation MCP Tools

Rejected: 3 out of 5 most popular MCP clients don't support form-mode elicitation (Claude Desktop, Cline, Continue.dev). This would make the primary auth path inaccessible to most users.

## Migrating from OIDC Branch

The `feature/oidc-phase1-storage` branch is archived. No migration needed — the OIDC code was never merged to master. Existing deployments on master have no OIDC dependencies and no DB tables.

## References

- [ADR 0002](./0002-oidc-self-service-auth.md) — Superseded OIDC approach
- [ADR 0003](./0003-oidc-phase4-scope-based-auth.md) — Superseded Phase 4 draft
- [ADR 0008](./0008-auth-telemetry-events.md) — Auth telemetry events (instrumented QR login flow)
- [Telethon QR Login Documentation](https://docs.telethon.dev/en/stable/modules/client.html#TelethonClient.qr_login)
- [Telegram OIDC Provider](https://oauth.telegram.org/.well-known/openid-configuration)
- [MCP Elicitation Specification](https://spec.modelcontextprotocol.io/specification/2025-03-26/basic/elicitation-considerations/)
- [MCP Streamable HTTP — 2025-11-25 (with session management)](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports)
- [SEP-2567: Sessionless MCP via Explicit State Handles](https://github.com/modelcontextprotocol/specification/discussions/163)
