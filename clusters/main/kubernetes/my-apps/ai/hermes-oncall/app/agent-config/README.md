# Hermes agent config (GitOps)

Edit files here and commit — **no `hermes-homelab` image rebuild** required.

| Path | Role |
|------|------|
| `SOUL.md` | Agent persona / priorities (`~/.hermes/SOUL.md` in pod) |
| `USER.md` | Operator context (`~/.hermes/USER.md` in pod) |
| `skills/*/SKILL.md` | Hermes skills (`HERMES_OPTIONAL_SKILLS_DIR`) |

Kustomize builds ConfigMaps `hermes-oncall-agent` and `hermes-oncall-skills`; the HelmRelease mounts them.

After changing these files, bump `homelab.agent-config/version` in `helm-release.yaml` so Flux rolls the pod and picks up new content.
