# homelab-alert-bridge

Lightweight incident funnel + ticketing for homelab alerts — a PagerDuty-style incident layer without on-call scheduling.

## What it does

1. **`POST /hook`** — ingest Alertmanager webhooks into SQLite, auto-group related firing alerts, publish to ntfy
2. **Web UI** — organize incidents: ack, resolve, merge, enrich (title/summary/tags), notes, timeline
3. **`GET /homelab/api/incidents/<id>`** — legacy/Hermes export (`operator_message`, `hermes_message`)
4. **`POST /homelab/triage`** — optional Hermes webhook forward (Bearer / `?token=`)
5. **REST API** — `/api/incidents`, ack/resolve/merge/notes for automation

```text
Alertmanager → bridge (SQLite incidents) → ntfy (Open incident | Ask AI)
                    ↓
              incidents.<domain> UI
                    ↓
              Hermes Ask AI (on demand)
```

## Incident model

| Concept | Behavior |
|---------|----------|
| **Ingest** | Each alert stored by fingerprint; new alerts attach to an open incident with same `alertname` + `namespace` |
| **Merge** | Move alerts from source incidents into a target; sources marked `merged` |
| **Enrich** | Edit title, summary, severity, tags; appended to timeline |
| **Lifecycle** | `open` → `acknowledged` → `resolved` (auto-resolve when all alerts resolve) |
| **Notes** | Operator notes stored on incident + timeline |

No on-call scheduler — ntfy remains the paging channel.

## URLs

| Surface | Path |
|---------|------|
| **Incident UI** | `https://incidents.${DOMAIN_0}/` |
| **Hermes API** | `https://hermes.${DOMAIN_0}/homelab/api/incidents/<id>` |
| **REST API** | `https://incidents.${DOMAIN_0}/api/incidents` |

Login uses `INCIDENTS_AUTH_TOKEN` (defaults to `TRIAGE_AUTH_TOKEN` / `HERMES_ALERT_TRIAGE_SECRET`).

## Environment

| Variable | Purpose |
|----------|---------|
| `INCIDENT_DIR` | PVC mount (default `/data/incidents`) |
| `INCIDENT_DB` | SQLite path (default `/data/incidents/incidents.db`) |
| `INCIDENTS_PUBLIC_BASE_URL` | ntfy X-Click + Open incident action |
| `NTFY_BASE_URL` / `NTFY_TOPIC` / `NTFY_PUBLIC_URL` | ntfy publish |
| `GRAFANA_PUBLIC_URL` | Links in notification body |
| `HERMES_WEBHOOK_URL` / `HERMES_WEBHOOK_SECRET` | Triage webhook |
| `HERMES_PUBLIC_BASE_URL` | Ask AI action button |
| `INCIDENTS_AUTH_TOKEN` / `TRIAGE_AUTH_TOKEN` | UI + API auth |

Legacy `{fingerprint}.json` files on the PVC are imported into SQLite on startup.

Built by **Build Custom Docker Images** on push to `custom_images/homelab-alert-bridge/`.

**`VERSION`** → GHCR tag; **Renovate** updates `homelab-alert-bridge/app/deployment.yaml`.
