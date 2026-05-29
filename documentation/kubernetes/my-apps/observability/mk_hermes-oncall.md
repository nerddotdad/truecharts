---
title: Hermes on-call (WebUI + Agent)
---

# Hermes on-call

AI-assisted alert triage using **[Hermes Agent](https://github.com/NousResearch/hermes-agent)** and **[Hermes WebUI](https://github.com/nesquena/hermes-webui)** — full CLI parity in the browser, with **persistent memory** (skills, sessions, `MEMORY.md`) so repeat incidents get faster over time.

## URLs

| Service | URL |
|---------|-----|
| **Hermes WebUI** | `https://hermes.${DOMAIN_0}` |
| **Ask AI** (from ntfy) | `POST https://hermes.${DOMAIN_0}/homelab/triage` (Bearer `HERMES_ALERT_TRIAGE_SECRET`) |
| **Incident API** | `https://hermes.${DOMAIN_0}/homelab/api/incidents/<id>` |

Login uses **`HERMES_WEBUI_PASSWORD`** → Flux substitutes **`${ADMIN_PASS}`** (same as Grafana).

## Alert flow

```text
Prometheus / Grafana → homelab-alert-bridge (stores incident JSON)
                    → alertmanager-ntfy → ntfy (Runbook | Alert | Ask AI)
Phone → Ask AI (POST) → https://hermes.<domain>/homelab/triage (bridge)
      → Hermes gateway webhook :8644 (/webhooks/homelab-alerts)
      → Agent triage (read-only kubectl / flux; skill homelab-k8s-flux-triage)
      → Follow up in Hermes WebUI if needed
```

The **Hermes gateway daemon** must run alongside WebUI in Docker. Upstream documents this for cron and messaging; homelab uses the same process for **webhooks** ([gateway daemon](https://github.com/nesquena/hermes-webui/blob/master/docs/docker.md#scheduled-jobs-and-the-gateway-daemon)). The `hermes-homelab` image starts `start-gateway.sh` in the background after WebUI installs `hermes-agent` into `/app/venv`.

## GitOps layout

| Path | Role |
|------|------|
| `my-apps/ai/kustomization.yaml` | Must list `hermes-oncall/ks.yaml` (Flux will not deploy Hermes otherwise) |
| `my-apps/ai/hermes-oncall/` | WebUI HelmRelease, RBAC, PVC |
| `my-apps/observability/homelab-alert-bridge/` | Webhook store + proxy + `/homelab/api` ingress |
| `custom_images/hermes-homelab/` | WebUI image + kubectl/flux + homelab skills |
| `custom_images/homelab-alert-bridge/` | Incident bridge image |
| `alertmanager-ntfy/app/configmap.yaml` | **Ask AI** `X-Actions` button |

## Image versions (CI PR)

CI publishes semver tags to GHCR (PaulHatch/semantic-version + git tags `x.y.z-<image>`), then **Renovate** opens PRs updating cluster image pins (`semver@sha256:…`). Merged PRs let Flux deploy the new tag.

| Image | Pin location |
|-------|----------------|
| `hermes-homelab` | `hermes-oncall/app/helm-release.yaml` → `values.image.tag` |
| `homelab-alert-bridge` | `homelab-alert-bridge/app/deployment.yaml` → `image:` |

## First deploy

1. **Push to `main`** so GitHub Actions builds `ghcr.io/nerddotdad/hermes-homelab` and `homelab-alert-bridge` (paths under `custom_images/`). Seed git baseline tags if GHCR already has newer semver (see `custom_images/README.md`).
2. Flux reconciles `homelab-alert-bridge` **before** Alertmanager traffic switches (Kustomization `dependsOn: alertmanager-ntfy` only — bridge should be up when AM config changes).
3. Open `https://hermes.${DOMAIN_0}`, complete WebUI onboarding if prompted, confirm model **qwen3.5:9b** via Ollama.
4. Fire a test alert (see `alert-test/`) and tap **Ask AI** on ntfy.

## Read-only cluster access

ServiceAccount **`hermes-oncall`** in namespace `ai` has **get/list/watch** on pods, events, jobs, HelmReleases, Kustomizations, etc. — no patch/delete.

Skill **`homelab-k8s-flux-triage`** (in the image) instructs the agent to stay read-only and prefer GitOps changes.

## Memory and skills

- State lives on PVC **`hermes-data`** mounted at `/home/hermeswebui/.hermes`.
- Back up this PVC (Longhorn snapshot or Velero) — losing it loses learned skills/sessions.
- After resolving an incident, tell Hermes what worked; it can offer to save a **skill** for future alerts.

## Ollama

Default model **`qwen3.5:9b`** at `http://ollama.ai.svc.cluster.local:11434/v1` (seeded in `custom_images/hermes-homelab/config.yaml`). In-cluster clients use Service **`ollama`** (or alias **`ollama-api`**) — not the ingress hostname alone. Change model/URL in WebUI **Control Center** or edit `config.yaml` on the PVC.

## Troubleshooting

| Issue | Check |
|-------|--------|
| **404 nginx** on `https://hermes.<domain>/` | Hermes HelmRelease not deployed — check `kubectl get helmrelease -n ai hermes-oncall` and `my-apps/ai/kustomization.yaml` includes `hermes-oncall/ks.yaml`. Only `/homelab/api` ingress alone returns 404 on `/`. |
| WebUI ImagePullBackOff | Build/push `hermes-homelab` image on `main` |
| Ask AI 404 incident | Bridge running? `kubectl logs -n observability deploy/homelab-alert-bridge` |
| Ask AI / triage 502 Hermes | Gateway not listening on :8644. WebUI **System Settings** may show “Gateway not configured”. Rebuild `hermes-homelab` ≥ 1.1.2; check `kubectl logs deploy/hermes-oncall-app-template -n ai \| grep start-gateway`. Verify: `kubectl run -n ai curl-test --rm -it --image=curlimages/curl -- curl -sS -o /dev/null -w '%{http_code}' http://hermes-oncall-app-template.ai.svc:8644/webhooks/homelab-alerts` (expect non-000). |
| Gateway never starts | `start-gateway` waits for `/app/venv/bin/hermes` (WebUI first boot ~5–10 min). Existing PVCs missing `platforms.webhook` in `config.yaml` are patched at gateway start. |
| **Gateway not configured** (orange pill) but `hermes gateway status` OK | Usually **root-owned** `gateway_state.json` from an older image while WebUI runs as `hermeswebui`. Fix: `hermes-homelab` ≥ 1.1.3 runs the gateway as `hermeswebui`, or `chown hermeswebui:hermeswebui ~/.hermes/gateway*` and restart the pod. |
| No kubectl in chat | Ensure `hermes-homelab` image (not upstream `nesquena/hermes-webui` alone) |
| Weak responses | Ollama up? `kubectl get pods -n ai -l app.kubernetes.io/instance=ollama` |
| **Connection error** in chat | Hermes logs show `ollama-api.ai.svc.cluster.local`? Use **`ollama.ai.svc.cluster.local:11434/v1`** (Service `ollama`) or apply `ollama-api` cluster DNS alias. `ollama-api.${DOMAIN_0}` is ingress-only. |
| **Missing imports: run_agent** | Use **`hermes-homelab`** image (includes agent at `/opt/hermes`), not upstream WebUI alone. After upgrade, **delete the pod** so first-boot `uv pip install` runs again (not only restart). First start can take **~5–10 min**. |
| Provider incomplete | Wait for startup; check logs for `Adding hermes-agent's pyproject.toml` |

See also [Observability](mk_observability.md) and [Alert runbooks](runbooks/mk_runbook_index.md).
