---
title: "Runbook: Ollama model pull (Job)"
alertname: HomelabOllamaModelPullStuck
alertnames:
  - HomelabKubeJobFailedOllamaModelPull
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

If you received **HomelabKubeJobFailedOllamaModelPull**, the pull container exited with failure (not just “still running”).

**Common false positive:** the Job was recreated (Flux sync, manual delete, etc.) while models were **already on the Ollama volume**. An older script always called `/api/pull` and could fail even though `/api/tags` listed the models. Since pull-script **v2-idempotent**, the Job exits successfully when models are present.

**Flux dry-run `spec.template: field is immutable`:** the ollama Kustomization uses `force: true` so Flux replaces the Job when the pull script changes. If you still see this error, delete the Job once: `kubectl delete job ollama-model-pull-job -n ai`.

**Never use `${name}` in the pull script** — Flux `postBuild` substitutes `${VAR}` from clusterenv and strips shell variables (grep/pull JSON ends up empty).

1. Confirm models exist:

   ```bash
   curl -s http://ollama-api.ai.svc.cluster.local:11434/api/tags
   ```

2. If models are present, delete the stale failed Job and let Flux recreate it (or wait for the next apply after updating Git):

   ```bash
   kubectl delete job ollama-model-pull-job -n ai
   ```

   The recreated Job should log `already present, skipping pull` and complete.

3. If models are **missing**, check Job logs, Ollama pod health, disk space, and network, then delete the Job and re-apply.

## Resolve

1. **If the pull finished** but the Job object is old: delete the Job (spec is immutable; recreate from Git if needed):

   ```bash
   kubectl delete job ollama-model-pull-job -n ai
   ```

2. **If stuck**: delete the Job, fix Ollama/disk/network, then re-apply or let Flux recreate the Job from `ollama/app/ollama-model-pull-job.yaml`.

3. **If pulls are no longer needed** on this cluster: remove `ollama-model-pull-job.yaml` from `ollama/app/kustomization.yaml` and commit.

Job manifest: `clusters/main/kubernetes/my-apps/ai/ollama/app/ollama-model-pull-job.yaml`
