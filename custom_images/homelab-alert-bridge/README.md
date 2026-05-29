# homelab-alert-bridge

- `POST /hook` — stores each alert as JSON, forwards to alertmanager-ntfy
- `GET /homelab/api/incidents/<id>` — incident JSON for debugging
- `POST /homelab/triage` — auth token + `incident_id` → Hermes webhook on `hermes-oncall-app-template.ai.svc:8644` (ntfy Ask AI)
- `GET /health`

PVC: `/data/incidents` (14-day retention policy can be added later).

Built by **Build Custom Docker Images** on push to `custom_images/homelab-alert-bridge/`.

**`VERSION`** drives GHCR tag `x.y.z`; **Renovate** updates `homelab-alert-bridge/app/deployment.yaml` (`image: …:x.y.z@sha256:…`) when a newer tag is on GHCR.
