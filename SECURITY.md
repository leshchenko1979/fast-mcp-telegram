# 🔒 Security & Authentication

## Bearer Token Authentication System

- **Per-Session Authentication**: Each session requires a unique Bearer token
- **Session Isolation**: Each token creates an isolated Telegram session
- **Token Generation**: Cryptographically secure 256-bit tokens via setup script
- **Reserved Name Protection**: Common session names blocked to prevent conflicts
- **HTTP Authentication**: Mandatory Bearer tokens for HTTP transport (`Authorization: Bearer <token>`)
- **Development Mode**: `DISABLE_AUTH=true` bypasses authentication for development

### Authentication Methods

**Header-Based Auth (Recommended):**
- Token sent in `Authorization: Bearer <token>` header
- Token does not appear in URL or server access logs
- Use this for production environments

**URL-Based Auth (For Limited Clients):**
- Token included in URL path: `/v1/url_auth/{token}/mcp/...`
- Token appears in URLs and server access logs
- Use only when header-based auth is not possible
- Same token validation applies (reserved names blocked)

## Multi-User Security Model

- **Session Separation**: Each user gets their own authenticated session file
- **Token Privacy**: Bearer tokens should be treated as passwords and kept secure
- **Session Files**: Contain complete Telegram access for the associated token
- **Account Access**: Anyone with a valid Bearer token can perform **ANY action** on that associated Telegram account **unless** opt-in session ACL applies to that principal

## Opt-in session ACL (http-auth)

When **`ACL_ENABLED=true`**, operators can restrict **specific principals** via a server-side config file (default `{session_directory}/acl.yaml`, override with **`ACL_CONFIG_PATH`**). See **`acl.yaml.example`**, [ADR 0001](docs/adr/0001-agent-scoped-session-acl.md), and [acl-design-brief.md](docs/research/acl-design-brief.md).

**What ACL does:** Limits what **MCP tools** can do for specific principals (which chats they may use, whether they may send messages or call raw Telegram APIs). It does **not** lock the Telegram account — people can still use the official Telegram apps.

**Terminology**

| Term | Meaning |
| --- | --- |
| **Principal** | One hosted MCP session: a Telegram account (human or bot) with lane rules in `acl.yaml`. |
| **Principal identifier** | Key under `principals:` naming that session. **Today** = same string as the Bearer token and `{id}.session` filename. **Later** = `@username` or Telegram `user_id` (roadmap). |
| **Bearer token** | What clients send in `Authorization: Bearer …`. HTTP credential only — not the ACL policy noun. |
| **Chat ref** | Entry in `chats:` (id, `@handle`, `me`). Not a principal. |

### Enablement

1. Set `ACL_ENABLED=true` in the server environment (http-auth only; not stdio or http-no-auth).
2. Create the ACL file at the default path or set `ACL_CONFIG_PATH`.
3. Restart the server (or redeploy). The server **refuses to start** if ACL is enabled but the file is missing or invalid.
4. List only the **principals** you want to restrict under `principals:`. **Unlisted principals keep full tool access** unless `ACL_DENY_UNLISTED_PRINCIPALS=true` (then any principal not listed is denied).
5. Use top-level **`principals:`**, not `tokens:` (renamed in 0.23.0; server errors if legacy `tokens:` is present).

Treat the ACL file like a secret (contains principal identifier strings). Restrict file permissions (e.g. `0600`). Clients still authenticate with Bearer tokens in the HTTP header.

### Agent profiles (copy these patterns into `acl.yaml`)

| Profile | Typical use | `chats` | `read_only` | `allow_global_search` | `allow_mtproto` |
| --- | --- | --- | --- | --- | --- |
| **full_access** *(default, unlisted principal)* | Personal / demo | — | false | true | true *(unlisted)* |
| **analyst** | Read only, specific chats | non-empty list | true | true | false |
| **team_lane** | Work chats; may send | non-empty list | false | true | false |
| **bot** | Channel automation only | channel ids | false | false | false |
| **power-principal** *(optional, see example)* | Needs raw Telegram API access | non-empty list | false | true | true |

`read_only: true` **requires** a non-empty `chats` list (the server rejects startup if an analyst-style entry has no chats).

### Principal lane settings

- **`chats`**: Chat ids, `@username`, or `me` (Saved Messages) this principal may use.
- **Listed principal with empty `chats`** (`chats: []` or `chats` omitted): Chat tools are **rejected with an error** (not an empty result list). Applies to `find_chats`, `search_messages_globally`, reads/writes in any chat, and `send_message_to_phone`.
- **`read_only`**: Blocks send, edit, `invoke_mtproto`, and the HTTP MTProto bridge (`/mtproto-api/*`).
- **`allow_global_search`**: When false, blocks `search_messages_globally` and raw MTProto.
- **`allow_mtproto`**: When false (default for listed principals), blocks `invoke_mtproto` and the HTTP MTProto bridge. Set `read_only: false` and `allow_global_search: true` as well to allow raw MTProto.
- **`ACL_DENY_UNLISTED_PRINCIPALS`**: When true, any principal not listed under `principals:` is denied (error message names the env var). Default false.
- **Extra YAML keys**: Unknown keys log a warning at startup. Operator notes may use an `x_` prefix (for example `x_note`) to avoid warnings.

### Sensitive peers every principal must avoid (`blocked_peers`)

When **`blocked_peers`** is set (non-empty list in the ACL file), those peers are **blocked for every principal** — listed and unlisted. A blocked peer stays blocked even if it appears in a principal’s `chats` list.

| Config | Behavior |
| --- | --- |
| **`blocked_peers` omitted** | No sensitive blocking; lane ACL only |
| **`blocked_peers: []`** | Explicit empty — no sensitive blocking |
| **Non-empty list** | Enforced exactly as configured (operators own the full list) |

**Recommended defaults** (copy from [`acl.yaml.example`](acl.yaml.example) for shared hosts):

| Peer id | Handle | Why block |
| --- | --- | --- |
| `777000` | Telegram service | Login codes, security alerts |
| `93372553` | @BotFather | Bot tokens, settings |
| `178220800` | @SpamBot | Spam/limit appeals |

**Use numeric peer ids in YAML** when you can (covers MTProto calls that pass ids in JSON). Optional `@username` lines help block `@BotFather` in tool arguments before Telegram resolves the name.

**After a tool runs:** `get_chat_info` and `get_messages` are checked again using the numeric id and username Telegram returned — so `@BotFather` in YAML still blocks that chat even if the agent passed a numeric id.

**Limitation:** The server does not look up usernames in Telegram before the tool runs. If you only list `@BotFather` in YAML, a numeric id in the tool argument may succeed once; the follow-up check on the result still blocks it when the tool returns.

**MTProto calls:** The server scans `params` / `params_json` for blocked numeric ids (not every nested field). Invalid JSON in `params_json` is rejected when `blocked_peers` is set.

**List tools:** `find_chats` and `search_messages_globally` remove blocked peers from results. An empty list after filtering is normal success, not an error.

**Typical error:** `Session ACL: blocked peer (<ref>) is denied for this deployment. See SECURITY.md.`

**Shared-host risk:** With `ACL_ENABLED=true` and no `blocked_peers`, teammates who share a principal identifier can still read login-code chats and BotFather via MCP. On shared hosts, copy the recommended blocklist from [`acl.yaml.example`](acl.yaml.example).

### What the server checks for listed principals

| Surface | Behavior |
| --- | --- |
| MCP tools (`get_messages`, `send_message`, …) | `chat_id` checked before the tool runs; list results filtered afterward |
| `find_chats` / `search_messages_globally` | Results limited to allowed chats; empty `chats` → error, not empty lists |
| `invoke_mtproto` | Allowed only if `allow_mtproto: true`, `allow_global_search: true`, and not `read_only` |
| HTTP MTProto bridge (`/mtproto-api/*`) | Same rules as `invoke_mtproto` |

Denials return MCP `ok: false` with actionable text (principal, chat id, lane). HTTP bridge returns 403.

### Shared principal limits

ACL reduces **accidental** access to the wrong chats and **misuse of MCP tools** when teammates share one principal on an http-auth host. ACL does **not**:

- Stop someone with the raw Bearer token from calling Telegram outside this MCP server
- Replace Telegram account security (2FA, session revocation in official clients)
- Apply to stdio or http-no-auth deployments

When **`blocked_peers`** is configured, the denylist applies on http-auth for **all** principals (see above).

### Troubleshooting denials

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| “empty chat lane” | Principal listed with `chats: []` or no `chats` key | Add at least one chat to the `principals:` entry |
| “empty chat lane” on `get_messages` / `get_chat_info` | Same as above (empty or missing `chats`) | Add at least one chat ref to the principal entry |
| “not in the allowed list” | Tool targets a chat outside the lane | Add chat id / `@username` to `chats` or use an unlisted principal |
| Lane lists `@handle` but numeric `chat_id` denied | Enforcement matches lane refs to the ref you pass; `@handle` lanes do not auto-match numeric ids in tool args | Pass `@username` in `chat_id` for tools, or add the numeric id to `chats`; future release may resolve handles — see [Roadmap](docs/Roadmap.md) Trust lane |
| “allow_mtproto is false” on `invoke_mtproto` with empty `chats` | Default `allow_mtproto: false` for listed principals (not the “empty chat lane” string) | Add chats and opt in with `allow_mtproto: true`, or fix empty lane |
| “read-only” | `read_only: true` on the principal | Set `read_only: false` or use a write-capable profile |
| “global message search” | `allow_global_search: false` | Set `allow_global_search: true` or use `get_messages` in-lane |
| “allow_mtproto is false” on MTProto | Listed principal has not opted in to raw MTProto | Set `allow_mtproto: true` (and ensure `read_only: false`, `allow_global_search: true`) |
| “allow_global_search is false” on MTProto | **bot** profile (`allow_global_search: false`) | Set `allow_global_search: true` or use `get_messages` in allowed chats |
| Unlisted principal denied everywhere | `ACL_DENY_UNLISTED_PRINCIPALS=true` | Add principal to `principals:` with a lane, or set `ACL_DENY_UNLISTED_PRINCIPALS=false` |
| “blocked peer … denied for this deployment” | Peer is on `blocked_peers` denylist | Remove peer from tool args; adjust denylist if policy allows; see numeric-id guidance above |
| “invalid params_json” with blocked_peers | Malformed JSON when denylist is active | Fix JSON or omit `params_json` |
| Server refuses to start | Missing ACL file, invalid YAML, or legacy `tokens:` key | Create file; rename `tokens:` → `principals:`; fix malformed entries; ensure `read_only` has `chats`; fix `blocked_peers` list shape |

No MCP tool mutates ACL in v1 — edit the file on the server and restart.

**Development and testing:** ACL behavior is validated with **pytest** and a local **http-auth** server exercised via **curl** (Bearer header per profile), not via Cursor MCP — stdio mode has no ACL, and URL MCP entries bind a single fixed token. See [CONTRIBUTING.md — ACL development and testing](CONTRIBUTING.md#acl-development-and-testing-not-via-cursor-mcp).

## Production Security Recommendations

1. **Secure Token Distribution**: Distribute Bearer tokens through secure channels only
2. **Token Rotation**: Regularly generate new tokens and invalidate old ones
3. **Access Monitoring**: Monitor session activity through `/health` HTTP endpoint
4. **Network Security**: Use HTTPS/TLS and consider IP restrictions
5. **Session Management**: Regularly clean up unused sessions and tokens

## Attachment download URLs (HTTP)

When **`DOMAIN`** is set to a non-placeholder public host and the server runs over **HTTP**, tools that return formatted messages may include **`media.attachment_download_url`** pointing to **`GET /v1/attachments/{uuid}`** (same public origin as web setup / MCP URL, derived from **`DOMAIN`**).

- **No Bearer token on download**: The UUID in the path is a **secret capability**. Anyone who obtains the URL can download the associated media until the ticket expires.
- **TTL**: Controlled by **`ATTACHMENT_TICKET_TTL_SECONDS`** (see `.env.example`). Use the shortest TTL that fits your workflow.
- **Single process**: Tickets are stored **in memory**. A process restart invalidates all tickets. Multiple workers or replicas without shared storage will not see each other’s tickets.
- **Session binding**: The server uses the Telegram session that minted the ticket to stream bytes; the HTTP client does not send session credentials.
- **Mitigations**: Use HTTPS at the edge, keep TTL low, avoid pasting links into public logs or chats, and treat leaked URLs like leaked file access.

## File Security

### SSRF Protection
- **URL Security Validation**: Blocks localhost, private IPs, and suspicious domains
- **Enhanced HTTP Client**: Disabled redirects, connection limits, security headers, and timeouts
- **File Size Limits**: Configurable maximum file size with both header and content validation
- **Configuration Options**: `allow_http_urls`, `max_file_size_mb`, `block_private_ips` settings

### Local File Access
- **Local paths**: Allowed in all transport modes — automatically inlined as data: URIs
- **URL downloads**: Supported in all modes with SSRF protection
- **Size validation**: Both header and content validation for downloaded files

## Token Validation Security

- **Format**: HTTP_AUTH bearer tokens must be 43-character URL-safe base64 strings (same as setup/CLI generation: `[A-Za-z0-9_-]{43}`). Tokens containing `/`, `\`, or path segments are rejected.
- **Path containment**: Session files are resolved as `{session_directory}/{token}.session` and must stay under `session_directory` after `resolve()`.
- **Reserved Name Blocking**: Prevents common session names from being used as bearer tokens
- **Blocked Names**: `telegram`, `default`, `session`, `bot`, `user`, `main`, `primary`, `test`, `dev`, `prod`
- **Case Insensitive**: Validation ignores case differences
- **Session Conflict Prevention**: Blocks tokens that could create file conflicts with STDIO/HTTP_NO_AUTH sessions
- **Logging**: Rejected tokens are logged with warning messages for security monitoring

## Session File Security

- **Location**: `~/.config/fast-mcp-telegram/` for cross-platform compatibility
- **Format**: `{token}.session` for multi-user isolation
- **Git Security**: Session files excluded from version control
- **Permissions**: Automatic permission fixing for container user access (1000:1000)
- **Backup/Restore**: Sessions automatically backed up and restored across deployments

## Development Security

- **Environment Variables**: Never commit `.env` files with real credentials
- **Session Files**: Excluded from git via `.gitignore`
- **Authentication Bypass**: Use `DISABLE_AUTH=true` only in development environments
- **Token Management**: Use temporary tokens for testing, not production tokens
