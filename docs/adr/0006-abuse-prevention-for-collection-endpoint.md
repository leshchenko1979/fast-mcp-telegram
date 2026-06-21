# ADR 0006: Abuse Prevention for the Open Telemetry Collection Endpoint

**Status:** proposed
**Date:** 2026-06-10

## Context

ADR 0005 defines an **anonymous** telemetry collection endpoint at `https://fast-mcp-telegram-telemetry.l1979.ru/v1/event`. There is no authentication — any client running the fast-mcp-telegram library can POST a heartbeat. This openness creates an attack surface.

### Risks

| Risk | Impact | Likelihood |
|------|--------|------------|
| **Disk fill** — attacker floods the endpoint with garbage payloads, filling PostgreSQL storage | Service degradation / disk-full crash on Box 3 | Medium — endpoint is public, no auth |
| **Data pollution** — attacker sends plausible-but-fake heartbeats with random instance_ids | Metrics become meaningless; maintainer cannot distinguish real adoption from noise | High — no auth + no cost to send |
| **DDoS** — attacker saturates the collector with high volume | Collection unavailable; data loss for real clients | Low — small target, but always possible |
| **Replay** — attacker captures a legitimate heartbeat and re-sends it many times | Inflated unique-instance counts, skewed aggregate numbers | Medium — payload has timestamps, can be validated |

### Constraints

- **No auth** — the endpoint must remain open so library users never need credentials
- **No new infra** — collector runs on Box 3 alongside existing services (already has Traefik + PostgreSQL)
- **Lightweight** — the collector must be fast enough to return 204 within a few hundred ms
- **No user impact** — rate limits must be generous enough that every legitimate client passes

## Decision — Multi-Layer Abuse Prevention

We layer four independent defences so no single bypass exposes the database:

```
Internet ──→ Traefik ──→ Collector App ──→ PostgreSQL
                │              │                 │
            body size       schema           row cap
            rate limit      dedup            TTL
            IP ban          inst. rate       alert
```

### Layer 1 — Traefik (Proxy)

Before the request reaches the collector application, Traefik enforces two filters:

**1a. `client_max_body_size 10k`**

Block oversized payloads at the proxy. A legitimate heartbeat is ~300–500 bytes. Setting the limit to 10 KB (~20× normal) allows room for v2 payload growth while preventing a 100 MB blob from reaching the collector or database.

Implemented as a Traefik middleware:

```yaml
# telemetry-buffering.yml
http:
  middlewares:
    telemetry-buffering:
      buffering:
        maxRequestBodyBytes: 10240  # 10 KB
```

**1b. Per-IP rate limit**

Traefik's `RateLimit` middleware enforces a leaky-bucket per IP:

```yaml
http:
  middlewares:
    telemetry-ratelimit:
      rateLimit:
        average: 20          # 20 requests/minute average
        burst: 5             # allow short bursts
        period: 1m
        sourceCriterion:
          ipStrategy:
            depth: 1         # use client IP, not X-Forwarded-For
```

20 req/min per IP = 28 800 requests/day. A legitimate instance sends one heartbeat every 6 hours (4/day). Even if an attacker uses all 20 req/min for 24 hours, that's ~8 MB/day of raw POST bodies before validation — harmless.

**Why not nginx?**

Box 3 uses Traefik, not nginx. All traffic goes through Traefik. Adding nginx just for telemetry would be a new service with SSL termination duplication. Traefik's middleware chain is sufficient.

### Layer 2 — Collector Application

The collector runs as a lightweight Python container on Box 3 using the existing `traefik-public` network. It validates every payload before touching PostgreSQL.

**2a. Schema validation**

Every request body is validated against a strict dataclass model **before** any database operation. Unknown fields cause an immediate 422 with no DB write.

```python
from __future__ import annotations

import time
from dataclasses import dataclass, field, asdict
from typing import Any, Literal


_FUTURE_DRIFT_SECONDS = 300        # 5 min clock-skew tolerance
_OLD_WINDOW_SECONDS = 7 * 24 * 3600  # 7 days


class ValidationError(Exception):
    """The payload failed schema or business-rule validation."""


@dataclass
class TelemetryPayload:
    """Schema for incoming anonymous telemetry events."""

    v: Literal[1]
    iid: str
    ts: int
    started_at: int
    ver: str
    os: str
    py: str
    features: dict[str, Any] = field(default_factory=dict)
    runtime: dict[str, int] = field(default_factory=dict)
    counters: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        errors: list[str] = []

        # --- v (Literal[1]) ---
        if self.v != 1:
            errors.append(f"v must be 1, got {self.v!r}")

        # --- iid ---
        if not isinstance(self.iid, str) or not self.iid:
            errors.append("iid must be a non-empty string")
        elif len(self.iid) > 128:
            errors.append(f"iid exceeds 128 chars ({len(self.iid)})")

        # --- ts ---
        if not isinstance(self.ts, int) or isinstance(self.ts, bool):
            errors.append("ts must be an integer")
        else:
            now = int(time.time())
            if self.ts > now + _FUTURE_DRIFT_SECONDS:
                errors.append(f"ts {self.ts} is {self.ts - now}s in the future")
            if self.ts < now - _OLD_WINDOW_SECONDS:
                errors.append(f"ts {self.ts} is {now - self.ts}s old")

        # --- started_at ---
        if not isinstance(self.started_at, int) or isinstance(self.started_at, bool):
            errors.append("started_at must be an integer")

        # --- ver / os / py string-length checks ---
        if not isinstance(self.ver, str) or not self.ver or len(self.ver) > 64:
            errors.append("ver must be a non-empty string ≤64 chars")
        if not isinstance(self.os, str) or len(self.os) > 128:
            errors.append("os must be a string ≤128 chars")
        if not isinstance(self.py, str) or len(self.py) > 32:
            errors.append("py must be a string ≤32 chars")

        # --- features ---
        if not isinstance(self.features, dict):
            errors.append("features must be a dict")

        # --- runtime / counters (dict[str, int] with non-negative values) ---
        for field_name, d in (("runtime", self.runtime), ("counters", self.counters)):
            if not isinstance(d, dict):
                errors.append(f"{field_name} must be a dict")
                continue
            for k, val in d.items():
                if not isinstance(val, int) or isinstance(val, bool):
                    errors.append(f"{field_name}.{k!r} must be int")
                    break
                if val < 0:
                    errors.append(f"{field_name}.{k!r} must be >= 0, got {val}")
                    break

        if errors:
            raise ValidationError("; ".join(errors))

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TelemetryPayload:
        """Construct and validate from a raw dict. Rejects extra keys."""
        known = set(cls.__dataclass_fields__)
        extra = set(data) - known
        if extra:
            raise ValidationError(
                f"Unexpected fields: {', '.join(sorted(extra))}"
            )
        return cls(**data)
```

Rationale:
- **No Pydantic dependency** — saves ~15–20 MB RSS from pydantic-core's Rust `.so`
- **`__post_init__`** replaces Pydantic validators — same strictness, no extra deps
- **`from_dict()`** with extra-keys check replaces `extra="forbid"` — attacker cannot inject unexpected fields
- **Manual type checks** replace `Field(ge=...)` on numerics — no negative counters, no impossible session counts
- **`iid` length filter** — max 128 chars; rejects obviously fake IDs
- **Timestamp range check** (±5 min clock skew, max 7 days old) — kills replay attacks
- **`Literal[1]`** enforced manually — only version 1 payloads accepted
- All validation errors are collected and reported at once rather than short-circuiting on the first failure

**2b. Per-instance_id rate limiting**

Even with per-IP limits, a distributed attacker (botnet) could send from many IPs with many fake instance_ids. The collector enforces a per-instance_id cap in the application layer:

```python
# Before DB insert: check recent count for this iid
SELECT COUNT(*) FROM telemetry_events
WHERE payload->>'iid' = $iid
  AND received_at > NOW() - INTERVAL '24 hours';
```

If the count exceeds `MAX_HEARTBEATS_PER_DAY` (configurable, default 100), return 204 without writing. This works even without a unique index on `iid` because the telemetry table is append-only.

100 heartbeats/day per instance is 25× the expected rate (4/day at 6-hour intervals). A real instance never hits this. A fake instance that somehow bypasses IP limits still caps at 100 writes/day.

**2c. Payload dedup (exact match)**

Check if identical payload already exists within the last hour:

```sql
SELECT 1 FROM telemetry_events
WHERE payload = $payload_jsonb
  AND received_at > NOW() - INTERVAL '1 hour'
LIMIT 1;
```

Catches replay of the exact same heartbeat body sent multiple times.

**2d. Reject empty/trivial payloads**

Empty body, `{}`, `null`, `[]` → 400 Bad Request before Pydantic validation.

### Layer 3 — PostgreSQL (Storage)

The database is the final defence. Even if Layers 1 and 2 are bypassed (e.g. a bug in schema validation allows a write), hard limits prevent disk exhaustion.

**3a. Row cap (hard ceiling)**

On every INSERT, the collector enforces a maximum row count:

```sql
-- Run after every successful insert
DELETE FROM telemetry_events
WHERE id IN (
  SELECT id FROM telemetry_events
  ORDER BY received_at DESC
  OFFSET 10000000  -- 10M row ceiling
);
```

This is a simple `SELECT ... OFFSET` + `DELETE`. With `received_at` indexed, PostgreSQL plans this efficiently. The 10M ceiling at ~500 bytes/row = ~5 GB max storage.

**Why not PostgreSQL row-level security or triggers?**
- Triggers add complexity and can be bypassed by direct DB access
- The app-level DELETE is explicit, auditable, and runs only when needed
- If the collector container is re-deployed or the application logic is bypassed, the row cap in the application won't apply. To guard against this, also add a **PostgreSQL-side trigger** as a safety net:

```sql
CREATE OR REPLACE FUNCTION trg_enforce_telemetry_row_cap()
RETURNS TRIGGER AS $$
BEGIN
  DELETE FROM telemetry_events
  WHERE id IN (
    SELECT id FROM telemetry_events
    ORDER BY received_at DESC
    OFFSET 10000000
  );
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER enforce_telemetry_row_cap
  AFTER INSERT ON telemetry_events
  FOR EACH STATEMENT
  EXECUTE FUNCTION trg_enforce_telemetry_row_cap();
```

The trigger fires once per INSERT statement (not per row), so it adds negligible overhead during normal operation (where the cap is never reached).

**3b. TTL cleanup**

A cron job (or the collector's own startup) runs periodically:

```sql
DELETE FROM telemetry_events
WHERE received_at < NOW() - INTERVAL '90 days';
```

This runs independently of the row cap. A 90-day retention window means even a worst-case attack auto-recovers once the TTL job catches up. Run via a cron on Box 3 or as a periodic task in the collector container.

**3c. Dedicated database**

Telemetry data lives in its own database (`telemetry`, not the default `postgres` database) with its own table. This isolates telemetry storage from other services — even if the telemetry table fills, the other databases on the same PostgreSQL instance remain functional.

```sql
CREATE DATABASE telemetry;
\c telemetry
CREATE TABLE telemetry_events (
  id          BIGSERIAL PRIMARY KEY,
  payload     JSONB NOT NULL,
  received_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

**3d. Storage alerting**

A cron job on Box 3 checks the telemetry database file size daily:

```bash
#!/bin/sh
DATA_DIR=$(docker volume inspect telemetry_data --format '{{.Mountpoint}}' 2>/dev/null)
[ -z "$DATA_DIR" ] && exit 0
SIZE_MB=$(du -sm "$DATA_DIR" | cut -f1)
if [ "$SIZE_MB" -gt 4000 ]; then  # 4 GB → ~80% of 5 GB quota
  # Send alert (e.g. via telegram_send or Gatus)
  echo "Telemetry DB at ${SIZE_MB}MB — approaching 5GB quota"
fi
```

### Layer 4 — OS / Filesystem

**4a. Dedicated Docker volume**

The telemetry PostgreSQL data directory lives in a named Docker volume with a filesystem quota. On Box 3 (ext4 or XFS):

- **Option A (recommended — XFS project quota):** Mount a dedicated filesystem for telemetry data and apply a project quota.
- **Option B (practical — Docker volume on its own partition):** Use an LVM thin volume or a Docker volume backed by a loop device with a size limit.

For v1, the simplest approach is a **Docker named volume** with no special quota on the assumption that the PostgreSQL-level row cap + trigger at Layer 3 prevents the table from exceeding ~5 GB regardless of attack.

If Box 3's root filesystem is tight (<10 GB free), create a dedicated volume on its own partition:

```yaml
# docker-compose override for telemetry-postgres
volumes:
  telemetry-data:
    driver: local
    driver_opts:
      type: none
      device: /data/telemetry/postgres
      o: bind
```

Then enforce a 5 GB limit with XFS project quota on `/data/telemetry/`:

```bash
# Mark /data as XFS project-quota-enabled
xfs_quota -x -c 'limit bhard=5g telemetry' /data
```

**4b. PostgreSQL per-database size limit**

PostgreSQL 16 does not natively support per-database size caps, but `ALTER TABLESPACE` with a quota is available via extension (`pg_quota`) or filesystem-level limits as above. For v1, the database-level row cap + trigger is sufficient without filesystem quotas.

### Decision Summary

| Layer | Measure | Enforcement | Impact on attacker |
|-------|---------|-------------|--------------------|
| **L1 — Traefik** | `client_max_body_size 10k` | Proxy | Cannot write large blobs |
| **L1 — Traefik** | Per-IP rate limit (20/min) | Proxy | Limited to 28 800 req/day per IP |
| **L2 — App** | Pydantic schema, `extra="forbid"` | Validation | Cannot inject unexpected fields |
| **L2 — App** | Timestamp validation (±5 min, max 7d) | Validation | Replay attacks fail after 7 days |
| **L2 — App** | Per-instance_id rate limit (100/day) | App | Each fake iid capped at 100 writes/day |
| **L2 — App** | Payload dedup (1h window) | App | Exact replay rejected within 1h |
| **L3 — PG** | Row cap (10M rows ≈ 5 GB max) | DB trigger | Hard ceiling — cannot exceed even with bypassed app |
| **L3 — PG** | TTL (90 days) | Cron | Data auto-purges, worst-case self-heals |
| **L3 — PG** | Dedicated database | Isolation | Telemetry cannot impact other services |
| **L4 — FS** | 5 GB volume quota (v2) | XFS/Docker | Physical disk cannot fill |

### What is NOT in v1

- **Proof-of-work on the client** — adds complexity to the library, increases startup latency. Overkill for a tool that may be installed by a few hundred users.
- **HMAC signing** — no shared secret to distribute. The library is open-source, so any embedded key is visible to anyone.
- **Spam-detection ML** — not needed at the expected scale; monitoring + manual ban is sufficient.
- **CAPTCHA** — would require user interaction, defeats the purpose of silent telemetry.
- **Cloudflare WAF** — currently not in front of Box 3. Useful if the endpoint were under sustained attack, but not needed pre-emptively.

### Monitoring & Response

When abuse is detected (sudden spike in validation errors, storage approaching quota):

1. **Temporary IP block at Traefik** — add the offending IPs to a deny list middleware
2. **Adjust rate limits** — tighten per-IP from 20/min to 5/min
3. **Review anomaly** — check logs to determine if it's a bug in a real client version or deliberate abuse
4. **Permanent block** — if abuse persists, add a firewall rule at the host level

The rate limits are intentionally generous Layer 1 — they stop floods, not single-request sneaky writes. The tightest defence is Layer 3 (row cap + trigger), which guarantees the disk cannot fill regardless of what gets past the upper layers.

## Consequences

### Positive

- Disk cannot fill under any attack scenario (hard ceiling at 10M rows ≈ 5 GB)
- Defences are layered — no single bypass exposes storage
- Legitimate clients never hit any limit (4 heartbeats/day vs 100/day cap)
- Timestamp validation kills replay attacks without state on the collector
- Row cap + TTL are self-healing — data automatically purges over time
- Dedicated telemetry database cannot impact other services on the same PostgreSQL instance

### Negative

- Per-instance_id rate limit requires a SELECT per insert (~1 ms, negligible)
- Row cap trigger adds a tiny overhead to every INSERT statement (negligible until the cap is reached)
- Collector container is another service to deploy on Box 3 (but minimal — 1 endpoint, ~50 lines Python + psycopg2)
- No filesystem quota in v1 — relies on the database-level row cap (acceptable risk)

### Risks

- Row cap trigger might not fire if the trigger function fails (unlikely — tested at deploy time)
- Per-instance_id rate limit can be bypassed by rotating instance_ids (but Layer 1 per-IP rate limit still applies, and Layer 3 row cap is the ultimate backup)
- If PostgreSQL itself is compromised, all defences are moot (but this applies to every service on Box 3)
- When the row cap kicks in, legitimate old data may be deleted before newer data from an attacker (mitigated by TTL: old legitimate data is already past retention; the row cap only deletes when the table exceeds 10M rows, which requires exceptional volume)

## References

- [ADR 0005: Anonymous Tool Telemetry](0005-anonymous-tool-telemetry.md) — defines the telemetry architecture that this ADR secures
- [ADR 0008: Auth Telemetry Events](0008-auth-telemetry-events.md) — auth flow events sharing the same endpoint and rate limiting
- [Traefik RateLimit middleware docs](https://doc.traefik.io/traefik/middlewares/http/ratelimit/)
- [Pydantic v2 `extra="forbid"`](https://docs.pydantic.dev/latest/concepts/config/#extra-fields)
- [consoledonottrack.com](https://consoledonottrack.com) — DO_NOT_TRACK convention
