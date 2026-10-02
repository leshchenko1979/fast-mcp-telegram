# Discoverability Plan

## Problem

When a user searches for "telegram mcp" on any registry, **fast-mcp-telegram does not appear** in results on the biggest indexes.

## Owner migration (2026-09-26)

**The canonical owner is `leshchenko1979`** (owner order 2026-09-26), replacing
`alexeyleshchenko` — whose repository has been stale since 2026-08-21 and holds no
commits the canonical repo lacks.

Everything below dated 2026-06-18 is preserved as the history it is: those
sessions genuinely published under the then-canonical owner, and rewriting them
would erase the record of how each listing was created. What changes is which
owner is canonical from here, and what still needs doing externally.

| Surface | State after migration | Action owed |
|---------|----------------------|-------------|
| Repo URLs, image names, manifests | ✅ Migrated in-repo | None |
| Official MCP Registry | ✅ Manifest now names the canonical entry | **Republish** — both owners are ACTIVE entries; the canonical one carries up to v0.36.0 while the superseded one carries v0.44.1 |
| Glama | ✅ Badge and `glama.json` now name the canonical listing | **Deprecate** the duplicate listing in Glama admin |
| GHCR | ✅ Defaults now name the canonical owner | None — both owners' packages stay pullable |
| Superseded GitHub repo | Still exists, unarchived | Owner's call — deleting or archiving it is not something this repo can do |

Note on Smithery: its namespace is `leshchenko` (neither account name), so this
migration does not touch it.

## Current Status (2026-06-18 verified)

| Registry | Status | Search visibility | Action needed |
|----------|--------|------------------|---------------|
| **PyPI** | ✅ v0.35.0 | ✅ `pip install fast-mcp-telegram` | Done |
| **Official MCP Registry** | ✅ Published | ✅ Canonical entry `io.github.leshchenko1979/fast-mcp-telegram` (published 2026-06-18 under the then-canonical owner as `io.github.alexeyleshchenko/fast-mcp-telegram`; renamed in-repo 2026-09-26) | Republish so the canonical entry carries the current version |
| **Smithery** | ✅ Live | ⚠️ Not in search results yet | All 8 tools indexed in API. May need indexing time or metadata improvements. |
| **Glama** | ⏳ Submitted for review | ❌ `tools:[]` | User submitted connector. Awaiting Glama review to index tools. |
| **awesome-mcp-servers** | ✅ MERGED (PR #7019) | ✅ Discoverable | Done |
| **ToolSDK Registry** | ✅ MERGED (PR #324) | ✅ Discoverable | Done |
| **mcp.so** | ✅ 200 (direct URL) | ⚠️ Site search broken | Site issue, not ours |
| **MCP.Directory** | ✅ Submitted | ⏳ Pending | Auto-pulls from GitHub within 24h |
| **RemoteMCPList** | ⏳ Issue #22 open | ⏳ Pending | Wait |

## What Changed (2026-06-17/18 session)

### Official MCP Registry — unblocked and published
- **Blocker:** Expired GitHub JWT token, Mac Chrome had no GitHub session
- **Fix:** User logged into GitHub on Mac Chrome → `mcp-publisher login github` device code flow → authorized → `mcp-publisher publish server.json`
- **Extra requirement:** Registry validation demands `mcp-name: io.github.alexeyleshchenko/fast-mcp-telegram` in the PyPI README. Added to README.md, bumped to v0.35.0, published to PyPI via GitHub Release, then re-published to registry.
- **Result:** ✅ Published as `io.github.alexeyleshchenko/fast-mcp-telegram`

### Smithery — re-published
- **Blocker:** Listing was 404 (namespace deleted or expired)
- **Fix:** Created new API key via browser CDP (Mac Chrome → smithery.ai/console/api-keys), published via CLI: `smithery publish "https://tg-mcp.l1979.ru/v1/mcp" -n "leshchenko/fast-mcp-telegram"`
- **Namespace:** `leshchenko` (not `leshchenko1979`)
- **Result:** ✅ Live at `smithery.ai/servers/leshchenko/fast-mcp-telegram`, all 8 tools in API

### Glama — user submitted
- User submitted connector for review directly on Glama
- Awaiting Glama review — once approved, tools should be indexed and search visibility should follow

## Remaining Blockers

### 1. Smithery search visibility
Our server doesn't appear in search results for "telegram" (top hit is "Telegram-bot" by node2flow with 121 uses). Possible causes:
- **Indexing delay** — republished < 24h ago
- **Zero usage** — search ranking likely factors in usage count (we have 0)
- **Metadata/tags** — may need `smithery.yaml` with better tags

### 2. Glama tools: []
Glama's scanner can't introspect our server because auth blocks it. User submitted for review — this should trigger manual indexing. If not, register as a connector at `glama.ai/mcp/connectors` pointing to the live endpoint.

### 3. RemoteMCPList issue #22
Still open. Not merged yet.

## Steps Already Done

- [x] Updated `published-resources.md` with actual statuses
- [x] Updated `server.json` to schema 2025-12-11 with v0.35.0
- [x] Added `mcp-name:` to README.md for Official MCP Registry validation
- [x] Published v0.35.0 to PyPI (via GitHub Release + CI)
- [x] Published to Official MCP Registry via `mcp-publisher publish`
- [x] Re-published to Smithery via CLI with new API key
- [x] Updated BROWSER-CDP.md with Mac tunnel guidance and troubleshooting
- [x] User submitted connector for review on Glama
- [x] All 8 tools have TypedDict return types (not generic `dict`)
- [x] All 8 tools have MCP annotations (readOnlyHint, destructiveHint, etc.)
- [x] Server-card.json has full metadata with all 8 tools
- [x] MCP endpoint returns tools without auth

## Server-side improvements already in place

1. **Server-card.json** — Full metadata at `/.well-known/mcp/server-card.json` with all 8 tools
2. **No-auth tools/list** — The MCP endpoint returns tools without requiring Bearer token
3. **glama.json** — Rich metadata with categories, env vars, related servers
4. **server.json** — Updated to schema 2025-12-11 with correct version
5. **Output schemas** — All 8 tools have specific TypedDict return types
6. **Annotations** — All tools have MCP annotations
7. **awesome-mcp-servers** — Merged and discoverable
8. **ToolSDK Registry** — Merged and discoverable
