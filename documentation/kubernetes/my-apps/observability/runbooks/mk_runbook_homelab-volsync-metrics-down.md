---
title: "Runbook: VolSync metrics scrape down"
alertname: HomelabVolsyncMetricsDown
severity: warning
homelab_team: platform
releases:
  - system/volsync
---

# HomelabVolsyncMetricsDown

--8<-- "runbook/overview.md"

| Field | Value |
|-------|-------|
| **Alert** | `HomelabVolsyncMetricsDown` |
| **Severity** | warning |
| **Condition** | `up{namespace="volsync"} == 0` or absent for **20m** |
| **Impact** | `volsync_*` backup alerts may not fire; operator may still run |

## What this means

Prometheus is not scraping the VolSync operator metrics Service (HTTPS on port **8443**). Backup health rules in `homelab-storage.yaml` depend on metrics like `volsync_missed_intervals_total` and `volsync_volume_out_of_sync`. kube-state alerts (`volsync-src` jobs/pods) may still work.

## Triage

--8<-- "runbook/triage-checklist.md"

```bash
kubectl -n volsync get pods,svc,servicemonitor
kubectl -n observability get prometheusrules homelab-storage
# Prometheus UI → Status → Targets → filter volsync
```

## Diagnose

```bash
# Operator pod healthy?
kubectl -n volsync get pods -l app.kubernetes.io/name=volsync
kubectl -n volsync logs deploy/volsync --tail=50

# ServiceMonitor (chart should enable metrics)
kubectl -n volsync get servicemonitor volsync -o yaml

# In-cluster scrape test
kubectl run curl-vs --rm -i --restart=Never --image=curlimages/curl:latest -- \
  curl -sk https://volsync-metrics.volsync.svc:8443/metrics | head
```

**Common causes**

- VolSync pod crash loop or not ready after upgrade (`system/volsync/app/helm-release.yaml`).
- ServiceMonitor label mismatch with Prometheus `serviceMonitorSelector`.
- TLS / network policy blocking scrape from Prometheus namespace.
- Prometheus or operator restarted; wait 20m before assuming sustained outage.

## Resolve

1. Fix the VolSync HelmRelease via Git (`clusters/main/kubernetes/system/volsync/app/helm-release.yaml`); let Flux reconcile.
2. Confirm `ServiceMonitor` exists and target shows **UP** in Prometheus.
3. If only metrics are broken but backups run, prioritize restoring scrape before relying on missed-interval alerts.

--8<-- "runbook/resolve-gitops.md"

## Escalation

--8<-- "runbook/escalation.md"

While metrics are down, use `kubectl get jobs,pods -A | rg volsync-src` and Longhorn disk alerts as backup signals.
