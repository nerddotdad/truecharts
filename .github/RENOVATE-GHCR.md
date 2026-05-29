# Renovate + custom GHCR images

Renovate watches **three manifests** only (see `scripts/custom_image_manifest_map.yaml`):

| Image | Manifest |
|-------|----------|
| `hermes-homelab` | `hermes-oncall/app/helm-release.yaml` |
| `homelab-alert-bridge` | `homelab-alert-bridge/app/deployment.yaml` |
| `homelab-docs` | `homelab-docs/app/helm-release.yaml` |

When CI pushes a **new semver tag** to `ghcr.io/nerddotdad/<image>`, Renovate should open a PR like:

`chore(deps): update ghcr.io/nerddotdad/hermes-homelab to 1.1.3`

with `tag: 1.1.3@sha256:<digest>` (or the deployment `image:` line).

## What we disabled

- **Digest-only updates** (same tag, new build) — those caused dashboard errors on [issue #10](https://github.com/nerddotdad/truecharts/issues/10).
- **`custom_images/*/VERSION`** as a Renovate dep — VERSION is written by CI, not the registry.
- **All other `helm-release.yaml` files** — no accidental custom-image regex matches.

## If PRs stay in “Errored” on the dashboard

The Mend Renovate GitHub App often **cannot read GHCR** with its default token. Add a host rule password once:

1. Create a GitHub PAT with **`read:packages`** (classic) or fine-grained **packages read** for your org/user.
2. In [Mend Renovate](https://developer.mend.io/) → your repo → **Settings** → **Encrypted secrets**, add a secret (e.g. `GHCR_PAT`).
3. In the same UI, **Host rules** (or extra `renovate.json` in the app config):

```json
{
  "hostType": "docker",
  "matchHost": "ghcr.io",
  "username": "nerddotdad",
  "encrypted": {
    "password": "<your encrypted GHCR_PAT>"
  }
}
```

Use the field **`password`**, not `token`.

4. On [Renovate Dashboard #10](https://github.com/nerddotdad/truecharts/issues/10), check **“re-run Renovate”**.

Public packages sometimes work without a PAT; private packages require this step.

## Fallback (no Renovate)

After **Build Custom Docker Images** finishes, run **Sync custom image tags** (`workflow_dispatch`) with image / version / digest from the job log, or:

```bash
python scripts/bump_custom_image_manifest.py \
  --image hermes-homelab --version 1.1.3 --digest sha256:...
```
