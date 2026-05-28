# homelab-alert-bridge

- `POST /hook` — stores each alert as JSON, forwards to alertmanager-ntfy
- `GET /homelab/api/incidents/<id>` — used by Hermes WebUI (Ask AI)
- `GET /health`

PVC: `/data/incidents` (14-day retention policy can be added later).

Built by **Build Custom Docker Images** on push to `custom_images/homelab-alert-bridge/`.
