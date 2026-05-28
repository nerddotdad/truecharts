# hermes-homelab

Extends [nesquena/hermes-webui](https://github.com/nesquena/hermes-webui) for homelab on-call:

- **[Hermes Agent](https://github.com/NousResearch/hermes-agent)** cloned to `/opt/hermes` at image build (`run_agent` import)
- `kubectl` + `flux` CLI (read-only triage via in-cluster ServiceAccount)
- Skill `homelab-k8s-flux-triage`
- Alert deep-link extension (`?incident=&autostart=1`) auto-starts triage via WebUI APIs
- Ollama provider seed (`qwen3.5:9b` → `ollama-api.ai.svc`)

Built by **Build Custom Docker Images** on push to `custom_images/hermes-homelab/`.

- **`VERSION`** — semver tag pushed to GHCR; patch auto-bumps on each build unless you edit `VERSION` in the same commit
- **Renovate** updates `hermes-oncall/app/helm-release.yaml` when a newer tag appears on GHCR

Deploy: `clusters/main/kubernetes/my-apps/ai/hermes-oncall/`
