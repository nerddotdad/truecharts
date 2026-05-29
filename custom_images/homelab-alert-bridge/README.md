# homelab-alert-bridge

- `POST /hook` — stores each alert as JSON; forwards non-grouped alerts to alertmanager-ntfy
- **Grouped alerts** (v1.2+) — one ntfy message per Alertmanager group, updated in place:
  - `new` — post to ntfy, store `group → ntfy_message_id` under `/data/incidents/_groups/`
  - `updated` — append `— Update —` and refresh locked-user list (Prometheus query)
  - `resolved` — append `— Resolved —` when the group clears (no second ntfy publish)
  - First handler: `jellyfin_user_locked` (group key: alertname + namespace)
- `GET /homelab/api/incidents/<id>` — incident JSON (per-alert fingerprints + `group-jellyfin_user_locked-<ns>`)
- `POST /homelab/triage` — Bearer (or `?token=` on 1.1.2+) + `incident_id` → Hermes webhook (ntfy **Ask AI** button)
- `GET /health`

PVC: `/data/incidents` (incidents + `_groups/` state).

Env (see deployment):

| Variable | Purpose |
|---|---|
| `NTFY_BASE_URL` / `NTFY_TOPIC` | Direct ntfy publish/update for grouped alerts |
| `PROMETHEUS_URL` | Live query for grouped alert state |
| `GRAFANA_PUBLIC_URL` / `JELLYFIN_DASHBOARD_URL` / `NTFY_CLICK_URL` | Markdown links in grouped messages |

Built by **Build Custom Docker Images** on push to `custom_images/homelab-alert-bridge/`.

**`VERSION`** drives GHCR tag `x.y.z`; **Renovate** updates `homelab-alert-bridge/app/deployment.yaml` when a newer tag is on GHCR.
