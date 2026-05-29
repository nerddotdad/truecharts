# Custom image version bumps

**CI owns this**, not Renovate.

1. Push changes under `custom_images/<name>/` → **Build Custom Docker Images** (or **Build Homelab Docs**).
2. Workflow publishes to GHCR, then **sync-custom-image-tags** opens a PR updating:
   - `custom_images/<name>/VERSION`
   - Cluster pins in `scripts/custom_image_manifest_map.yaml` manifests
3. Merge that PR → Flux deploys the new tag.

Renovate has `enabled: false` for `ghcr.io/nerddotdad/*` custom images to avoid fighting CI and GHCR digest lookup errors on [dashboard #10](https://github.com/nerddotdad/truecharts/issues/10).

Manual bump (emergency):

```bash
python scripts/bump_custom_image_manifest.py --image hermes-homelab --version 1.1.3 --digest sha256:...
```
