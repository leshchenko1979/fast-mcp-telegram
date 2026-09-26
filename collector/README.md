# Telemetry Collector

Tiny ingestion HTTP server for anonymous feature-adoption telemetry
(ADR 0005).  Runs on Box 3 behind Traefik at
`fast-mcp-telegram-telemetry.l1979.ru/v1/event`.

## Architecture

One HTTP handler, one PostgreSQL INSERT per event.  That's it.

```
POST /v1/event  →  validate with dataclasses  →  rate-limit / dedup  →  psycopg2 INSERT
```

**Stack:**

| Layer | Choice | Why |
|-------|--------|-----|
| HTTP server | `http.server.ThreadingHTTPServer` (stdlib) | Single endpoint, no routing needed. Saves ~15–20 MB RSS vs FastAPI + uvicorn. |
| Validation | `dataclasses` + manual `__post_init__` | Stdlib, zero dependencies. Saved ~15-20 MB RSS by dropping pydantic-core (Rust .so). Constraints are explicit — no magic type coercion. |
| Database | `psycopg2-binary` | Sync, battle-tested, ships prebuilt manylinux wheels. Direct connection, no pool needed (single-threaded writer). |

### What was removed (overkill)

- **FastAPI** — adds starlette (~5 MB RSS) + pydantic duplication
- **uvicorn** — ASGI server with event loop overhead; we sync-handle requests in worker threads
- **asyncpg** — async-only; same connector overhead as psycopg2 but requires async plumbing
- **asyncio** — the collector is I/O-bound on one table; green threading is enough
- **pydantic v2** — pydantic-core Rust .so added ~15-20 MB RSS; replaced with stdlib ``dataclasses``

### Why `python:3-slim` (not alpine, not pinned)

| Base | Image size | libc | psycopg2-binary wheel | RSS |
|------|-----------|------|----------------------|-----|
| `python:3` (full) | ~1 GB | glibc | ✅ prebuilt | baseline |
| `python:3-slim` | ~130 MB | glibc | ✅ prebuilt | **identical** |
| `python:3-alpine` | ~55 MB | musl | ❌ builds from source | same interpreter, same RSS |

- **Alpine** has no psycopg2-binary wheel — pip falls back to `gcc + musl-dev + postgresql-dev` at build time, requiring a multi-stage Dockerfile.  musl's malloc is simpler (= possibly *more* RSS for some workloads) and introduces a non-glibc surface for debugging.
- **Full `python:3`** adds 850 MB of Debian build toolchain (gcc, dpkg-dev, headers) that never run at runtime.
- **Pinning to `3.12`** would prevent automatically receiving minor Python updates (performance fixes, security patches) on rebuild.  The collector has zero Python-version-specific code — `python:3` tracks the latest 3.x branch safely.

**Conclusion**: `python:3-slim` is the sweet spot for a container that depends on a native-C-extension library and has no version pinning requirements.

## Endpoints

### `GET /health`

```
→ 200 {"status": "ok", "service": "telemetry-collector"}
```

Used by Docker healthcheck and Traefik.

### `POST /v1/event`

```
→ 204 (stored) | 422 (validation error) | 429 (rate-limited)
```

Accepts the TelemetryPayload JSON schema defined in `app/models.py`:
`{v, iid, ts, started_at, ver, os, py, features, runtime, counters}`.

Rate limit: 100 events per instance_id per 24 hours (configurable).
Dedup: exact payload match within 5 minutes → silently ignored.

## Local Development

```bash
cd collector
docker compose -f docker-compose.dev.yml up --build
```

This starts:
- `telemetry-collector` on port 8000
- `telemetry-db` (PostgreSQL 16) on port 5433

Test it:

```bash
curl -s -o /dev/null -w '%{http_code}' http://localhost:8000/health
# → 200

curl -s -o /dev/null -w '%{http_code}' -X POST \
  -H 'Content-Type: application/json' \
  -d '{"v":1,"iid":"test","ts":2000000000,"started_at":1000000000,"ver":"0.1","os":"Linux","py":"3.12","features":{"a":true},"runtime":{"s":1},"counters":{"c":0}}' \
  http://localhost:8000/v1/event
# → 204
```

### Running tests

```bash
# unit tests (in-memory storage, no DB needed)
pytest collector/tests/ -v -m "not e2e"

# e2e tests (requires Postgres at localhost:5432, telemetry/telemetry/telemetry)
pytest collector/tests/test_e2e.py -v
```

CI runs both via `deploy-collector.yml` with a Postgres service container.

## PostgreSQL Schema

```sql
CREATE TABLE telemetry (
    id              BIGSERIAL PRIMARY KEY,
    received_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    instance_id     TEXT NOT NULL,
    payload         JSONB NOT NULL,
    payload_hash    TEXT NOT NULL,
    source_ip_hash  TEXT NOT NULL
);

CREATE INDEX idx_telemetry_instance_id  ON telemetry(instance_id);
CREATE INDEX idx_telemetry_received_at  ON telemetry(received_at);
CREATE INDEX idx_telemetry_payload_hash ON telemetry(payload_hash);
```

TTL: 90 days (configurable via `RETENTION_DAYS`).
Row cap: 10 million (configurable via `MAX_ROWS`).

## Deployment

Deployed via GitHub Actions (`.github/workflows/deploy-collector.yml`):

1. **Test** — unit + e2e against ephemeral Postgres service
2. **Build & push** — `ghcr.io/leshchenko1979/telemetry-collector:main`
3. **Deploy** — appleboy/ssh-action writes `docker-compose.yml` and `.env` to
   `/root/services/telemetry-collector` on Box 3, then runs
   `docker compose pull && docker compose up -d --wait`.

The deployment script also creates the PostgreSQL role and database
if they don't already exist (parsed from the `TELEMETRY_DSN` secret).

Traefik routes `Host(fast-mcp-telegram-telemetry.l1979.ru) + Path(/v1/event)`
to the collector.  Config lives in the `vds-servers` repo.

## Environment

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `TELEMETRY_DSN` | production | `postgres://telemetry:telemetry@localhost:5432/telemetry` | PostgreSQL connection string |
