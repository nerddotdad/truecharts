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

5. **exportarr / config.xml port mismatch (Radarr):** exportarr reads `CONFIG=/config/config.xml` and uses `<Port>` for API calls. If config still has another app’s port (e.g. `8686` from Lidarr) while Radarr listens on `7878` via `RADARR__SERVER__PORT`, the UI works but metrics time out.

   ```bash
   kubectl exec -n downloaders deploy/radarr -c radarr -- grep '<Port>' /config/config.xml
   kubectl logs -n downloaders deploy/radarr -c radarr-exportarr --tail=20 | rg '7878|8686|timeout'
   ```

   One-time fix on the Radarr PVC (persists across restarts):

   ```bash
   # confirm mismatch (Radarr should be 7878, not 8686)
   kubectl exec -n downloaders deploy/radarr -c radarr -- grep '<Port>' /config/config.xml

   kubectl exec -n downloaders deploy/radarr -c radarr -- \
     sed -i 's|<Port>8686</Port>|<Port>7878</Port>|' /config/config.xml

   # restart pod so exportarr re-reads config
   kubectl delete pod -n downloaders -l app.kubernetes.io/instance=radarr
   ```

   Or in Radarr UI: **Settings → General → Port → 7878**, Save. Then restart the pod.

   Confirm: `up{namespace="downloaders",service="radarr-metrics"}==1` (may take up to ~20m for the alert to clear).

## Resolve

- Fix the workload or ServiceMonitor in GitOps under `my-apps/downloaders/<app>/`.
- After `up==1` for the target, the alert resolves and ntfy sends a resolved notification.
