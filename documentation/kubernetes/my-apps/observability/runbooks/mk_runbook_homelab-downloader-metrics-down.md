---
title: "Runbook: HomelabDownloaderMetricsDown"
alertname: HomelabDownloaderMetricsDown
severity: warning
homelab_team: downloaders
areas:
  - downloaders
---

# HomelabDownloaderMetricsDown

| Field | Value |
|-------|-------|
| **Alert** | `HomelabDownloaderMetricsDown` |
| **Namespace** | `downloaders` |
| **Typical labels** | `service=*-metrics`, `job=radarr` (chart-dependent) |

## What this means

Prometheus has not scraped the app’s **metrics** target for at least **20 minutes**. That is separate from the web UI: Radarr/Sonarr/etc. may still load while metrics or the ServiceMonitor path is broken.

kube-prometheus-stack **TargetDown** in `downloaders` is routed to `null`; this homelab rule is what pages you on ntfy.

## Triage

1. Identify the app from alert labels (`service`, `job`), e.g. `radarr-metrics` / `job=radarr`.

   ```bash
   kubectl get pods -n downloaders -l app.kubernetes.io/name=radarr
   kubectl get servicemonitor -n downloaders | rg -i radarr
   ```

2. Check the metrics target in Prometheus (Grafana → Explore):

   ```promql
   up{namespace="downloaders", service="radarr-metrics"}
   ```

3. Confirm the HelmRelease and pod are healthy:

   ```bash
   flux get helmrelease radarr -n downloaders
   kubectl describe pod -n downloaders -l app.kubernetes.io/instance=radarr
   ```

4. Common fixes: pod crash loop, wrong metrics port in ServiceMonitor, chart upgrade disabled metrics, network policy blocking scrape.

## Resolve

- Fix the workload or ServiceMonitor in GitOps under `my-apps/downloaders/<app>/`.
- After `up==1` for the target, the alert resolves and ntfy sends a resolved notification.
