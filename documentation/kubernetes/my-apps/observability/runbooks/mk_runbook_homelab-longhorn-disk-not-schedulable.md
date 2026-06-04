---
title: "Runbook: Longhorn disk capacity and schedulability"
alertname: HomelabLonghornDiskNotSchedulable
alertnames:
  - HomelabLonghornDiskSpaceLow
  - HomelabLonghornNodeStorageScheduledHigh
severity: critical
homelab_team: platform
releases:
  - system/longhorn
areas:
  - downloaders
  - media
  - ai
---

# Longhorn disk schedulability and headroom

--8<-- "runbook/overview.md"

| Field | Value |
|-------|-------|
| **Alerts** | `HomelabLonghornDiskNotSchedulable`, `HomelabLonghornDiskSpaceLow`, `HomelabLonghornNodeStorageScheduledHigh` |
| **PrometheusRule** | `homelab-storage.yaml` |
| **GitOps** | `clusters/main/kubernetes/system/longhorn/app/helm-release.yaml`, `recurring-jobs.yaml` |

## What this means

Longhorn is running out of **schedulable** space on a disk or node. This is not always the same as “data size” in the UI: with VolSync, snapshot chains and **filesystem-trim** lag can make disks report full while payload is modest. When `longhorn_disk_status{condition="schedulable"} == 0`, new replicas (including VolSync `volsync-*-src` clone PVCs) fail with errors like **precheck new replica failed: disks are unavailable**.

**DiskSpaceLow** (free &lt; 30%) is an early warning before the **20%** `storageMinimalAvailablePercentage` floor in Helm values.

**NodeStorageScheduledHigh** means scheduled bytes are a large fraction of capacity (overprovisioning 200% + snapshots); “allocated” in the UI can look worse than actual usage.

## Triage

--8<-- "runbook/triage-checklist.md"

```bash
# Disk schedulability and usage (Prometheus / Longhorn metrics)
kubectl -n longhorn-system get nodes.longhorn.io -o wide
kubectl get pods -A -o wide | rg 'volsync-src|ContainerCreating' || true

# Longhorn UI: Node → Disk → check Schedulable, Actual space used, Scheduled
```

Confirm whether VolSync backup jobs are stuck at the same time (`volsync-src-*` pods Pending).

## Diagnose

```bash
# Metrics endpoint (optional)
kubectl -n longhorn-system port-forward svc/longhorn-backend 9500:9500 &
curl -s localhost:9500/metrics | rg 'longhorn_disk_status|longhorn_disk_usage|longhorn_disk_capacity'

# Faulted VolSync temp PVCs (common during disk pressure)
kubectl get pvc -A | rg 'volsync-.*-src|volsync-.*' || true

# Recurring jobs applied from Git
kubectl -n longhorn-system get recurringjobs.longhorn.io
```

**Typical root causes**

1. Filesystem free space below `storageMinimalAvailablePercentage` (currently **20%** in `helm-release.yaml`).
2. VolSync snapshot/clone PVCs left **faulted** after a failed backup window.
3. Snapshot space not reclaimed until **filesystem-trim** runs (TrueCharts + Longhorn guide).
4. Many `volsync-src` jobs at once (schedules not staggered) → snapshot pile-up around midnight.

Reference: [TrueCharts Longhorn + VolSync](https://truecharts.org/guides/clustertool/csi/longhorn/#issues-with-longhorn-and-volsync)

## Resolve

1. **Free schedulable space (observe only — do not kubectl patch Longhorn settings live)**
   - Wait for or verify recurring jobs: `trim` (02:00), `snapshot-delete` (22:00), `snapshot-cleanup` (22:30) in `system/longhorn/app/recurring-jobs.yaml`.
   - In Longhorn UI, run **Trim Filesystem** on affected volumes if urgent.

2. **Clear stuck VolSync clones** (app data PVCs are separate; Garage has Restic backups)
   - Pause the `ReplicationSource` (Git or one-off edit is still GitOps-preferred; if emergency: `kubectl patch replicationsource <name> -n <ns> --type merge -p '{"spec":{"paused":true}}'` then revert via Git).
   - Delete failed `volsync-src` **Jobs** and faulted **`volsync-*-src`** PVCs only — not the app `config` PVC.
   - Unpause `ReplicationSource` after disk is schedulable.

3. **If headroom stays low after trim**
   - Review `storageMinimalAvailablePercentage` / `storageOverProvisioningPercentage` in Git (`helm-release.yaml`), not ad-hoc UI edits you cannot commit.
   - Reduce concurrent backups: stagger `volsync.src.trigger.schedule` on HelmReleases (`downloaders`, `media`, `ai`).

4. **After recovery**
   - Confirm `longhorn_disk_status{condition="schedulable"} == 1` and VolSync `volsync_missed_intervals_total` stops increasing.

## Escalation

--8<-- "runbook/escalation.md"

If app PVCs (not `volsync-*`) are faulted, see [Longhorn volume faulted](mk_runbook_homelab-longhorn-volume-faulted.md). If backups still fail, see [VolSync missed backup](mk_runbook_homelab-volsync-missed-backup.md).
