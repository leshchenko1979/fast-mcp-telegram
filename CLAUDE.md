# fast-mcp-telegram

Canonical GitHub repository: https://github.com/leshchenko1979/fast-mcp-telegram

Canonical Python package: `fast-mcp-telegram` on PyPI (https://pypi.org/project/fast-mcp-telegram/).

Canonical MCP registry name: `io.github.leshchenko1979/fast-mcp-telegram`

**Owner order 2026-09-26: the `leshchenko1979` account is the canonical
location.** This reverses the guidance that stood here, which was written while
that account was suspended and told agents to avoid its owner name on every
surface. The account is live again and now carries origin, CI, the issue tracker
and all current pushes.

The previously used owner account is superseded: do not push to it, file against
it, or use its owner in new links, image names or registry manifests. Which
listings and packages still exist under it, and which duplicates still need
deprecating, is recorded in [docs/published-resources.md](docs/published-resources.md).

Repository identity and published artifacts are separate things: the GHCR
packages under both owners stay pullable, and both owners' MCP registry and
Glama listings are live, so a duplicate listing is deprecated in its own console
rather than assumed gone.

PyPI remains a stable pointer regardless of which GitHub owner is canonical.

Telegram MCP server (stdio, http-no-auth, http-auth). Full setup, ACL matrix, and dev workflow: [CONTRIBUTING.md](CONTRIBUTING.md).

## Session Corrections

### 2026-05-27
- **Issue**: Tried ACL live testing via Cursor MCP (`telegram-dev` or http-auth URL with fixed `Authorization`)
  - **Correct approach**: ACL is not viable through Cursor MCP (stdio has no ACL; URL MCP uses a fixed bearer; stale MCP subprocesses). Use `pytest tests/test_session_acl.py tests/test_mcp_tool_acl_integration.py`, HTTP curl against a local http-auth server, and [`scripts/acl_mcp_smoke.sh`](scripts/acl_mcp_smoke.sh) (reads bearer tokens from `acl.dev.yaml`, not hardcoded placeholders) — see [CONTRIBUTING.md § ACL development and testing](CONTRIBUTING.md#acl-development-and-testing-not-via-cursor-mcp)
- **Issue**: Started http-auth ACL server from wrong cwd, or `source .env.local` in zsh for `MTPROTO_PROXY`
  - **Correct approach**: Start the server from the **project root** so Python loads `.env` / `.env.local` via dotenv; do not `source .env.local` in zsh — proxy URLs with `&` break shell parsing
- **Issue**: Assumed ACL applies in stdio or without per-bearer sessions
  - **Correct approach**: ACL enforces only with `SERVER_MODE=http-auth` and `ACL_ENABLED=true`; each bearer in `acl.dev.yaml` needs a matching `{token}.session` via `http://127.0.0.1:8765/setup`
- **Issue**: Expected `connection.py` stdio fix without restarting Cursor MCP
  - **Correct approach**: After changing server code used by **telegram-dev**, restart **telegram-dev** in Cursor’s MCP panel — stale subprocess keeps old behavior
- **Issue**: Risk of committing real ACL bearer tokens
  - **Correct approach**: Keep `acl.dev.yaml` gitignored; never commit real bearer tokens (template only: `acl.dev.yaml.example`)
- **Issue**: "Repeat the sourcery-pr-cycle" interpreted as running another full PR → Sourcery → fix loop
  - **Correct approach**: User may mean publish/commit the skill to master, not re-execute the review cycle. Confirm intent when ambiguous.
- **Issue**: Treated phase closeout as blocked until all follow-up PRs merge, or assumed phase 1 code cannot land on master while follow-ups are open
  - **Correct approach**: Phase 1 code can be on master while follow-up PRs (e.g. #56) remain open; closeout means merge all **blocking** follow-ups first, not every open PR.
- **Issue**: Posted Telegram release announcement before release CI finished
  - **Correct approach**: After `gh release create`, verify CI/checks are green on the release tag or master commit (`gh run list`, `gh release view`); do not post Telegram until release is published **and** CI is green unless the user explicitly overrides — see [release-notes skill](.cursor/skills/release-notes/SKILL.md)
