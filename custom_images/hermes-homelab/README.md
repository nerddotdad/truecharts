# hermes-homelab

Extends [nesquena/hermes-webui](https://github.com/nesquena/hermes-webui) for homelab on-call:

- **[Hermes Agent](https://github.com/NousResearch/hermes-agent)** cloned to `/opt/hermes` at image build (`run_agent` import)
- **Pre-baked `/apptoo/venv`** — WebUI + `hermes-agent[all]` + plugins deps installed at build time (rsync’d to `/app` on start; skips runtime `uv pip install`)
- `HERMES_BUNDLED_SKILLS=/opt/hermes/skills` — upstream `skills_sync` excludes paths containing `venv`; bundled skills sync from the agent checkout instead
- `kubectl` + `flux` CLI (read-only triage via in-cluster ServiceAccount)
- Skill `homelab-k8s-flux-triage` + `jellyfin-api` (GitOps-mounted from `hermes-oncall/app/agent-config/`, not in image)
- Alert deep-link extension (`?incident=&autostart=1`) auto-starts triage via WebUI APIs
- Ollama provider seed (`qwen3.5:9b` → in-cluster Ollama), SearXNG web search, terminal `env_passthrough` for homelab secrets

Built by **Build Custom Docker Images** on push to `custom_images/hermes-homelab/`.

- **`VERSION`** + CI publish `x.y.z` to GHCR (auto patch bump when you did not edit `VERSION` in the commit)
- **Renovate** updates `hermes-oncall/app/helm-release.yaml` (`tag: x.y.z@sha256:…`) when a newer tag is on GHCR

Deploy: `clusters/main/kubernetes/my-apps/ai/hermes-oncall/`
