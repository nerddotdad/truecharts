# homelab-alert-bridge

Alert-agnostic pipe between Alertmanager and homelab notifications:

1. **`POST /hook`** — store each alert as JSON (key = Alertmanager `fingerprint`), forward the **same** payload to alertmanager-ntfy
2. **`GET /homelab/api/incidents/<fingerprint>`** — incident JSON for Hermes WebUI Ask AI, including:
   - **`operator_message`** — same text the operator sees in ntfy (mirrors alertmanager-ntfy templates)
   - **`hermes_message`** — `operator_message` plus an **Agent context** block (`recommended_ai_skills`, timestamps, incident id)
3. **`POST /homelab/triage`** — optional Hermes webhook forward (Bearer / `?token=`)
4. **`GET /health`**

No alert-specific logic. Grouping, titles, ntfy actions, and runbook links belong in **PrometheusRule annotations** and **alertmanager-ntfy** templates.

PVC: `/data/incidents` (one `{fingerprint}.json` per alert).

| Variable | Purpose |
|----------|---------|
| `NTFY_BRIDGE_URL` | alertmanager-ntfy hook (default in-cluster) |
| `GRAFANA_PUBLIC_URL` | Grafana base URL for links in `operator_message` (match alertmanager-ntfy) |
| `HERMES_WEBHOOK_URL` / `HERMES_WEBHOOK_SECRET` | Optional triage → Hermes gateway |
| `HERMES_PUBLIC_BASE_URL` | Ask AI redirect base URL |
| `TRIAGE_AUTH_TOKEN` | Auth for `/homelab/triage` |

Built by **Build Custom Docker Images** on push to `custom_images/homelab-alert-bridge/`.

**`VERSION`** → GHCR tag; **Renovate** updates `homelab-alert-bridge/app/deployment.yaml`.
