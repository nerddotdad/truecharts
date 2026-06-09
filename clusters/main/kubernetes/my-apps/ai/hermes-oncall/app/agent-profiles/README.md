# Hermes named profiles (GitOps)

Named profiles live on the PVC at `~/.hermes/profiles/<name>/`.

## How it works

On **gateway start** (after bundled skills sync on the default profile), `sync-gitops-profiles.py`:

1. Copies the **full default** `config.yaml` (webhook, terminal, browser, …)
2. Applies the GitOps **model overlay** from `agent-profiles/<name>/config.yaml`
3. Mirrors **all skills** from `~/.hermes/skills/`
4. Copies **SOUL.md** and seeds **USER.md** (if missing)
5. Mirrors **gateway_state.json** so WebUI shows gateway status (gateway process stays on default)

Result: same capabilities as default, different default model.

## Switch default model without a profile

Edit `agent-config/model.yaml` (default profile) or use **WebUI → Control Center → model picker** (instant; persists on PVC until pod restart).

## Add another profile

1. Create `agent-profiles/<name>/config.yaml` with a `model:` block only.
2. Add ConfigMap entry in `app/kustomization.yaml`.
3. Add mount `items` in `helm-release.yaml` (`homelab-profiles` volume).
4. Bump `homelab.agent-config/version`.

Requires `hermes-homelab` **≥ 1.1.19** (profile sync script in the image).
