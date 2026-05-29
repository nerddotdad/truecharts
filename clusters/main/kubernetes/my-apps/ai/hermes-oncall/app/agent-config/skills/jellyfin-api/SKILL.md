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

Pair with **`homelab-k8s-flux-triage`** for pod logs, HelmRelease status, and Flux — use this skill for **Jellyfin server state** via its API.

## Hard rules

- **Default read-only**: use GET endpoints to investigate. Do **not** unlock users, change policies, restart the server, or delete library items via API unless the human explicitly asks.
- **GitOps for infra**: pod restarts, Helm values, and cluster changes still go through Git + Flux (see `homelab-k8s-flux-triage`).
- Prefer **in-cluster API URL** (`JELLYFIN_API_URL`) from the Hermes pod — faster and avoids ingress/TLS issues.
- **`curl -I` / HEAD** on OpenAPI and some routes returns **404** even when GET works — always use GET for API probes.
- Cite **`JELLYFIN_PUBLIC_URL`** when giving the human browser links (Dashboard, Users, etc.).

## Environment (pod)

Flux sets these on the Hermes pod (token is the same Homepage widget key as `HP_JELLYFIN` in `clusterenv.yaml`):

| Variable | Value / purpose |
|----------|-----------------|
| `JELLYFIN_API_TOKEN` | Jellyfin API key (admin) — use in auth header below |
| `JELLYFIN_API_URL` | In-cluster base, e.g. `http://jellyfin.media.svc.cluster.local:8096` |
| `JELLYFIN_PUBLIC_URL` | Public UI, e.g. `https://jellyfin.hoth.systems` |
| `HOMELAB_GRAFANA_URL` | Jellyfin dashboard: `{HOMELAB_GRAFANA_URL}/d/603679cbda70a9fe/jellyfin` |

## Authentication

Every authenticated request needs the Emby/Jellyfin authorization header (token from `$JELLYFIN_API_TOKEN`):

```bash
AUTH='X-Emby-Authorization: MediaBrowser Client="Hermes-oncall", Device="Hermes", DeviceId="hermes-oncall", Version="1.0.0", Token="'"$JELLYFIN_API_TOKEN"'"'
BASE="$JELLYFIN_API_URL"
```

Quick auth check:

```bash
curl -sS -H "$AUTH" "$BASE/System/Info" | head -c 400
```

Public health (no token):

```bash
curl -sS "$BASE/System/Info/Public"
curl -sS -o /dev/null -w "health HTTP %{http_code}\n" "$BASE/health"
```

## OpenAPI (machine-readable spec)

| Source | URL | Notes |
|--------|-----|-------|
| **Live (this server)** | `$JELLYFIN_API_URL/api-docs/openapi.json` | GET only; ~2 MB JSON; matches Swagger UI / ReDoc |
| **Stable upstream** | https://api.jellyfin.org/openapi/jellyfin-openapi-stable.json | Version-agnostic reference |

Wrong path (404): `/api-docs/v1/openapi.json` — Jellyfin 10.11 uses document name `api-docs`, not `v1`.

Browse interactively: `$JELLYFIN_PUBLIC_URL/api-docs/swagger/` or `/api-docs/redoc/`.

## Homelab layout

| Item | Value |
|------|-------|
| Namespace | `media` |
| HelmRelease | `jellyfin` |
| Service | `jellyfin.media.svc.cluster.local:8096` |
| Exporter | `jellyfin-exporter-app-template` (uses same API token) |
| Metrics | Chart `/metrics` on :8096; rebelcore exporter on :9594 |

## Alert → investigation map

| Alert | API-first checks | Then (K8s skill) |
|-------|------------------|------------------|
| `jellyfin_api_down` | `GET /health`, `GET /System/Info/Public`, `GET /System/Info` with token | Jellyfin pod logs, exporter `JELLYFIN_ADDRESS` |
| `jellyfin_user_locked` | `GET /Users` — find user by `username` label; check `Policy.IsDisabled` | Confirm `jellyfin_user_account{admin="0"}==0` in Grafana |
| `jellyfin_pending_restart` | `GET /System/Info` → `RestartRequired` / pending restart flags | Admin Dashboard or planned pod recycle via GitOps |
| `jellyfin_metrics_down` | `GET /health` (app may be fine) | Scrape targets, ServiceMonitors — not API |
| `jellyfin_exporter_collector_failed` | `GET /System/Info`, plugin-dependent collectors | Exporter logs; Playback Reporting plugin for activity collector |

## High-value endpoints

Paths are relative to `$JELLYFIN_API_URL`. Append query params as documented in OpenAPI.

| Endpoint | Purpose |
|----------|---------|
| `GET /System/Info` | Version, startup wizard done, restart required, OS |
| `GET /System/Info/Public` | Unauthenticated reachability |
| `GET /Users` | All users — `Name`, `Id`, `Policy.IsDisabled`, `LastLoginDate`, failed login lockout state |
| `GET /Users/{userId}` | Single user policy and profile |
| `GET /Sessions` | Active streams, clients, transcode info |
| `GET /Library/VirtualFolders` | Libraries mounted and paths |
| `GET /ScheduledTasks` | Task failures / next run |
| `GET /System/Logs` | Recent server log entries (admin) |
| `GET /Branding/Configuration` | Server display name |

### Example: list users and lockout status

```bash
curl -sS -H "$AUTH" "$BASE/Users" \
  | python3 -c "
import json,sys
for u in json.load(sys.stdin):
    p=u.get('Policy') or {}
    print(f\"{u.get('Name'):20} id={u.get('Id')} disabled={p.get('IsDisabled')} last_login={u.get('LastLoginDate')}\")
"
```

### Example: find one user from alert label

```bash
USER="alice"   # from alert.labels.username
curl -sS -H "$AUTH" "$BASE/Users" \
  | python3 -c "
import json,sys
name=sys.argv[1]
for u in json.load(sys.stdin):
    if u.get('Name')==name:
        import pprint; pprint.pp(u)
        break
else:
    print('user not found:', name)
" "$USER"
```

### Example: active playback / sessions

```bash
curl -sS -H "$AUTH" "$BASE/Sessions" | python3 -m json.tool | head -80
```

## User lockout (`jellyfin_user_locked`)

1. Confirm via API: `Policy.IsDisabled == true` on the alert user.
2. Check `LastLoginDate` and admin activity feed (Dashboard) for failed login pattern vs manual disable.
3. **Unlock (human or explicit request only)**:
   - UI: Dashboard → Users → user → uncheck **Disable this user** → Save.
   - API (destructive — ask first): `GET /Users/{id}` → set `Policy.IsDisabled` false → `POST /Users/{id}/Policy` with updated JSON body per OpenAPI.

## Typical triage flow

1. Restate alert (`alertname`, `namespace`, `username` if present).
2. Run public health + authenticated `System/Info`.
3. For user alerts: `GET /Users` and correlate with Prometheus `jellyfin_user_account` labels (`user_id`, `username`, `last_access`).
4. For API down: compare in-cluster `$JELLYFIN_API_URL` vs `$JELLYFIN_PUBLIC_URL` (ingress/TLS vs app failure).
5. Switch to **`homelab-k8s-flux-triage`** for pod events, logs, HelmRelease.
6. Link Grafana dashboard from `dashboard_url` annotation or `HOMELAB_GRAFANA_URL` table above.
7. Propose numbered resolution steps; ask before unlock, restart, or policy changes.

## curl template

```bash
export AUTH='X-Emby-Authorization: MediaBrowser Client="Hermes-oncall", Device="Hermes", DeviceId="hermes-oncall", Version="1.0.0", Token="'"$JELLYFIN_API_TOKEN"'"'
export BASE="$JELLYFIN_API_URL"

curl -sS -H "$AUTH" "$BASE/System/Info" | python3 -m json.tool
curl -sS -H "$AUTH" "$BASE/Users" | python3 -m json.tool
curl -sS -H "$AUTH" "$BASE/Sessions" | python3 -m json.tool
```

## References

- Jellyfin API docs (Swagger): `$JELLYFIN_PUBLIC_URL/api-docs/swagger/`
- OpenAPI JSON: `$JELLYFIN_API_URL/api-docs/openapi.json` (GET)
- Upstream stable OpenAPI: https://api.jellyfin.org/openapi/jellyfin-openapi-stable.json
- Homelab Grafana dashboard UID: `603679cbda70a9fe`
