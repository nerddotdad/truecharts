# homelab-alert-bridge

- `POST /hook` — stores each alert as JSON, forwards to alertmanager-ntfy
- `GET /homelab/api/incidents/<id>` — incident JSON for debugging
- `POST /homelab/triage` — auth token + `incident_id` → Hermes webhook (ntfy Ask AI)
- `GET /health`

PVC: `/data/incidents` (14-day retention policy can be added later).

Built by **Build Custom Docker Images** on push to `custom_images/homelab-alert-bridge/`.

CI semver tags (`x.y.z-homelab-alert-bridge` via **PaulHatch/semantic-version**); **Renovate** updates `homelab-alert-bridge/app/deployment.yaml` when a newer tag is published.
