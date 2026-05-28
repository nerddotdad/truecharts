---
title: Alert pipeline test
---

# Alert pipeline test harness

Intentionally broken `HelmRelease` to validate Flux and notification alerts without waiting for a real outage.

## What it does

| Resource | Purpose |
|----------|---------|
| `app/helm-release.yaml` | `alert-test-fail` — chart `alert-test-nonexistent-chart` does not exist |
| `../prometheus-rules/app/homelab-flux-test.yaml` | Fires `HomelabFluxHelmReleaseTestFail` after **2 minutes** (not 10) |

Production rule `HomelabFluxHelmReleaseNotReady` in `homelab-flux.yaml` also matches this release after **10 minutes**.

## Run the test

1. Commit and push (Flux reconciles `alert-test` Kustomization).
2. Confirm the release is failing:

   ```bash
   kubectl get helmrelease alert-test-fail -n observability
   kubectl describe helmrelease alert-test-fail -n observability
   ```

3. Confirm metrics (after kube-state-metrics Flux config is live):

   ```bash
   kubectl exec -n kube-prometheus-stack prometheus-kube-prometheus-stack-0 -c prometheus -- \
     wget -qO- 'http://localhost:9090/api/v1/query?query=gotk_resource_info{name="alert-test-fail"}'
   ```

4. Watch Prometheus (optional):

   ```bash
   kubectl exec -n kube-prometheus-stack prometheus-kube-prometheus-stack-0 -c prometheus -- \
     wget -qO- 'http://localhost:9090/api/v1/rules' | grep -i HomelabFlux
   ```

5. Expect ntfy on topic `homelab-alerts` within ~2–3 minutes (`HomelabFluxHelmReleaseTestFail`).

## Clean up

Remove these from Git and push:

- `observability/alert-test/` (this directory + `ks.yaml` entry in parent `kustomization.yaml`)
- `observability/prometheus-rules/app/homelab-flux-test.yaml` (and its line in `kustomization.yaml`)

The broken HelmRelease is pruned automatically when the Flux Kustomization is removed.
