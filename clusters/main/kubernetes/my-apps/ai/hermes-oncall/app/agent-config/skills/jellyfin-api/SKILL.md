---
name: jellyfin-api
description: Investigate Jellyfin incidents via the Jellyfin REST API (users, sessions, system health, lockouts). Use with homelab-k8s-flux-triage for jellyfin_* alerts and media issues.
metadata:
  hermes:
    tags:
      - homelab
      - jellyfin
      - media
      - api
---

# Jellyfin API (homelab investigations)

Use this skill when triaging **`jellyfin_*` alerts**, playback issues, user lockouts, library problems, or exporter/API health failures on the homelab Jellyfin instance.

Pair with **`homelab-k8s-flux-triage`** for pod logs, HelmRelease status, and Flux — use this skill for **Jellyfin application checks** via its API.

## Hard rules

- **GitOps for infra**: pod restarts, Helm values, and cluster changes still go through Git + Flux (see `homelab-k8s-flux-triage`).
- Prefer **in-cluster API URL** (`JELLYFIN_API_URL`) from the Hermes pod — faster and avoids ingress/TLS issues.

## References

- Jellyfin API docs (Swagger): `$JELLYFIN_PUBLIC_URL/api-docs/swagger/`
- OpenAPI JSON: `$JELLYFIN_API_URL/api-docs/openapi.json` (GET)
- Upstream stable OpenAPI: https://api.jellyfin.org/openapi/jellyfin-openapi-stable.json
- Homelab Grafana dashboard UID: `603679cbda70a9fe`

## Environment Variables

The following are useful environment variables related to jellyfin

$JELLYFIN_API_TOKEN - Jellyfin API key (admin) — use in auth header below
$JELLYFIN_API_URL - In-cluster base, e.g. http://jellyfin.media.svc.cluster.local:8096
$JELLYFIN_PUBLIC_URL - Public UI, e.g. https://jellyfin.hoth.systems
$HOMELAB_GRAFANA_URL - Jellyfin dashboard: {HOMELAB_GRAFANA_URL}/d/603679cbda70a9fe/jellyfin

## Public health (great for api connectivity tests)

```bash
curl -X GET "$JELLYFIN_API_URL/Users" 
```

## Authentication

Every authenticated request needs the Emby/Jellyfin authorization header e.g. "X-Emby-Token: $JELLYFIN_API_TOKEN"

## Unlocking a user

The below command will give you a list of all the users on the server. Grab the USER IDs for the users that are locked.

```bash
curl -X GET "$JELLYFIN_API_URL:8096/Users" -H "X-Emby-Token: $JELLYFIN_API_TOKEN" -H "Content-Type: application/json" 
```

After you gathered the USER IDs you'd use this curl to enable them

```bash
curl -X POST "$JELLYFIN_API_URL/Users/${USER_ID}/Policy" -H "X-Emby-Token: $JELLYFIN_API_TOKEN" -H "Content-Type: application/json" -d '{"IsDisabled": false}'
```