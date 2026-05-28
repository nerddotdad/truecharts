# hermes-homelab

Extends [nesquena/hermes-webui](https://github.com/nesquena/hermes-webui) for homelab on-call:

- `kubectl` + `flux` CLI (read-only triage via in-cluster ServiceAccount)
- Skill `homelab-k8s-flux-triage`
- Alert deep-link extension + prefill script
- Ollama provider seed (`qwen3.5:9b` → `ollama-api.ai.svc`)

Built by **Build Custom Docker Images** on push to `custom_images/hermes-homelab/`.

Deploy: `clusters/main/kubernetes/my-apps/ai/hermes-oncall/`
