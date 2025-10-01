# 🌐 HTTP-MTProto Bridge

**Direct curl access to any Telegram API method** - The server provides a powerful HTTP endpoint that allows you to execute any Telegram MTProto method directly via curl or HTTP requests.

## Key Benefits

- **🔄 Any Method**: Execute any Telegram API method not covered by MCP tools
- **🌍 Entity Resolution**: Automatic resolution of usernames, IDs, and phone numbers
- **🛡️ Safety Guardrails**: Dangerous methods blocked by default with opt-in override
- **🔧 Case Insensitive**: Accepts `messages.getHistory`, `messages.GetHistory`, or `messages.GetHistoryRequest`
- **🔐 Multi-Mode Support**: Works in all server modes with appropriate authentication

## Quick Start

```bash
# Send message with automatic entity resolution
curl -X POST "https://your-domain.com/mtproto-api/messages.SendMessage" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
        "params": {"peer": "@username", "message": "Hello from curl!"},
        "resolve": true
      }'

# Get message history with peer resolution
curl -X POST "https://your-domain.com/mtproto-api/messages.getHistory" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
        "params": {"peer": "me", "limit": 10},
        "resolve": true
      }'
```

**Endpoint**: `POST /mtproto-api/{method}` (alias: `POST /mtproto-api/v1/{method}`)

## Advanced Features

- **Case-insensitive method names**: Accepts `messages.getHistory`, `messages.GetHistory`, or `messages.GetHistoryRequest`
- **Entity resolution**: Optional automatic resolution of usernames, IDs, and phone numbers to proper Telegram entities
- **Safety guardrails**: Dangerous methods blocked by default (e.g., `account.DeleteAccount`, `messages.DeleteHistory`)
- **Multi-mode support**: Works in all server modes with appropriate authentication

## Request Format

```json
{
  "params": { "peer": "@durov", "limit": 5 },
  "params_json": "{...}",
  "resolve": true,
  "allow_dangerous": false
}
```

### Parameters

- **`params`**: Object with method parameters (preferred)
- **`params_json`**: JSON string with method parameters (alternative)
- **`resolve`**: Boolean to enable automatic entity resolution (default: false)
- **`allow_dangerous`**: Boolean to allow dangerous methods (default: false)

## Server Mode Behavior

- **stdio, http-no-auth**: Proceeds without Bearer token
- **http-auth**: Requires `Authorization: Bearer <token>`; missing/invalid returns 401 JSON error

## Examples

### Basic Message Operations

```bash
# Send message with entity resolution
curl -X POST "https://your-domain.com/mtproto-api/messages.SendMessage" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
        "params": {"peer": "me", "message": "Hello from MTProto API"},
        "resolve": true
      }'

# Get message history with automatic peer resolution
curl -X POST "https://your-domain.com/mtproto-api/messages.getHistory" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
        "params": {"peer": "@telegram", "limit": 3},
        "resolve": true
      }'

# Forward messages with list resolution
curl -X POST "https://your-domain.com/mtproto-api/messages.ForwardMessages" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
        "params": {
          "from_peer": "@sourceChannel",
          "to_peer": "me",
          "id": [12345, 12346]
        },
        "resolve": true
      }'
```

### User and Chat Operations

```bash
# Get your own user information
curl -X POST "https://your-domain.com/mtproto-api/users.GetFullUser" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
        "params": {"id": {"_": "inputUserSelf"}}
      }'

# Get chat information
curl -X POST "https://your-domain.com/mtproto-api/channels.GetFullChannel" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
        "params": {"channel": {"_": "inputChannel", "channel_id": 123456, "access_hash": 0}},
        "resolve": true
      }'
```

### Advanced Operations

```bash
# Get dialogs (chat list)
curl -X POST "https://your-domain.com/mtproto-api/messages.GetDialogs" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
        "params": {"limit": 20}
      }'

# Search messages globally
curl -X POST "https://your-domain.com/mtproto-api/messages.SearchGlobal" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
        "params": {"q": "hello", "limit": 10}
      }'

# Get contacts
curl -X POST "https://your-domain.com/mtproto-api/contacts.GetContacts" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
        "params": {"hash": 0}
      }'
```

## Entity Resolution

When `resolve: true` is set, the bridge automatically resolves:

- **Usernames**: `@username` → proper input entity
- **Numeric IDs**: `123456789` → proper input entity  
- **Channel IDs**: `-1001234567890` → proper input entity
- **Phone numbers**: `+1234567890` → proper input entity
- **Special identifiers**: `me` → `inputPeerSelf`

### Resolution Examples

```bash
# These all work with resolve: true
{"peer": "@durov"}           # Username
{"peer": "me"}               # Saved Messages
{"peer": 123456789}          # User ID
{"peer": "-1001234567890"}   # Channel ID
{"peer": "+1234567890"}      # Phone number
```

## Safety Features

### Dangerous Method Protection

Certain methods are blocked by default for safety:

- `account.DeleteAccount`
- `messages.DeleteHistory`
- `channels.DeleteChannel`
- `contacts.DeleteContacts`

To use dangerous methods, explicitly set `allow_dangerous: true`:

```bash
curl -X POST "https://your-domain.com/mtproto-api/messages.DeleteHistory" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
        "params": {"peer": "me", "max_id": 0},
        "allow_dangerous": true
      }'
```

## Response Format

### Success Response
```json
{
  "ok": true,
  "result": {
    // Telegram API response data
  }
}
```

### Error Response
```json
{
  "ok": false,
  "error": "Error description",
  "error_type": "ErrorType",
  "operation": "mtproto_api_call"
}
```

## Error Handling

### HTTP Status Codes
- **200**: Success
- **400**: Bad request (invalid parameters)
- **401**: Unauthorized (missing/invalid Bearer token)
- **403**: Forbidden (dangerous method blocked)
- **500**: Internal server error

### Common Errors

**Invalid method name:**
```json
{
  "ok": false,
  "error": "Unknown method: invalidMethod",
  "error_type": "MethodNotFound",
  "operation": "mtproto_api_call"
}
```

**Missing authentication:**
```json
{
  "ok": false,
  "error": "Bearer token required for HTTP_AUTH mode",
  "error_type": "AuthenticationRequired",
  "operation": "mtproto_api_call"
}
```

**Dangerous method blocked:**
```json
{
  "ok": false,
  "error": "Dangerous method blocked. Set allow_dangerous=true to override.",
  "error_type": "DangerousMethodBlocked",
  "operation": "mtproto_api_call"
}
```

## Integration Examples

### Python Integration
```python
import requests
import json

def call_mtproto(method, params, token, resolve=True):
    url = f"https://your-domain.com/mtproto-api/{method}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    data = {
        "params": params,
        "resolve": resolve
    }
    
    response = requests.post(url, headers=headers, json=data)
    return response.json()

# Example usage
result = call_mtproto("messages.SendMessage", {
    "peer": "@durov",
    "message": "Hello from Python!"
}, "your_token_here")
```

### JavaScript Integration
```javascript
async function callMTProto(method, params, token, resolve = true) {
    const response = await fetch(`https://your-domain.com/mtproto-api/${method}`, {
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            params,
            resolve
        })
    });
    
    return await response.json();
}

// Example usage
const result = await callMTProto("messages.SendMessage", {
    peer: "@durov",
    message: "Hello from JavaScript!"
}, "your_token_here");
```

## Best Practices

### Security
- Always use HTTPS in production
- Keep Bearer tokens secure and rotate regularly
- Be cautious with `allow_dangerous: true`
- Monitor usage through health endpoints

### Performance
- Use entity resolution sparingly for better performance
- Batch operations when possible
- Implement proper error handling and retries
- Monitor rate limits and implement backoff strategies

### Error Handling
- Always check response status codes
- Implement retry logic for transient failures
- Log errors for debugging and monitoring
- Handle authentication failures gracefully
