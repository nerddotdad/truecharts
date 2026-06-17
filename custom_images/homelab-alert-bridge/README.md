# homelab-alert-bridge

Lightweight incident funnel + ticketing for homelab alerts.

## Flow

```text
Alertmanager → alerts inbox (UI: /alerts)
                    ↓ auto-raise rules (Settings) OR manual "Raise incident"
              incident record
                    ↓ notification settings
                  ntfy
```

1. **`POST /hook`** — ingest alerts into the **inbox** (not incidents by default)
2. **Auto-raise** — configurable rules create incidents automatically (default: `critical` only)
3. **Alerts inbox** — review, multi-select, **Raise incident** (bundle alerts into one ticket)
4. **Incidents UI** — ack, merge, enrich, resolve; notifications flow **incident → ntfy**
5. **Manual incidents** — `+ New incident` without any alert

## URLs

| Surface | Path |
|---------|------|
| **Incidents** | `https://incidents.${DOMAIN_0}/` |
| **Alerts inbox** | `https://incidents.${DOMAIN_0}/alerts` |
| **Settings** | `https://incidents.${DOMAIN_0}/settings` |

## Auto-raise (Settings)

| Option | Purpose |
|--------|---------|
| **Enabled** | Turn auto-raise on/off |
| **Min severity** | e.g. `critical` — only matching severities raise |
| **Alertnames** | Comma list (empty = all names that meet severity) |
| **Label rules** | JSON matchers `[{"alertname":"Foo","namespace":"bar"}]` |
| **Group open** | Attach to existing open incident (same alertname + namespace) |

## Notifications (Settings)

ntfy posts are sent when incidents are raised/updated — not from raw Alertmanager payloads.

Built by **Build Custom Docker Images** on push to `custom_images/homelab-alert-bridge/`.

**`VERSION`** → GHCR tag; **Renovate** updates `homelab-alert-bridge/app/deployment.yaml`.
