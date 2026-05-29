# Hermes agent config (GitOps)

Edit files here and commit — **no `hermes-homelab` image rebuild** required.

## What belongs in Git vs PVC

| File | In Git? | On pod start |
|------|---------|--------------|
| `SOUL.md` | Yes — platform persona | **Always** copied to PVC |
| `skills/homelab-k8s-flux-triage/SKILL.md` | Yes — on-call triage | **Always** copied to PVC |
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

To reset **USER** to the Git seed: delete `memories/USER.md` on the PVC (or remove the file via exec), then roll the pod.

## Verify

```bash
kubectl exec -n ai deploy/hermes-oncall-app-template -c hermes-oncall-app-template -- \
  cat /home/hermeswebui/.hermes/memories/USER.md
```

Pick skill **`homelab-k8s-flux-triage`** in the WebUI for manual triage.
