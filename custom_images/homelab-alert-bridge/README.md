# homelab-alert-bridge

- `POST /hook` — stores each alert as JSON, forwards to alertmanager-ntfy
- `GET /homelab/api/incidents/<id>` — incident JSON for debugging
- `POST /homelab/triage` — Bearer (or `?token=` on 1.1.2+) + `incident_id` in JSON body or `?incident_id=` query → Hermes webhook (ntfy **Ask AI** button, not the notification tap)
- `GET /health`

PVC: `/data/incidents` (14-day retention policy can be added later).

Built by **Build Custom Docker Images** on push to `custom_images/homelab-alert-bridge/`.

**`VERSION`** drives GHCR tag `x.y.z`; **Renovate** updates `homelab-alert-bridge/app/deployment.yaml` (`image: …:x.y.z@sha256:…`) when a newer tag is on GHCR.
