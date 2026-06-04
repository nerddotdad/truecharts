---
title: "Runbook: Longhorn volume faulted"
alertname: HomelabLonghornVolumeFaulted
alertnames:
  - HomelabLonghornVolsyncPvcFaulted
severity: critical
homelab_team: platform
releases:
  - system/longhorn
areas:
  - downloaders
  - media
  - ai
---

# Longhorn volume faulted

--8<-- "runbook/overview.md"

| Field | Value |
|-------|-------|
| **Alerts** | `HomelabLonghornVolumeFaulted` (app PVCs), `HomelabLonghornVolsyncPvcFaulted` (`volsync-*` temp PVCs) |
| **PrometheusRule** | `homelab-storage.yaml` |
| **Condition** | `longhorn_volume_robustness{state="faulted"} == 1` |

## What this means

A Longhorn volume is in the **faulted** state. **Application PVCs** (`downloaders`, `media`, `ai`, excluding names matching `volsync-*`) may indicate real data risk — investigate before delete. **VolSync temp PVCs** (`volsync-*-src` clones) are disposable after a failed backup; deleting them does not remove app config data when Restic backups to Garage are healthy.

## Triage

--8<-- "runbook/triage-checklist.md"

```bash
# From alert labels: pvc_namespace, pvc, volume
kubectl get pvc -n <pvc_namespace> <pvc>
kubectl describe pvc -n <pvc_namespace> <pvc>
kubectl get volume.longhorn.io -n longhorn-system | rg <pvc> || true
```

Determine: **app PVC** vs **VolSync temp PVC** (`pvc` name contains `volsync-`).

## Diagnose

```bash
# Events on the workload using the PVC
kubectl get pods -n <pvc_namespace> -o wide
kubectl describe pod -n <pvc_namespace> <pod-using-pvc>

# All faulted volsync-related PVCs
kubectl get pvc -A -o custom-columns=NS:.metadata.namespace,NAME:.metadata.name,PHASE:.status.phase | rg volsync

# ReplicationSource still synchronizing?
kubectl get replicationsource -A
kubectl describe replicationsource -n <pvc_namespace> <name>
```

**VolSync temp PVC faulted** often follows disk not schedulable or a stuck `volsync-src` job. Fix disk headroom first ([disk schedulability runbook](mk_runbook_homelab-longhorn-disk-not-schedulable.md)).

**App PVC faulted** may need Longhorn UI: salvage, replica rebuild, or restore from VolSync/Garage — do not delete the app PVC without a backup/restore plan.

## Resolve

### VolSync temp PVC (`HomelabLonghornVolsyncPvcFaulted`)

1. **Pause** the matching `ReplicationSource` (`spec.paused: true`).
2. Delete the **failed Job**: `kubectl delete job -n <ns> -l ...` or by name `volsync-src-*`.
3. Delete the **faulted** PVC(s) matching `volsync-*-src` (and other idle `volsync-*` clones if documented in your chart notes — not the main app `config` claim).
4. **Unpause** `ReplicationSource`; operator recreates the next backup job.

Deleting only the Job without pausing can cause the operator to recreate work while `Synchronizing=True`.

### Application PVC (`HomelabLonghornVolumeFaulted`)

1. Longhorn UI → Volume → check replicas, snapshots, last error.
2. If the workload is down, check whether a **detach/reattach** cycle or node issue caused fault.
3. Restore path: TrueCharts **dest** `restore-once` + Garage if reinstalling; do not assume faulted app PVC is safe to delete.
4. GitOps fixes (replica count, storage class) go through `helm-release.yaml` for the app and Longhorn — never `kubectl apply` live hotfixes you cannot commit.

## Escalation

--8<-- "runbook/escalation.md"

Pair with [VolSync missed backup](mk_runbook_homelab-volsync-missed-backup.md) when faulted clones coincide with failed `volsync-src` jobs.
