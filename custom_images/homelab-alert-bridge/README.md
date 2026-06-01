# homelab-alert-bridge

Alert-agnostic pipe between Alertmanager and homelab notifications:

1. **`POST /hook`** — store each alert as JSON (key = Alertmanager `fingerprint`), **publish to ntfy** (title, body, priority, headers)
2. **`GET /homelab/api/incidents/<fingerprint>`** — incident JSON for Hermes WebUI Ask AI, including:
   - **`operator_message`** — same text the operator sees in ntfy (`message_format.py`)
   - **`hermes_message`** — `operator_message` plus an **Agent context** block (`recommended_ai_skills`, timestamps, incident id)
3. **`POST /homelab/triage`** — optional Hermes webhook forward (Bearer / `?token=`)
4. **`GET /health`**

No alert-specific logic. Grouping belongs in **AlertmanagerConfig**; human-readable text in **PrometheusRule annotations** (`summary`, `description`).

Publishing uses **ntfy priority** (`urgent` / `high` / `default` / `low`) from severity and status — not emoji tags. The bridge publishes directly to ntfy so Prometheus labels are not dumped into the notification (unlike stock `alertmanager-ntfy`, which appends every label as an `X-Tag`).

PVC: `/data/incidents` (one `{fingerprint}.json` per alert).

| Variable | Purpose |
|----------|---------|
| `NTFY_BASE_URL` | In-cluster ntfy base URL (default `http://ntfy.observability.svc.cluster.local:10222`) |
| `NTFY_TOPIC` | Topic name (default `homelab-alerts`) |
| `NTFY_PUBLIC_URL` | Tap-to-open URL (`X-Click`) |
| `GRAFANA_PUBLIC_URL` | Grafana links in message body |
| `HERMES_WEBHOOK_URL` / `HERMES_WEBHOOK_SECRET` | Optional triage → Hermes gateway |
| `HERMES_PUBLIC_BASE_URL` | Ask AI action button URL |
| `TRIAGE_AUTH_TOKEN` | Auth for `/homelab/triage` |

`alertmanager-ntfy` remains in the cluster for reference/fallback; the live path is bridge → ntfy.

Built by **Build Custom Docker Images** on push to `custom_images/homelab-alert-bridge/`.

**`VERSION`** → GHCR tag; **Renovate** updates `homelab-alert-bridge/app/deployment.yaml`.
