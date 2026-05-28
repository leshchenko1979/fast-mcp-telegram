# Published Resources

This file tracks where **fast-mcp-telegram** has been published or listed, with status and links.

## Published ✅

| Resource | URL | Status | Notes |
|----------|-----|--------|-------|
| **PyPI** | https://pypi.org/project/fast-mcp-telegram/ | ✅ Live | `pip install fast-mcp-telegram` |
| **Glama** | https://glama.ai/mcp/servers/leshchenko1979/fast-mcp-telegram | ✅ Live | Badge in README |
| **Docker (GHCR)** | `ghcr.io/leshchenko1979/fast-mcp-telegram:*` | ✅ Live | Published alongside releases |
| **RemoteMCPList** | https://github.com/remotemcplist/servers/issues/22 | ✅ Submitted | GitHub issue #22 created |
| **ToolSDK Registry** | https://github.com/toolsdk-ai/toolsdk-mcp-registry/pull/324 | ✅ PR #324 | Added `fast-mcp-telegram.json` to registry |

## Submitted — Awaiting Review / Merge ⏳

| Resource | URL | Status | Notes |
|----------|-----|--------|-------|
| **awesome-mcp-servers** | https://github.com/punkpeye/awesome-mcp-servers/pull/7019 | ⏳ PR pending | Awaiting merge by @punkpeye |
| **MCP.Directory** | https://mcp.directory | ❌ Form failed | Submit form requires authentication (Sign In) |
| **mcp.so** | https://mcp.so | ❌ Form failed | Submit form requires GitHub login |
| **MCPMarket** | https://mcpmarket.com/submit | ❌ Form failed | Submit form requires authentication |
| **MCPFind** | https://mcpfind.org/submit | ❌ Form failed | Submit requires GitHub auth / PR workflow |

## Failed — Blocks Automation ❌

| Resource | URL | Status | Notes |
|----------|-----|--------|-------|
| **Smithery** | https://smithery.ai/servers/fast-mcp-telegram | ❌ 404 | Was live at sing./server/; needs re-publish via URL or hosted Docker |
| **PulseMCP** | https://pulsemcp.com/servers | ❌ Blocked | Cloudflare blocks automated checks |
| **MCPForge** | https://mcpforge.org | ❌ Not a directory | Managed hosting service (like Smithery), not a listing directory |

## Requires User Action 🔲

| Resource | URL | Status | Notes |
|----------|-----|--------|-------|
| **Official MCP Registry** | https://registry.modelcontextprotocol.io | 🔲 Needs device auth | `mcp-publisher login github` prints device code — user must visit https://github.com/login/device and enter the code |
| **GitHub MCP Registry** | — | 🔲 Needs email | Requires email to `partnerships@github.com` — agent cannot send email |

## Adding a new listing

1. Submit the package to the registry/directory
2. Verify the listing is live
3. Add a row to the table above
4. Commit and push

## Updating listings

When a listing status changes (e.g. PR merged, listing removed), update this table accordingly.
