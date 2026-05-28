---
title: "Runbook: HomelabOllamaModelPullStuck"
alertname: HomelabOllamaModelPullStuck
severity: warning
homelab_team: ai
releases:
  - ai/ollama
---

# HomelabOllamaModelPullStuck

| Field | Value |
|-------|-------|
| **Alert** | `HomelabOllamaModelPullStuck` |
| **Job** | `ollama-model-pull-job` in namespace `ai` |

## What this means

The GitOps **bootstrap Job** that pulls Ollama models has been **active for more than 36 hours**. Pulling multi‑GB models over HTTP can take a long time, but runs beyond a day and a half often mean a stuck `curl` pull or Ollama not progressing.

**KubeJobNotCompleted** (12h) for this job is suppressed in Alertmanager; this homelab rule is what pages you.

## Triage

```bash
kubectl get job ollama-model-pull-job -n ai
kubectl logs -n ai job/ollama-model-pull-job --tail=80
kubectl get pods -n ai -l app.kubernetes.io/instance=ollama
curl -s http://ollama-api.ai.svc.cluster.local:11434/api/tags | head
```

Check whether the Job pod is still running, whether Ollama API responds, and whether pulls appear in logs (`pulling qwen3.5:9b`, etc.).

## KubeJobFailed

If you received **KubeJobFailed** for this Job, the pull container exited with failure (not just “still running”). Use the steps below, then delete the Job so the alert clears.

## Resolve

1. **If the pull finished** but the Job object is old: delete the Job (spec is immutable; recreate from Git if needed):

   ```bash
   kubectl delete job ollama-model-pull-job -n ai
   ```

2. **If stuck**: delete the Job, fix Ollama/disk/network, then re-apply or let Flux recreate the Job from `ollama/app/ollama-model-pull-job.yaml`.

3. **If pulls are no longer needed** on this cluster: remove `ollama-model-pull-job.yaml` from `ollama/app/kustomization.yaml` and commit.

Job manifest: `clusters/main/kubernetes/my-apps/ai/ollama/app/ollama-model-pull-job.yaml`
