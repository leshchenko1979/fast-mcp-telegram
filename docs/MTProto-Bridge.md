# 🌐 HTTP-MTProto Bridge

**Direct curl access to any Telegram API method** - The server provides a powerful HTTP endpoint that allows you to execute any Telegram MTProto method directly via curl or HTTP requests.

## Key Benefits

- **🔄 Any Method**: Execute any Telegram API method not covered by MCP tools
- **🔧 Method Normalization**: Automatic conversion of method names to proper format
- **🛡️ Safety Guardrails**: Dangerous methods blocked by default with opt-in override
- **🌍 Entity Resolution**: Optional automatic resolution of usernames, IDs, and phone numbers
- **🔧 Case Insensitive**: Accepts `messages.getHistory`, `messages.GetHistory`, or `messages.GetHistoryRequest`
- **🔐 Multi-Mode Support**: Works in all server modes with appropriate authentication
- **⚡ Unified Implementation**: Same core logic as MCP tool with HTTP-specific defaults

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
- **Method name normalization**: Automatically converts method names to proper Telegram API format
- **Automatic TL object construction**: Builds complex Telegram objects from JSON dictionaries using `"_"` keys
- **Case-insensitive type lookup**: `inputmediatodo` → `InputMediaTodo` automatically
- **Recursive object construction**: Handles deeply nested structures (todo lists, polls, rich media)
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

## Automatic TL Object Construction

The MTProto bridge automatically constructs complex Telegram TL objects from JSON dictionaries. Use the `"_"` key to specify the object type - the bridge handles the rest!

### Simple Example

```bash
# Send a message with formatted text
curl -X POST "https://your-domain.com/mtproto-api/messages.SendMessage" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
        "params": {
          "peer": "me",
          "message": "Hello!",
          "entities": [
            {
              "_": "messageEntityBold",
              "offset": 0,
              "length": 5
            }
          ]
        },
        "resolve": true
      }'
```

### Complex Example: Todo List

```bash
# Create a todo list (automatic object construction)
curl -X POST "https://your-domain.com/mtproto-api/messages.sendMedia" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
        "params": {
          "peer": "me",
          "media": {
            "_": "InputMediaTodo",
            "todo": {
              "_": "TodoList",
              "title": {
                "_": "TextWithEntities",
                "text": "My Todo List",
                "entities": []
              },
              "list": [
                {
                  "_": "TodoItem",
                  "id": 1,
                  "title": {
                    "_": "TextWithEntities",
                    "text": "Complete project documentation",
                    "entities": []
                  }
                },
                {
                  "_": "TodoItem",
                  "id": 2,
                  "title": {
                    "_": "TextWithEntities",
                    "text": "Review code changes",
                    "entities": []
                  }
                }
              ],
              "others_can_append": true,
              "others_can_complete": false
            }
          },
          "message": "Check out my new todo list!",
          "random_id": 1234567890123456789
        },
        "resolve": true
      }'
```

### Features

- **Automatic Construction**: Objects with `"_"` key are automatically built
- **Case-Insensitive**: `inputmediatodo`, `INPUTMEDIATODO`, `inputMediaTodo` all work
- **Nested Objects**: Handles deeply nested structures recursively
- **List Processing**: Arrays of objects are processed automatically
- **Parameter Matching**: Uses constructor signatures to match JSON keys

### Common TL Object Types

- `InputMediaTodo` - Todo lists and checklists
- `InputMediaPoll` - Polls and quizzes
- `InputMediaPhoto` - Photo uploads with captions
- `InputMediaDocument` - File and document uploads
- `TextWithEntities` - Rich text with formatting
- `MessageEntityBold/Italic/Url/etc.` - Text formatting entities
- `InputPeerUser/Channel/Chat` - Peer references
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

## Multi-bot via Bearer Tokens

The server supports multiple bots by issuing one Bearer token per bot. Each bot gets its own session file and can only use the MTProto bridge (high-level tools are disabled for bots).

### Bot Setup

Create a bot session using the CLI setup tool:

```bash
# Create a bot session (replace with your bot token from BotFather)
python -m src.cli_setup --api-id <your_api_id> --api-hash <your_api_hash> --bot-token <bot_token_from_botfather>

# The command will print a Bearer token - this identifies your bot
# Example output:
# 🔑 Bearer Token: abc123def456...
# 🤖 Bot setup complete! You can now use the MTProto bridge:
#    - Use /mtproto-api/... endpoints for bot operations
#    - High-level tools (search, send_message, etc.) are disabled for bots
```

### Using Bot Sessions

Each bot session is identified by its unique Bearer token. Use this token in the Authorization header:

```bash
# Use the bot via MTProto bridge with the printed Bearer token
curl -X POST "https://your-domain.com/mtproto-api/messages.SendMessage" \
  -H "Authorization: Bearer <bot-server-token>" \
  -H "Content-Type: application/json" \
  -d '{
        "params": {"peer": "@yourchannel", "message": "Hello from bot!"},
        "resolve": true
      }'
```

### Bot Limitations

Bot accounts have the following restrictions:

- **Bridge Only**: Only `/mtproto-api/...` endpoints and the `invoke_mtproto` tool are available
- **No High-level Tools**: `search_messages`, `send_message`, `find_chats`, etc. are disabled for bots
- **Bot Account Restrictions**: Standard Telegram bot limitations apply (cannot message arbitrary users, limited search capabilities, etc.)
- **Session Isolation**: Each bot has its own session file (`{token}.session`) and Bearer token

### Multiple Bots

To use multiple bots:

1. Create a separate session for each bot using `--bot-token`
2. Each bot gets its own unique Bearer token
3. Use the appropriate Bearer token for each bot in your requests
4. Each bot operates independently with its own session

```bash
# Bot 1
python -m src.cli_setup --api-id <id> --api-hash <hash> --bot-token <bot1_token>
# Bearer Token: token1_abc123...

# Bot 2
python -m src.cli_setup --api-id <id> --api-hash <hash> --bot-token <bot2_token>
# Bearer Token: token2_def456...

# Use Bot 1
curl -X POST "https://your-domain.com/mtproto-api/messages.SendMessage" \
  -H "Authorization: Bearer token1_abc123..." \
  -H "Content-Type: application/json" \
  -d '{"params": {"peer": "@channel1", "message": "From Bot 1"}}'

# Use Bot 2
curl -X POST "https://your-domain.com/mtproto-api/messages.SendMessage" \
  -H "Authorization: Bearer token2_def456..." \
  -H "Content-Type: application/json" \
  -d '{"params": {"peer": "@channel2", "message": "From Bot 2"}}'
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
