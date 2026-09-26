# Published Resources

This file tracks where **fast-mcp-telegram** has been published or listed, with status and links.

## Identity migration (2026-09-26)

**The canonical owner is `leshchenko1979`** (owner order 2026-09-26). The
`alexeyleshchenko` account is superseded: its repository has been stale since
2026-08-21 and holds no commits the canonical repo lacks.

| Surface | State |
|---------|-------|
| GitHub repository | ✅ Migrated — `leshchenko1979/fast-mcp-telegram` carries origin, CI, issues and all pushes. The superseded copy still exists and is not archived. |
| GHCR packages | ✅ Migrated — both owners' packages remain pullable. |
| Repo URLs in docs and source | ✅ Migrated. |
| `server.json` manifest | ✅ Migrated — a republish is owed so the canonical registry entry carries the current version. |
| `glama.json` + README badge | ✅ Migrated — deprecating the duplicate listing is owed in Glama admin. |

**Repository identity and published artifacts are separate.** Renaming the repo
does not remove anything published under the old owner, so the rows below keep
naming that owner wherever it still has a live artifact. That is a record of what
exists, not a recommendation to use it.

### The collector build/pull mismatch (fixed 2026-09-26)

The collector workflow derived its build image from `github.repository_owner`
while its deploy step hardcoded the superseded owner's image into the compose
file it writes on the host. Two different repositories: the workflow built one
and pointed the host at the other.

What is **verified**: the last pre-fix run's workflow file carried the hardcoded
owner (`9c68def`, line 123, read via `git show`), and both images exist with
different build dates — canonical `2026-08-23T21:37:31Z`, superseded
`2026-08-07T15:04:45Z`.

What is **not** established: that the wrong image was ever actually running. The
container observed before the fix was already on the canonical image and had been
up about three weeks, and no collector workflow run occurred between 2026-08-23
and the fix — so whatever recreated it in between was not that workflow, and its
provenance is unknown. The mismatch was a latent defect that would have deployed
the stale image on the next collector change, not a demonstrated one.

The fix exports the image repository as a job output so the build tags and the
deploy pull consume one derivation and cannot drift again.

## Published ✅

| Resource | URL | Status | Notes |
|----------|-----|--------|-------|
| **PyPI** | https://pypi.org/project/fast-mcp-telegram/ | ✅ Live (v0.35.0) | `pip install fast-mcp-telegram` |
| **Glama** | https://glama.ai/mcp/servers/leshchenko1979/fast-mcp-telegram | ✅ Live | Canonical listing — claimed by its maintainer, 8 tools indexed, rated A. The superseded duplicate at https://glama.ai/mcp/servers/alexeyleshchenko/fast-mcp-telegram is also live and also rated A, but carries stale metadata and is unclaimed — deprecate it in Glama admin (Discord: https://glama.ai/discord). |
| **Docker (GHCR)** | `ghcr.io/leshchenko1979/fast-mcp-telegram:*` | ✅ Live | Published alongside releases. The superseded owner's package stays pullable, but nothing deploys it any more — see the collector note below. |
| **RemoteMCPList** | https://github.com/remotemcplist/servers/issues/22 | ⏳ Issue open | GitHub issue #22 — not yet merged |
| **ToolSDK Registry** | https://github.com/toolsdk-ai/toolsdk-mcp-registry/pull/324 | ✅ MERGED | PR #324 merged |
| **Official MCP Registry** | https://registry.modelcontextprotocol.io | ✅ Published | Canonical name: `io.github.leshchenko1979/fast-mcp-telegram`. BOTH owners are registered as ACTIVE entries — the canonical one carries up to v0.36.0 while the superseded `io.github.alexeyleshchenko/fast-mcp-telegram` carries v0.44.1 — so a republish is owed to bring the canonical entry current. The live remote `https://tg-mcp.l1979.ru/v1/mcp` is bound to the `leshchenko1979` entry, which is now the canonical name, so the binding that previously blocked the migration now works in its favour. |
| **mcp.so** | https://mcp.so/servers/678f0b7fc72dda6b377d9800 | ✅ 200 — search broken | Direct URL works but site search returns 404 (site issue, not ours) |
| **Smithery** | https://smithery.ai/servers/leshchenko/fast-mcp-telegram | ✅ Live | Re-published 2026-06-17 via CLI. Namespace: `leshchenko` (not `leshchenko1979`). API key: `553a7ea1-...` in Smithery console. All 8 tools indexed in API. Not yet in search results for "telegram" — may need indexing time. |

## Submitted — Awaiting Review / Merge ⏳

| Resource | URL | Status | Notes |
|----------|-----|--------|-------|
| **awesome-mcp-servers** | https://github.com/punkpeye/awesome-mcp-servers/pull/7019 | ✅ MERGED | PR #7019 merged by @punkpeye |
| **MCPFind** | https://github.com/MCPFind/mcp-find/pull/53 | ❌ Closed | MCPFind moved to automated curation — PR #53 closed without merge |
| **MCP.Directory** | https://mcp.directory | ✅ Submitted | "Server Submitted!" — auto-pulls metadata from GitHub, publishes within 24h |

## Failed — Blocks Automation ❌

| Resource | URL | Status | Notes |
|----------|-----|--------|-------|
| **MCPMarket** | https://app.mcpmarket.com/servers/fast-mcp-telegram | ❌ Dead end | Custom MCP deployments from GitHub require Pro plan — user declined |
| **PulseMCP** | https://pulsemcp.com/servers | ❌ Blocked | Cloudflare blocks automated checks |
| **MCPForge** | https://mcpforge.org | ❌ Not a directory | Managed hosting service (like Smithery), not a listing directory |

## Requires User Action 🔲

| Resource | URL | Status | Notes |
|----------|-----|--------|-------|
| **GitHub MCP Registry** | — | 🔲 Needs email | Requires email to `partnerships@github.com` — agent cannot send email |

## Adding a new listing

1. Submit the package to the registry/directory
2. Verify the listing is live
3. Add a row to the table above
4. Commit and push

## Updating listings

When a listing status changes (e.g. PR merged, listing removed), update this table accordingly.
