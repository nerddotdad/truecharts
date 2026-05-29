# hermes-homelab

Extends [nesquena/hermes-webui](https://github.com/nesquena/hermes-webui) for homelab on-call:

- **[Hermes Agent](https://github.com/NousResearch/hermes-agent)** cloned to `/opt/hermes` at image build (`run_agent` import)
- `kubectl` + `flux` CLI (read-only triage via in-cluster ServiceAccount)
- Skill `homelab-k8s-flux-triage` (GitOps-mounted from `hermes-oncall/app/agent-config/`, not in image)
- Alert deep-link extension (`?incident=&autostart=1`) auto-starts triage via WebUI APIs
- Ollama provider seed (`qwen3.5:9b` → `ollama-api.ai.svc`)

Built by **Build Custom Docker Images** on push to `custom_images/hermes-homelab/`.

- **`VERSION`** + CI publish `x.y.z` to GHCR (auto patch bump when you did not edit `VERSION` in the commit)
- **Renovate** updates `hermes-oncall/app/helm-release.yaml` (`tag: x.y.z@sha256:…`) when a newer tag is on GHCR

Deploy: `clusters/main/kubernetes/my-apps/ai/hermes-oncall/`
