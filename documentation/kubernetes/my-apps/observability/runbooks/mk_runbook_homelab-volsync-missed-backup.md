---
title: "Runbook: VolSync backup and mover jobs"
alertname: HomelabVolsyncMissedBackupInterval
alertnames:
  - HomelabVolsyncMissedBackupIntervalCritical
  - HomelabVolsyncSourceOutOfSync
  - HomelabVolsyncSrcJobFailed
  - HomelabVolsyncSrcPodStuck
  - HomelabVolsyncSrcJobsConcurrent
  - HomelabVolsyncReplicationSourceReconcileErrors
severity: warning
homelab_team: platform
releases:
  - system/volsync
areas:
  - downloaders
  - media
  - ai
---

# VolSync backup and mover health

--8<-- "runbook/overview.md"

| Field | Value |
|-------|-------|
| **Alerts** | Missed interval (6h warn / 30h critical), out of sync, src job failed, src pod stuck, concurrent jobs, reconcile errors |
| **PrometheusRule** | `homelab-storage.yaml` |
| **Backup target** | Restic → Garage (`truenas_garage` on TrueCharts apps) |
| **Pattern** | TrueCharts default: `volsync` **src** (scheduled) + **dest** (`manual: restore-once`) |

## What this means

VolSync **ReplicationSource** jobs push app PVC data to S3-compatible storage on a cron. Alerts use operator metrics (`volsync_missed_intervals_total`, `volsync_volume_out_of_sync`) and kube-state (`volsync-src` Jobs/Pods).

**Destination** `volsync_volume_out_of_sync == 1` is normal for idle `restore-once` destinations — homelab rules only page **source** role with missed intervals.

**Missed interval counter** does not reset automatically after one good backup; if you fixed an incident days ago, the warning may linger until the metric clears or you adjust the rule.

## Triage

--8<-- "runbook/triage-checklist.md"

```bash
# ReplicationSources in backup namespaces
kubectl get replicationsource -n downloaders -o wide
kubectl get replicationsource -n media -o wide
kubectl get replicationsource -n ai -o wide

# Active / failed mover jobs
kubectl get jobs -A | rg volsync-src
kubectl get pods -A | rg volsync-src

# Operator metrics (if scrape up)
kubectl run curl-vs --rm -i --restart=Never --image=curlimages/curl:latest -- \
  curl -sk https://volsync-metrics.volsync.svc:8443/metrics | rg 'missed_intervals|out_of_sync'
```

Map alert `obj_name` / `obj_namespace` to the app (e.g. `sonarr-config-config` → Sonarr HelmRelease).

## Diagnose

```bash
# Failed job logs (from alert job_name / namespace)
kubectl logs -n <namespace> job/<volsync-src-job-name> --all-containers --tail=100

# Stuck pod (ContainerCreating = Pending phase)
kubectl describe pod -n <namespace> <volsync-src-pod>

# Longhorn blocking attach?
kubectl get pvc -n <namespace> | rg volsync
kubectl describe pvc -n <namespace> <volsync-clone-pvc>

# ReplicationSource status
kubectl describe replicationsource -n <namespace> <name>
```

| Symptom | Likely cause |
|---------|----------------|
| Pod Pending &gt;2h | Longhorn disk not schedulable; faulted `volsync-*-src` PVC |
| Job Failed | Restic/S3 error, RBAC, or mover script exit |
| Many concurrent src jobs | Cron schedules overlap — stagger in app `helm-release.yaml` |
| Reconcile errors | CRD/spec conflict; paused source; leftover jobs |
| Missed intervals only | Prior failed night; counter not reset |

TrueCharts: only **`src.trigger.schedule`** is supported in chart values; dest stays **manual restore-once** (do not patch `ReplicationDestination` to scheduled triggers in postRenderers).

## Resolve

1. **Longhorn / disk** — If disk alerts fire, follow [Longhorn disk schedulability](mk_runbook_homelab-longhorn-disk-not-schedulable.md) first.

2. **Faulted VolSync clones** — [Longhorn volume faulted (VolSync PVCs)](mk_runbook_homelab-longhorn-volume-faulted.md): pause `ReplicationSource`, delete faulted `volsync-*-src` PVCs and failed jobs, unpause.

3. **Failed Restic backup** — Check Garage endpoint reachability from cluster, credentials in cluster secrets, and job logs for `restic` errors.

4. **Stagger schedules** — Spread `volsync.src.trigger.schedule` across apps (example pattern: Sonarr `0 0`, then +20m steps through Jellyfin) in each app's `helm-release.yaml` under `downloaders/`, `media/`, `ai/`.

5. **Concurrent job storm** — Verify Git cron values; wait for jobs to finish; avoid restarting all ReplicationSources at once.

6. **After successful backup** — Confirm `ReplicationSource` status and that a new snapshot exists in Garage; `volsync_missed_intervals_total` may need one clean interval before alerts clear.

```bash
# Optional: list ReplicationSources paused
kubectl get replicationsource -A -o json | jq '.items[] | select(.spec.paused==true) | .metadata | {ns:.namespace,name:.name}'
```

GitOps paths:

- VolSync operator: `clusters/main/kubernetes/system/volsync/app/helm-release.yaml`
- Per-app VolSync: `clusters/main/kubernetes/my-apps/<area>/<app>/app/helm-release.yaml`

## False positives and silences

- **Missed intervals after recovery**: metric can stay &gt;0; confirm last successful job before silencing.
- **HomelabVolsyncSourceOutOfSync**: requires missed intervals too; ignores dest-only drift.
- **HomelabVolsyncReplicationSourceReconcileErrors**: investigate if sustained; brief spikes during upgrades may be benign.

## Escalation

--8<-- "runbook/escalation.md"

- Storage: [Longhorn disk runbook](mk_runbook_homelab-longhorn-disk-not-schedulable.md)
- Metrics blind: [VolSync metrics down](mk_runbook_homelab-volsync-metrics-down.md)
