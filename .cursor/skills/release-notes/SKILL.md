---
name: Release Notes Generation
description: >-
  Mandatory fast-mcp-telegram release workflow. Use when the user says release,
  merge and release, bump version, tag, gh release, PyPI publish, or Telegram
  version announcement.
---

# Release Notes Generation

Mandatory workflow for fast-mcp-telegram releases. Release notes belong on GitHub only — never commit `RELEASE_NOTES*`, temp note files, or similar to git.

## Workflow overview

1. Memory bank + git on `master` → user-facing diff analysis
2. Update docs (section 3) if needed
3. Classify scope (section 4) → draft notes (section 5) → review gate when required
4. `uv version` → commit → tag → push → `gh release create` → `gh release view`
5. Verify CI/checks green on release tag or master commit (section 6 gate)
6. Telegram HTML (section 7) only after release is published **and** CI is green (or user explicitly overrides)

## 1. Context

**Memory bank** — completed work since last release:

```bash
cat .cursor/memory-bank/progress.md
cat .cursor/memory-bank/activeContext.md
```

Focus on dated entries; cross-check with git.

**Git since last major tag** (`X.Y.0`):

```bash
git tag --sort=-version:refname | grep -E '^[0-9]+\.[0-9]+\.0$' | head -1
git log --oneline <last-major-tag>..HEAD
git log --oneline --all --graph --decorate | head -40
```

Only include changes merged to **`master`** (memory bank may mention other branches). Merge memory bank summaries with git analysis. Prepare notes before creating the new tag.

## 2. User-facing analysis

End-user impact only:

```bash
git diff <previous-major-tag>..HEAD
git log --oneline <previous-major-tag>..HEAD
git show HEAD:<file>   # final state when needed
```

Treat commit messages as hints; validate against actual behavior. Describe what users can do, not implementation.

**Prioritization for notes:**

- **Primary**: new features, fixes, behavior changes
- **Omit**: refactoring and internal cleanup unless they are the only changes (still complete docs per section 3)
- **Grafana, telemetry, and ops dashboards** are internal/ops tooling — never user-facing. Omit from release notes unless they are the only changes.
- **Fixes vs new work**: Fixes that pertain to features introduced in **this** release go under **New Features** only — never under **Fixes**. **Fixes** = regressions in previously existing features or unrelated bugs. If a new feature has bugs, it's not a "fix" for users, it's just the feature being completed.
- **Dependencies**: User-visible stack milestones (e.g. FastMCP 3.x) go under **New Features**.

## 3. User-facing documentation

Before draft notes or version bump, document new/changed behavior on `master`:

| Location | What to update |
|----------|----------------|
| `README.md` | Features table (overview links if setup-related) |
| `docs/Installation.md` | config, env, deployment, auth flows |
| `docs/Tools-Reference.md` | tools, parameters, returns, flags |
| `.env.example` | new/renamed vars with short comments |
| MCP metadata | `description` / `Field(description=…)` in `mcp_tool_types.py`, `tools_register.py` |

```bash
git diff <previous-major-tag>..HEAD -- README.md docs/ .env.example src/server_components/mcp_tool_types.py src/server_components/tools_register.py
```

Update and commit (or include in the release PR) before publishing. Link to `docs/…` anchors on `master` in release notes when helpful.

## 4. Scope and review gate

| Single-feature (no approval wait) | Review required (post section 5 notes in a markdown code block; **wait** before `uv version` / `gh release create`) |
|-----------------------------------|----------------------------------------------------------------------------------------------------------------------|
| One primary user-facing theme since last tag | Multiple unrelated user-facing changes |
| Docs complete (section 3) | Release aggregates several features since last `X.Y.0` |
| Brief draft in chat while shipping | Ambiguous version or notes; user asked to review |

User may say **skip review** or **ship it** to override review-required cases.

Single-feature: draft with section 5, ship through section 6 without blocking on note approval. Review-required: paste notes as a markdown code block and stop until approved.

## 5. Release notes format

```markdown
<One short sentence: main value — NO VERSION NUMBERS in this line>

## New Features
- **`tool_name` / feature** - What users can now do (backticks for tools, params like `chat_id`)
- **Documentation** - Link to `docs/…` on `master` when setup/reference matters

## Fixes
- **Issue resolved** - What was broken and how it's fixed

This release <primary user-facing value>.

**Full Changelog**: https://github.com/leshchenko1979/fast-mcp-telegram/compare/<previous-major-tag>...<current-tag>
```

- Replace tag placeholders (e.g. `0.12.0`, `0.11.0`). Tags have **no** `v` prefix.
- Do **not** repeat the GitHub release title as the first body line.
- Omit **Fixes** section entirely if all changes are new features (including their post-release polish).
- Omit internal improvements when user-facing items exist.
- No emojis in GitHub notes. No file stats or implementation detail.
- Verify notes match code and section 3 docs before shipping.

## 6. Version bump and GitHub release

- **Never** hand-edit `[project].version` in `pyproject.toml` — **`uv version`** only. Do not edit `src/_version.py` (reads metadata / `pyproject.toml`).

```bash
uv version <version>
# or: uv version --bump patch | minor | major
```

Include `uv.lock` if it changed; run `uv lock` only when dependencies changed.

```bash
git add pyproject.toml uv.lock
git commit -m "chore: bump version to <version>"
git tag <version>
git push origin <branch> && git push origin <version>

gh release create <version> \
  --title "<short headline without version>" \
  --notes-file - <<'EOF'
<paste body from section 5 — no duplicate title line>
EOF
```

Or `--notes-file /path/to/notes.md` (temp file; do not commit).

```bash
gh release view <version>
```

**CI gate (required before Telegram):** After `gh release create`, confirm GitHub Actions / checks are green on the release tag or the `master` commit that tag points to:

```bash
gh release view <version>   # note target commit SHA
gh run list --commit <sha> --limit 10
# or: gh run list --branch master --limit 5
gh run watch <run-id>       # optional — wait for completion
```

Do **not** post Telegram until **both** (a) the GitHub release is published and (b) CI is green. User may explicitly override (e.g. **skip CI wait**, **post anyway**).

## 7. Telegram announcement

Only after section 6: GitHub release published **and** CI green (unless user explicitly overrides).

| Audience | `chat_id` | Language |
|----------|-----------|----------|
| English — “Telegram MCP and MTProto-HTTP Bridge” ([invite](https://t.me/+U_3CpNWhXa9jZDcy)) | `5131784155` | English |
| Russian — [t.me/mcp_telegram](https://t.me/mcp_telegram) | `mcp_telegram` or `2537965832` | Russian |

Use fixed `chat_id` values; do not rely on `find_chats` unless a target moved or posting fails with “chat not found”.

**Formatting**: `parse_mode="html"` only (not Markdown). Tags: `<b>`, `<i>`, `<code>`, `<a href="...">`. Escape `&`, `<`, `>` in literal text. Emojis OK in Telegram.

**Structure**: version header with date (e.g. `🚀 <b>fast-mcp-telegram 0.x.y</b> · YYYY-MM-DD`); feature highlights; release link `<a href="https://github.com/leshchenko1979/fast-mcp-telegram/releases/tag/0.x.y">…</a>`.

```bash
send_message chat_id=5131784155 parse_mode=html message="..."
send_message chat_id=mcp_telegram parse_mode=html message="..."
```

On `ChatWriteForbiddenError`, give the user the HTML to paste manually.
