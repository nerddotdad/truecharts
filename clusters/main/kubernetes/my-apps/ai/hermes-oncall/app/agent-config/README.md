# Hermes agent config (GitOps)

Edit files here and commit — **no `hermes-homelab` image rebuild** required.

## What belongs in Git vs PVC

| File | In Git? | On pod start |
|------|---------|--------------|
| `SOUL.md` | Yes — platform persona | **Always** copied to PVC |
| `model.yaml` | Yes — default profile model | **Always** merged into default `config.yaml` on gateway start |
| `skills/homelab-k8s-flux-triage/SKILL.md` | Yes — on-call triage | **Always** copied to PVC |
| `skills/jellyfin-api/SKILL.md` | Yes — Jellyfin API investigations | **Always** copied to PVC |
| `agent-profiles/<name>/config.yaml` | Yes — model overlay only | Cloned from default + overlay on gateway start (see `agent-profiles/README.md`) |
| `USER.md` | Optional **seed** only | Copied **only if** PVC has no `memories/USER.md` yet |
| `MEMORY.md` | **Never** | PVC only — agent-managed |
| Other `skills/*` | **Never** (unless you promote one) | PVC only — e.g. from WebUI |

Hermes paths (under `HERMES_HOME`):

- `SOUL.md`
- `memories/USER.md`, `memories/MEMORY.md`
- `skills/<name>/SKILL.md`

## Chart env vars (`helm-release.yaml`)

| Env var | Role |
|---------|------|
| `HERMES_HOME` | Writable PVC (`/home/hermeswebui/.hermes`) |
| `HERMES_OPTIONAL_SKILLS_DIR` | Extra skill scan (`/opt/homelab-skills`) |
| `HOMELAB_GITOPS_*` | ConfigMap staging paths for init |

After editing **SOUL** or **skills**, bump `homelab.agent-config/version` in `helm-release.yaml` to roll the pod.

Init uses **hardcoded paths** in the shell script (not `${VAR}`) because Flux `postBuild` substitution would empty unknown placeholders and break `cp`.

To reset **USER** to the Git seed: delete `memories/USER.md` on the PVC (or remove the file via exec), then roll the pod.

## Verify

```bash
kubectl exec -n ai deploy/hermes-oncall-app-template -c hermes-oncall-app-template -- \
  cat /home/hermeswebui/.hermes/memories/USER.md
```

Pick skills from **`recommended_ai_skills`** on the alert when present; otherwise start with **`homelab-k8s-flux-triage`** (and **`jellyfin-api`** for media alerts).

## Alert annotations (Prometheus → Ask AI)

| Annotation | Purpose |
|------------|---------|
| `runbook_url` | Primary MkDocs runbook link |
| `recommended_ai_skills` | Comma-separated Hermes skill names to try first (e.g. `homelab-k8s-flux-triage,jellyfin-api`) |

Set these on `PrometheusRule` alerts in `observability/prometheus-rules/`. Ask AI sends **`hermes_message`** from the bridge (ntfy text + agent context) — SOUL.md and skills define investigation behavior.
