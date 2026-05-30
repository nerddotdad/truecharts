# Hermes named profiles (GitOps)

Named profiles live on the PVC at `~/.hermes/profiles/<name>/`. Each profile is an isolated Hermes home (config, sessions, skills, memory).

## In Git

| Path | Profile | Synced to PVC |
|------|---------|---------------|
| `gemma4/config.yaml` | `gemma4` | Always — model `gemma4:latest` via Ollama |

On pod start the initContainer also copies **SOUL.md**, **USER.md** (seed-only), and homelab **skills** into each GitOps profile (same as the default profile).

## Add another profile

1. Create `agent-profiles/<name>/config.yaml` (`<name>` must match `[a-z0-9][a-z0-9_-]{0,63}`).
2. Add a ConfigMap entry in `app/kustomization.yaml`.
3. Add mount `items` + initContainer bootstrap block in `helm-release.yaml` (copy the `gemma4` pattern).
4. Bump `homelab.agent-config/version` in `helm-release.yaml` to roll the pod.

Switch profiles in Hermes WebUI: **Control Center → Profiles**.
