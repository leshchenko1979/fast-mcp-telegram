# Grafana Annotations API

Reference for posting annotations to Grafana. Used to mark events on dashboards
(such as project releases) without provisioning a database table.

## Endpoint

```
POST /api/annotations
```

Auth: `Authorization: Bearer <GRAFANA_API_TOKEN>` (or basic auth with admin
credentials). The token must have `annotations:write` (Editor role or higher).

## Body

| Field | Required | Type | Notes |
|-------|----------|------|-------|
| `text` | yes | string | Annotation text. Shown on hover and in the panel legend. |
| `time` | yes | int (epoch ms) | Start of the annotation. |
| `timeEnd` | no | int (epoch ms) | End (for range annotations). |
| `tags` | no | string[] | Filterable in Grafana UI. |
| `dashboardUID` | no | string | Scopes annotation to one dashboard. |
| `panelId` | no | int | Scopes to one panel. |
| `data` | no | object | Free-form key/value pairs rendered as links. |

Org-wide annotations are created when `dashboardUID` is omitted. Dashboard-scoped
annotations need the dashboard UID; the `dataSourceUID` in the response is set
to the Grafana internal annotation DS.

## Minimal example (release annotation)

```bash
curl -X POST "$GRAFANA_URL/api/annotations" \
  -H "Authorization: Bearer $GRAFANA_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "v0.0.32 — OAuth2 PKCE",
    "time": 1750000000000,
    "tags": ["release", "fast-mcp-telegram"],
    "data": {
      "tag": "v0.0.32",
      "url": "https://github.com/leshchenko1979/fast-mcp-telegram/releases/tag/v0.0.32"
    }
  }'
```

The annotation appears as a vertical line on every panel in the dashboard,
labelled with the release tag. Tag the data with `release` so the user can
filter the annotation list in the Grafana UI.

## Programmatic example (Python, stdlib only)

```python
import json
import urllib.request
from datetime import datetime, timezone

RELEASE_TAG = "v0.0.32"
RELEASE_NAME = "OAuth2 PKCE"
RELEASE_URL = f"https://github.com/leshchenko1979/fast-mcp-telegram/releases/tag/{RELEASE_TAG}"
PUBLISHED_AT = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

body = {
    "text": f"{RELEASE_TAG} — {RELEASE_NAME}",
    "time": int(PUBLISHED_AT.timestamp() * 1000),
    "tags": ["release", "fast-mcp-telegram"],
    "data": {"tag": RELEASE_TAG, "url": RELEASE_URL},
}

req = urllib.request.Request(
    f"{GRAFANA_URL}/api/annotations",
    data=json.dumps(body).encode(),
    headers={
        "Authorization": f"Bearer {GRAFANA_API_TOKEN}",
        "Content-Type": "application/json",
    },
    method="POST",
)
with urllib.request.urlopen(req) as resp:
    print(resp.status, resp.read().decode())
```

## Use case: release annotations on the auth-telemetry dashboard

Trigger from a GitHub Action on `release: published`:

1. Extract the tag, name, and `published_at` from the GitHub event payload.
2. POST to `/api/annotations` with the dashboard UID of the auth-telemetry
   dashboard and a `release` tag.
3. Annotations show up on the timeline as soon as Grafana refreshes.

No DB schema, no collector changes, no sync script. The annotation lives in
Grafana's own `annotation` table, which is already provisioned.

## Gotchas

- `time` is **epoch milliseconds**, not seconds. Easy to get wrong.
- `dashboardUID` is the UID string, not the numeric ID. Find it in the
  dashboard URL or the dashboard JSON (`"uid": "..."`).
- The annotation API has no `GET /api/annotations` filter on `dashboardUID` for
  listing — use `/api/annotation-tags` or filter on `tags` via the UI.
- The `Bearer` token is per-user; rotate the same way as a password.
