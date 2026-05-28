---
title: "Runbook: ALERT_NAME_HERE"
alertname: ALERT_NAME_HERE
# Optional: more Prometheus alert names that share this page
# alertnames:
#   - OtherAlertForSameRunbook
severity: warning
homelab_team: platform
# Link to services (pick one or more):
# scope: all-helmreleases          # every HelmRelease doc page (platform alerts)
# releases:                         # specific Flux HelmReleases (namespace/name)
#   - downloaders/nzbget
#   - observability/grafana
# areas:                             # all releases under a my-apps folder
#   - downloaders
# charts:                            # match chart name from helm-release spec
#   - nzbget
---

# ALERT_NAME_HERE

!!! note "Template"
    Copy this file to `mk_runbook_<alert-kebab-name>.md` (see naming below), fill in the tables, then add `runbook_url` to the PrometheusRule. Delete this note block when done.

--8<-- "runbook/overview.md"

| Field | Value |
|-------|-------|
| **Alert** | `ALERT_NAME_HERE` |
| **Severity** | `warning` / `critical` |
| **Team** | `platform` |
| **PrometheusRule** | `homelab-*.yaml` (file name) |

## What this means

One or two sentences: what condition PromQL detects and what breaks for users.

## Triage

--8<-- "runbook/triage-checklist.md"

## Diagnose

<!-- Pick one or more snippet sections, or write custom steps -->

--8<-- "runbook/flux-helmrelease-diagnose.md"

```bash
# App-specific commands
```

## Resolve

--8<-- "runbook/resolve-gitops.md"

## Escalation

--8<-- "runbook/escalation.md"

## Applies to

Document which services this runbook is for (must match front matter above). With matching `releases:`, the runbook appears as a **sub-page under that chart** in the sidebar (below the auto-generated HelmRelease page). Platform-wide alerts use `scope: all-helmreleases` and stay at the area level.

| Binding | Example |
|---------|---------|
| `releases` | `downloaders/nzbget` → only that release’s doc |
| `areas` | `downloaders` → every release under `my-apps/downloaders/` |
| `charts` | `nzbget` → any release installing chart `nzbget` |
| `scope: all-helmreleases` | Listed under “Platform alert runbooks” on every chart page |

**Per-service on-call steps:** add `documentation/kubernetes/my-apps/<workload>/app/mk_runbook.md` (shows under “Service documentation” on that chart’s page).

## ntfy buttons (alertmanager-ntfy)

Homelab ntfy notifications expose three **view** actions when configured: **Runbook**, **Alert** (Grafana), **Dashboard** (only if `dashboard_url` is set on the alert). Tapping the notification opens the `homelab-alerts` topic in the ntfy app.

## Naming and ntfy link

| Item | Convention |
|------|------------|
| **Filename** | `mk_runbook_<slug>.md` — run the helper first; use the path it prints |
| **URL helper** | `python scripts/runbook_url.py HomelabFluxHelmReleaseNotReady` then `python scripts/runbook_url.py --path-only ...` |
| **Annotation** | `runbook_url: https://docs.${DOMAIN_0}/main/kubernetes/my-apps/observability/runbooks/mk_runbook_.../` |
| **URL helper** | Resolves `alertname` / `alertnames` from front matter — not only kebab-guessing |
| **Published** | **Last updated (Git)** on the page; **Site build info** for the nginx image date |

```yaml
annotations:
  runbook_url: https://docs.${DOMAIN_0}/main/kubernetes/my-apps/observability/runbooks/mk_runbook_ALERT-KEBAB-HERE/
```
