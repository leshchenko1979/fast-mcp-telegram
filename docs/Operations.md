# 📊 Operations Guide

## Health & Session Monitoring

For HTTP deployments, the server provides a `/health` endpoint for monitoring server status and session statistics.

### Health Endpoint

```bash
# Check server health and session statistics
curl -s https://your-domain.com/health
```

**Response includes:**
- Server status
- Active session count and max limit
- Count of session files on disk
- Setup session count (web setup flow)
- Per-session statistics (token prefix, hours since access, connection status, last access)

**Example response:**
```json
{
  "status": "healthy",
  "active_sessions": 3,
  "max_sessions": 10,
  "session_files": 3,
  "setup_sessions": 1,
  "sessions": [
    {
      "token_prefix": "AbCdEfGh...",
      "hours_since_access": 0.25,
      "is_connected": true,
      "last_access": "Thu Jan 4 16:30:15 2025"
    },
    {
      "token_prefix": "XyZ123Ab...",
      "hours_since_access": 2.5,
      "is_connected": false,
      "last_access": "Thu Jan 4 14:15:30 2025"
    }
  ]
}
```

### Session Statistics

#### Active Sessions
- **Current count**: Number of sessions currently in memory
- **Max limit**: Configurable via `MAX_ACTIVE_SESSIONS` environment variable
- **LRU eviction**: Oldest sessions disconnected when limit reached

#### Session Files
- **On disk count**: Total number of session files in `~/.config/fast-mcp-telegram/`
- **Setup sessions**: Temporary sessions created during web setup flow
- **TTL cleanup**: Setup sessions automatically cleaned up after 900 seconds

#### Per-Session Details
- **Token prefix**: First 8 characters of Bearer token for identification
- **Hours since access**: Time since last API call
- **Connection status**: Whether session is actively connected to Telegram
- **Last access**: Timestamp of most recent activity

## Container Health Checks

### Docker Health Status
```bash
# Check container status
docker compose ps

# View real-time logs
docker compose logs -f fast-mcp-telegram

# Check container health
docker inspect $(docker compose ps -q fast-mcp-telegram) | jq '.[0].State.Health'
```

### Health Check Endpoints
- **Container health**: Docker health check endpoint
- **Application health**: `/health` HTTP endpoint
- **MCP transport**: MCP protocol health via client connection

## Logging and Monitoring

### Log Levels
- **DEBUG**: Detailed operation traces
- **INFO**: General operation information
- **WARNING**: Non-critical issues
- **ERROR**: Critical errors requiring attention

### Log Configuration
```bash
# Set log level via environment variable
LOG_LEVEL=INFO

# Or via Docker environment
docker compose up -d --env LOG_LEVEL=DEBUG
```

### Log Locations
- **Container logs**: `docker compose logs fast-mcp-telegram`
- **File logs**: `/app/logs/` (if configured)
- **Console output**: Standard output for containerized deployments

### Key Log Events
- **Authentication**: Bearer token extraction and validation
- **Session creation**: New session file creation
- **API calls**: Telegram API requests and responses
- **Errors**: Authentication failures, API errors, connection issues
- **Health checks**: Periodic health status updates

## Session Management

### Session Lifecycle
1. **Creation**: New session created on first authentication
2. **Activation**: Session loaded into memory on first use
3. **Usage**: Session used for Telegram API calls
4. **Reauthorization**: Expired sessions can be reauthorized via web interface or CLI
5. **Eviction**: Session removed from memory when LRU limit reached
6. **Cleanup**: Invalid sessions automatically deleted

### Session Reauthorization

When a session becomes unauthorized (expired login, password change, etc.), you can reauthorize it:

#### Web Interface (HTTP_AUTH mode)
1. Visit `https://your-domain.com/setup`
2. Choose "Reauthorize Existing Session"
3. Enter your existing Bearer token
4. Confirm phone number and complete verification
5. Session is reauthorized with the same token

#### CLI Reauthorization
```bash
# For HTTP_AUTH mode (with existing token)
fast-mcp-telegram-setup --overwrite --phone-number="+1234567890"

# For STDIO mode
SESSION_NAME=telegram fast-mcp-telegram-setup --overwrite --phone-number="+1234567890"
```

#### Detecting Unauthorized Sessions
- **Health endpoint**: Shows connection status per session
- **API errors**: Unauthorized sessions return authentication errors
- **Logs**: Check for "Session not authorized" messages

### Session Files
- **Location**: `~/.config/fast-mcp-telegram/`
- **Format**: `{token}.session` for multi-user isolation
- **Permissions**: Automatic permission management (1000:1000)
- **Backup**: Automatic backup before deployments
- **Restore**: Automatic restore after deployments

### Session Monitoring
```bash
# Check session files on disk
ls -la ~/.config/fast-mcp-telegram/

# Monitor session creation/deletion
tail -f /var/log/telegram-sessions.log

# Check session permissions
find ~/.config/fast-mcp-telegram/ -type f -exec ls -la {} \;
```

## Performance Monitoring

### Key Metrics
- **Active sessions**: Current in-memory session count
- **API response times**: Telegram API call latency
- **Memory usage**: Container memory consumption
- **CPU usage**: Container CPU utilization
- **Network I/O**: Data transfer rates

### Monitoring Commands
```bash
# Container resource usage
docker stats fast-mcp-telegram

# Memory usage
docker exec fast-mcp-telegram ps aux

# Network connections
docker exec fast-mcp-telegram netstat -an

# Disk usage
docker exec fast-mcp-telegram df -h
```

### Performance Optimization
- **Session limits**: Adjust `MAX_ACTIVE_SESSIONS` based on usage
- **Log levels**: Use INFO/WARNING in production
- **Resource limits**: Set appropriate Docker resource limits
- **Monitoring**: Implement external monitoring for production

## Troubleshooting

### Common Issues

#### Authentication Failures
```bash
# Check Bearer token format
curl -H "Authorization: Bearer YOUR_TOKEN" https://your-domain.com/health

# Verify session file exists
ls -la ~/.config/fast-mcp-telegram/

# Check logs for authentication errors
docker compose logs fast-mcp-telegram | grep -i auth
```

#### Session Issues
```bash
# Check session file permissions
ls -la ~/.config/fast-mcp-telegram/

# Fix permissions if needed
chown -R 1000:1000 ~/.config/fast-mcp-telegram/

# Check session file integrity
file ~/.config/fast-mcp-telegram/*.session
```

#### Connection Problems
```bash
# Test basic connectivity
curl -s https://your-domain.com/health

# Check container status
docker compose ps

# Verify network connectivity
docker exec fast-mcp-telegram ping -c 3 api.telegram.org
```

### Debug Mode
```bash
# Enable debug logging
docker compose up -d --env LOG_LEVEL=DEBUG

# Monitor debug output
docker compose logs -f fast-mcp-telegram

# Check specific operations
docker compose logs fast-mcp-telegram | grep "operation_name"
```

### Health Check Failures
```bash
# Check container health
docker inspect $(docker compose ps -q fast-mcp-telegram) | jq '.[0].State.Health'

# Restart container
docker compose restart fast-mcp-telegram

# Check health endpoint
curl -s https://your-domain.com/health
```

## Maintenance

### Regular Tasks
- **Monitor health endpoint**: Check server status regularly
- **Review logs**: Look for errors and performance issues
- **Clean up sessions**: Remove unused session files
- **Update dependencies**: Keep packages up to date
- **Backup sessions**: Ensure session files are backed up

### Session Cleanup
```bash
# List all session files
ls -la ~/.config/fast-mcp-telegram/

# Remove old/unused sessions (be careful!)
rm ~/.config/fast-mcp-telegram/old-token.session

# Check session age
find ~/.config/fast-mcp-telegram/ -name "*.session" -mtime +30
```

### Log Rotation
```bash
# Check log file sizes
du -sh /var/log/telegram-*.log

# Rotate logs if needed
logrotate /etc/logrotate.d/telegram

# Clean old logs
find /var/log -name "telegram-*.log.*" -mtime +7 -delete
```

## Security Monitoring

### Authentication Monitoring
- **Failed logins**: Monitor for authentication failures
- **Token usage**: Track Bearer token usage patterns
- **Session creation**: Monitor new session creation
- **Suspicious activity**: Look for unusual access patterns

### Security Checks
```bash
# Check for failed authentication attempts
docker compose logs fast-mcp-telegram | grep -i "auth.*fail"

# Monitor token usage
docker compose logs fast-mcp-telegram | grep -i "bearer"

# Check for suspicious API calls
docker compose logs fast-mcp-telegram | grep -i "dangerous"
```

### Access Control
- **IP restrictions**: Implement network-level access controls
- **Rate limiting**: Monitor and limit API call rates
- **Token rotation**: Regularly rotate Bearer tokens
- **Session monitoring**: Track session usage and access patterns

## Backup and Recovery

### Session Backup
```bash
# Backup all sessions
tar -czf telegram-sessions-backup-$(date +%Y%m%d).tar.gz ~/.config/fast-mcp-telegram/

# Restore sessions
tar -xzf telegram-sessions-backup-20240104.tar.gz -C ~/
```

### Configuration Backup
```bash
# Backup configuration
cp .env .env.backup-$(date +%Y%m%d)

# Backup Docker Compose
cp docker-compose.yml docker-compose.yml.backup-$(date +%Y%m%d)
```

### Disaster Recovery
1. **Restore sessions**: Extract session files from backup
2. **Restore configuration**: Copy environment and config files
3. **Restart services**: Bring up containers with restored data
4. **Verify health**: Check health endpoint and test functionality
5. **Monitor logs**: Watch for any issues during recovery
