# 🔒 Security & Authentication

## Bearer Token Authentication System

- **Per-Session Authentication**: Each session requires a unique Bearer token
- **Session Isolation**: Each token creates an isolated Telegram session
- **Token Generation**: Cryptographically secure 256-bit tokens via setup script
- **HTTP Authentication**: Mandatory Bearer tokens for HTTP transport (`Authorization: Bearer <token>`)
- **Development Mode**: `DISABLE_AUTH=true` bypasses authentication for development

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
