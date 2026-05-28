---
title: "Runbook: HomelabFluxHelmReleaseTestFail"
alertname: HomelabFluxHelmReleaseTestFail
severity: critical
releases:
  - observability/alert-test-fail2
---

# HomelabFluxHelmReleaseTestFail

!!! info "Test alert"
    Fires for `observability/alert-test-fail` only. Remove `alert-test/` and this runbook when validation is done.

| Field | Value |
|-------|-------|
| **Alert** | `HomelabFluxHelmReleaseTestFail` |
| **Purpose** | Verify Prometheus → Alertmanager → ntfy pipeline (2m `for`) |

## Expected behavior

HelmRelease uses a **nonexistent chart** (`alert-test-nonexistent-chart`). Not Ready is expected.

## Clean up

1. Delete `observability/alert-test/`
2. Remove `homelab-flux-test.yaml` from prometheus-rules kustomization
3. Delete this runbook and remove the index row in `mk_runbook_index.md`

--8<-- "runbook/escalation.md"
