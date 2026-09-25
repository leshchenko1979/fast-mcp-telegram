# AGENTS.md — fast-mcp-telegram

## Operator Preferences

- **Use `pg_query` tool** for any database queries against the telemetry collector's PostgreSQL. This is the preferred and only way to inspect the telemetry database — do not use bash + psql or any other method.
- **Use `grep_docs` tool** for searching library and framework documentation.
- **Use the built-in `grep` tool for code analysis in this repo** — symbol search, function definitions, callers, impact analysis. There is no symbol-index tool for Python here: the fleet's codegraph indexer was removed 2026-09-14, and `memory_search scope="external"` indexes only `/root/opencrabs/src/**/*.rs`, so it cannot see this repository's code. Raw `grep` over the tree is the correct instrument, not a fallback.
