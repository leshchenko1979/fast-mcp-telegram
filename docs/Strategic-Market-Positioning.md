# Strategic Market Positioning

This page is the **project-maintained index** for market and architecture research about fast-mcp-telegram. It separates verified product facts from third-party analysis.

> **Third-party research:** Documents under [docs/research/](research/) are saved Gemini Deep Research output ([original share link](https://gemini.google.com/share/b1d8cb8b23c2), 2026-05-26). They are **not** official roadmaps, security audits, or legal/financial advice. Cross-check claims against [README.md](../README.md), [SECURITY.md](../SECURITY.md), and [docs/Tools-Reference.md](Tools-Reference.md).

## Verified current capabilities (2026-05-26)

Facts below match the repository at the time of the documentation review.

### MCP tools (8)

| Tool | Purpose |
| --- | --- |
| `search_messages_globally` | Cross-chat message search |
| `get_messages` | Browse, search, fetch by IDs, or load replies in one chat |
| `send_message` | Send text or media to a chat |
| `edit_message` | Edit an existing message |
| `find_chats` | Find chats by query, folder, or activity dates |
| `get_chat_info` | Profile and metadata for one chat or user |
| `send_message_to_phone` | Send to a phone number with optional contact auto-create |
| `invoke_mtproto` | Raw MTProto with dangerous-method guardrails |

See [Tools-Reference.md](Tools-Reference.md) for parameters and behavior.

### Server modes (3)

| Mode | Auth | Use case |
| --- | --- | --- |
| `stdio` | None | Local MCP clients (Cursor, Claude Desktop) |
| `http-no-auth` | None | Local HTTP development |
| `http-auth` | Bearer token | Production multi-user remote hosting |

Configured in [src/config/server_config.py](../src/config/server_config.py). Documented in [Installation.md](Installation.md).

### Authentication and sessions

- Per-user Bearer tokens (256-bit) with browser web setup ([Installation.md](Installation.md#web-setup-interface))
- Session files at `~/.config/fast-mcp-telegram/{token}.session`
- LRU session cache (`MAX_ACTIVE_SESSIONS`) in [src/client/connection.py](../src/client/connection.py)
- URL-based auth for headerless clients: `/v1/url_auth/{token}/mcp/...` ([SECURITY.md](../SECURITY.md))
- **Scope:** a valid Bearer token grants **full access** to that Telegram account — **unless** opt-in session ACL is enabled and the token has an entry in `acl.yaml` ([SECURITY.md](../SECURITY.md#opt-in-session-acl-http-auth))

### Session ACL (shipped, opt-in)

| Control | Behavior |
| --- | --- |
| Enable | `ACL_ENABLED=true` + config file (default `{session_directory}/acl.yaml`) |
| Unlisted tokens | Full account access (backward compatible) |
| Listed tokens | Chat whitelist, optional read-only, optional global search block |

See [research/acl-design-brief.md](research/acl-design-brief.md) and [Roadmap.md](Roadmap.md).

### Security (shipped)

| Area | Behavior |
| --- | --- |
| Local file paths | Allowed in **all transport modes** — inlined from disk as data: URIs |
| HTTP modes | Local paths inlined automatically; URL downloads with SSRF protection |
| URL downloads | SSRF protection, size limits, redirect blocking ([SECURITY.md](../SECURITY.md), [src/tools/messages/security.py](../src/tools/messages/security.py)) |
| Attachments | Ticketed streaming at `GET /v1/attachments/{uuid}/{filename}` ([src/server_components/attachment_routes.py](../src/server_components/attachment_routes.py)) |
| Bot sessions | Non-bridge tools blocked ([src/server_components/bot_restrictions.py](../src/server_components/bot_restrictions.py)) |

**Not shipped:** directory sandbox allowlists, input/output prompt-injection scanners. Per-chat ACL is **opt-in** when `ACL_ENABLED=true` ([SECURITY.md](../SECURITY.md)).

### Other shipped features

- HTTP-MTProto bridge: `POST /mtproto-api/{method}` — [MTProto-Bridge.md](MTProto-Bridge.md)
- Premium voice transcription in message flows — [Tools-Reference.md](Tools-Reference.md)
- Multi-account tool prefix (`PREFIX_MCP_TOOLS_WITH_ACCOUNT`) — [Installation.md](Installation.md#multi-account-mcp-tool-prefix)
- Health endpoint `/health` — [src/server_components/health.py](../src/server_components/health.py)
- Docker image (GHCR) with `traefik-public` network; Traefik router labels are manual per [Installation.md](Installation.md)
- Distribution: `uvx`, PyPI, Docker

### Known gaps vs competitors (research summary)

| Capability | fast-mcp-telegram today | Notable alternative |
| --- | --- | --- |
| Per-chat ACL | Opt-in (`ACL_ENABLED`) | mcp-telegram (Prgebish) — default-deny always on |
| Local SQLite message cache | Not implemented | telegram-mcp-server (kfastov) — background sync |
| Enterprise IdP / OAuth2 | Not implemented | StackOne — managed OAuth |

## Research documents (third-party)

| Document | Contents |
| --- | --- |
| [Roadmap.md](Roadmap.md) | Official product roadmap |
| [research/acl-operator-research.md](research/acl-operator-research.md) | ACL competitor audit and personas |
| [research/gemini-competitive-analysis.md](research/gemini-competitive-analysis.md) | MCP/Telegram landscape, competitor table, ecosystem risks |
| [research/gemini-strategy-monetization.md](research/gemini-strategy-monetization.md) | Aspirational positioning and monetization hypotheses |
| [research/gemini-roadmap-proposal.md](research/gemini-roadmap-proposal.md) | Proposed features, phase timeline (planned vs shipped) |

## See also

- [README.md](../README.md) — features and quick start
- [SECURITY.md](../SECURITY.md) — auth model and file security
- [Installation.md](Installation.md) — deployment and configuration
- [Tools-Reference.md](Tools-Reference.md) — tool API reference
- [MTProto-Bridge.md](MTProto-Bridge.md) — HTTP-MTProto bridge
