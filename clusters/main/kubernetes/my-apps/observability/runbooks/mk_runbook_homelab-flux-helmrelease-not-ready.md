---
title: "Runbook: HomelabFluxHelmReleaseNotReady"
alertname: HomelabFluxHelmReleaseNotReady
severity: critical
homelab_team: platform
scope: all-helmreleases
---

# HomelabFluxHelmReleaseNotReady

--8<-- "runbook/overview.md"

| Field | Value |
|-------|-------|
| **Alert** | `HomelabFluxHelmReleaseNotReady` |
| **Severity** | critical |
| **Condition** | `gotk_resource_info{kind=HelmRelease, ready="False"}` for **10m** |
| **Typical impact** | App not installed/upgraded; workload may be missing or on old revision |

## What this means

A Flux **HelmRelease** has been **Not Ready** for at least ten minutes. The chart install or upgrade failed, a dependency (HelmChart/HelmRepository) is broken, or values are invalid.

## Triage

--8<-- "runbook/triage-checklist.md"

Use labels from the alert: `exported_namespace`, `name`, `chart`, `chart_version`, `chart_source`.

## Diagnose

--8<-- "runbook/flux-helmrelease-diagnose.md"

```bash
# Example from alert labels
flux get helmchart -A | rg -i false
flux get helmrepository -A | rg -i false
```

## Resolve

--8<-- "runbook/resolve-gitops.md"

**Silence only if** you intentionally suspended the release (`spec.suspend: true`) and expect Not Ready.

## Escalation

--8<-- "runbook/escalation.md"
