---
title: Hermes on-call (WebUI + Agent)
---

# Hermes on-call

AI-assisted alert triage using **[Hermes Agent](https://github.com/NousResearch/hermes-agent)** and **[Hermes WebUI](https://github.com/nesquena/hermes-webui)** — full CLI parity in the browser, with **persistent memory** (skills, sessions, `MEMORY.md`) so repeat incidents get faster over time.

## URLs

| Service | URL |
|---------|-----|
| **Hermes WebUI** | `https://hermes.${DOMAIN_0}` |
| **Hermes dashboard** | `https://hermes-dash.${DOMAIN_0}` — config, logs, skills, gateway status, embedded TUI chat |
| **Ask AI** (from ntfy) | Opens `https://hermes.${DOMAIN_0}/?incident=<id>&autostart=1` (WebUI chat). API: `GET/POST /homelab/triage` (token) → gateway webhook |
| **Incident API** | `https://hermes.${DOMAIN_0}/homelab/api/incidents/<id>` |

Login uses **`HERMES_WEBUI_PASSWORD`** → Flux substitutes **`${ADMIN_PASS}`** (same as Grafana).

The **Hermes Agent dashboard** (`hermes dashboard`) runs in the same pod on port **9119**, exposed at **`https://hermes-dash.${DOMAIN_0}`**. It uses `--insecure` (session-token auth, not Nous OAuth) because this is a homelab ingress — it can read/write `config.yaml` and `.env`, so treat the URL like an admin surface. WebUI chat remains at `hermes.${DOMAIN_0}`; use the dashboard for config, cron, logs, skills toggles, and gateway status.

## Alert flow

```text
Prometheus / Grafana → homelab-alert-bridge (stores incident JSON)
                    → alertmanager-ntfy → ntfy (Runbook | Alert | Ask AI)
Phone → Ask AI → https://hermes.<domain>/?incident=<id>&autostart=1 (WebUI new chat + triage message)
      (Optional API path: /homelab/triage → gateway webhook — sessions appear under Gateway, not main chat list)
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
| `alertmanager-ntfy/app/configmap.yaml` | **Ask AI** `view` action (URL with `incident_id` + `token`; restart `alertmanager-ntfy` after edits) |

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

## Web search (SearXNG)

Hermes **`web_search`** uses your cluster **SearXNG** (`http://searxng.ai.svc.cluster.local:8080`), configured via GitOps:

- Helm env: `SEARXNG_URL` on `hermes-oncall`
- Seed `config.yaml`: `web.search_backend: searxng` in `custom_images/hermes-homelab`

SearXNG is **search-only** (no `web_extract`). For homelab MkDocs/runbooks, the agent should use **`HOMELAB_DOCS_BASE_URL`** and the in-cluster docs mirror (see skill `homelab-k8s-flux-triage`). For arbitrary URLs, use terminal `curl` or browser tools.

**Existing PVC** (already has `~/.hermes/config.yaml`): after Flux applies the new env, restart the Hermes pod. If search still fails, add to the PVC config:

```yaml
web:
  search_backend: searxng
```

Or run `hermes tools` → Web Search & Extract → SearXNG inside the pod.

Verify from the cluster: `curl -sS "http://searxng.ai.svc.cluster.local:8080/search?q=test&format=json"` → HTTP 200.

See [Hermes web search docs](https://hermes-agent.nousresearch.com/docs/user-guide/features/web-search).

## Tools not working in WebUI

Hermes **hermes-homelab** pre-bakes WebUI + `hermes-agent[all]` into `/apptoo/venv` (rsync’d to `/app` on start). Plugin-backed tools (`web_search`, `web_extract`, many integrations) load from **`/opt/hermes/plugins`**, not from the venv copy. Without **`HERMES_BUNDLED_PLUGINS=/opt/hermes/plugins`**, `web_search` returns *"No web search provider configured"* even when `SEARXNG_URL` is set. Bundled agent skills sync from **`HERMES_BUNDLED_SKILLS=/opt/hermes/skills`** (not `/app/venv/skills`, which upstream excludes).

| Symptom | Likely cause | Fix |
|---------|----------------|-----|
| `web_search` never runs / provider error | Missing `HERMES_BUNDLED_PLUGINS` | Set env on HelmRelease (see `hermes-oncall/app/helm-release.yaml`), restart pod |
| Model replies with JSON/tool XML as text | Ollama + `qwen3.5:9b` tool format | Keep `model.provider: custom`; try `qwen3-coder:latest`; upgrade Ollama |
| `kubectl` / cluster tools fail | Agent not using in-cluster SA | Use `terminal` tool (works with SA token); ignore missing `~/.kube/config` |
| No tools at all in UI | Session toolset override | Session settings → toolsets → leave blank (global) or include `web`, `terminal` |
| Tools work in CLI but not WebUI | Same plugin path issue | Restart WebUI pod after env fix |

Verify inside the pod (as `hermeswebui`):

```bash
export HERMES_BUNDLED_PLUGINS=/opt/hermes/plugins HERMES_HOME=/home/hermeswebui/.hermes
cd /app && /app/venv/bin/python -c "
from hermes_cli.plugins import discover_plugins
discover_plugins()
from agent.web_search_registry import list_providers
print([p.name for p in list_providers()])
from tools.web_tools import web_search_tool
print(web_search_tool(query='test', limit=1)[:120])
"
```

Expect provider names including `searxng` and `"success": true`.

## Troubleshooting

| Issue | Check |
|-------|--------|
| **404 nginx** on `https://hermes.<domain>/` | Hermes HelmRelease not deployed — check `kubectl get helmrelease -n ai hermes-oncall` and `my-apps/ai/kustomization.yaml` includes `hermes-oncall/ks.yaml`. Only `/homelab/api` ingress alone returns 404 on `/`. |
| WebUI ImagePullBackOff | Build/push `hermes-homelab` image on `main` |
| Ask AI 404 incident | Bridge running? `kubectl logs -n observability deploy/homelab-alert-bridge` |
| Ask AI / triage 502 Hermes | Bridge must use Service **`hermes-oncall-app-template`** (app-template chart name), not `hermes-oncall`. Gateway on :8644: `curl -sS -o /dev/null -w '%{http_code}' http://hermes-oncall-app-template.ai.svc:8644/health` → `200`. Rebuild `hermes-homelab` ≥ 1.1.2 if gateway missing; check `kubectl logs deploy/hermes-oncall-app-template -n ai \| grep start-gateway`. |
| Gateway never starts | `start-gateway` waits for `/app/venv/bin/hermes` (pre-baked venv rsync ~1 min on 1.1.13+). Existing PVCs missing `platforms.webhook` in `config.yaml` are patched at gateway start. |
| **Gateway not configured** (orange pill) but `hermes gateway status` OK | Usually **root-owned** `gateway_state.json` from an older image while WebUI runs as `hermeswebui`. Fix: `hermes-homelab` ≥ 1.1.3 runs the gateway as `hermeswebui`, or `chown hermeswebui:hermeswebui ~/.hermes/gateway*` and restart the pod. |
| No kubectl in chat | Ensure `hermes-homelab` image (not upstream `nesquena/hermes-webui` alone) |
| Weak responses | Ollama up? `kubectl get pods -n ai -l app.kubernetes.io/instance=ollama` |
| **Connection error** in chat | Hermes logs show `ollama-api.ai.svc.cluster.local`? Use **`ollama.ai.svc.cluster.local:11434/v1`** (Service `ollama`) or apply `ollama-api` cluster DNS alias. `ollama-api.${DOMAIN_0}` is ingress-only. |
| **Missing imports: run_agent** | Use **`hermes-homelab`** image (includes agent at `/opt/hermes`), not upstream WebUI alone. Image ≥ **1.1.13** pre-bakes the venv; pod should be ready in ~1–2 min. |
| **0 builtin skills** | Set **`HERMES_BUNDLED_SKILLS=/opt/hermes/skills`**; gateway/`ensure-homelab-config.py` runs `skills sync` on start. |
| Provider incomplete | Check logs for `Dependencies already installed — skipping`; rebuild if stuck on runtime `uv pip install`. |

See also [Observability](mk_observability.md) and [Alert runbooks](runbooks/mk_runbook_index.md).
