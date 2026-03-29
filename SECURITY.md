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
- **Account Access**: Anyone with a valid Bearer token can perform **ANY action** on that associated Telegram account

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
- **Local paths**: Only allowed in stdio mode for security
- **URL downloads**: Supported in all modes with SSRF protection
- **Size validation**: Both header and content validation for downloaded files

## Token Validation Security

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
