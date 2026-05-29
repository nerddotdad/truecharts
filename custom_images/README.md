# Custom Docker Images

This directory contains custom Docker images for applications that aren't available as pre-built images or need custom configurations.

## Structure

Each custom image should be in its own subdirectory:

```
custom_images/
  ├── styletts2/
  │   ├── Dockerfile
  │   ├── api_server.py
  │   └── README.md (optional)
  └── another-image/
      ├── Dockerfile
      └── ...
```

## Automatic Building

Images are automatically built and pushed to GitHub Container Registry (GHCR) when:

1. **Files in `custom_images/` are changed** and pushed to `main` branch
2. **Manually triggered** via GitHub Actions workflow dispatch

**Exception — `homelab-docs`:** uses **Build Homelab Docs** (`.github/workflows/build-homelab-docs.yml`) with the **repository root** as Docker context (`clusters/`, `mkdocs/`, `scripts/`). It is excluded from **Build Custom Docker Images**.

### Image Registry

Images are pushed to: `ghcr.io/nerddotdad/<image-name>`

### Image Versioning

CI uses **[PaulHatch/semantic-version](https://github.com/PaulHatch/semantic-version)** per image:

- Git tags: `{major}.{minor}.{patch}-{image-name}` (e.g. `1.1.4-hermes-homelab`)
- Each successful build on `main` bumps the **patch** (`bump_each_commit`)
- For **minor** / **major** bumps, adjust `bump_each_commit` in the workflow and use conventional commits (`feat:`, `BREAKING CHANGE:`, etc.)

Docker image tags on GHCR:

1. **Semantic version** (primary) — e.g. `1.1.4` — use in Helm/deploy pins via Renovate
2. **SHA-based** — `main-<sha>`
3. **`latest`** on `main` only

### One-time baseline tags (after removing `VERSION` files)

If an image already exists on GHCR, seed git tags once so the next CI build does not restart from `0.0.x`:

```bash
git tag 1.1.3-hermes-homelab
git tag 1.1.0-homelab-alert-bridge
git tag 1.0.12-homelab-docs
git tag 1.0.23-styletts2
git tag 1.0.4-bark
git push origin --tags
```

Adjust versions to match what is currently on GHCR.

## Adding a New Custom Image

1. Create a new directory: `custom_images/my-new-image/`
2. Add your `Dockerfile` and any required files
3. Optionally add a `README.md` with build/usage instructions
4. Commit and push — the first build creates `0.0.1-my-new-image` (or seed `1.0.0-my-new-image` before the first push if you prefer)

## Using Images in Kubernetes

Update your HelmRelease to use the GHCR image with the semantic version tag:

```yaml
image:
  repository: ghcr.io/nerddotdad/styletts2
  pullPolicy: IfNotPresent
  # renovate: datasource=docker depName=ghcr.io/nerddotdad/styletts2
  tag: 1.0.0@sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef
```

Use the TrueCharts-style `semver@sha256:…` pin (not bare semver or `latest`).

### Updating Image Versions

1. Change Dockerfile/source and push to `main` — CI publishes the next semver tag to GHCR.
2. **Renovate** opens a PR updating cluster pins (`helm-release.yaml` / `deployment.yaml`) to the new `semver@sha256:…` tag.
3. Merge the Renovate PR — Flux reconciles and pulls the new image.

Helm/deploy manifests use semver@sha256 pins plus Renovate annotations, for example:

```yaml
# renovate: datasource=docker depName=ghcr.io/nerddotdad/my-image
tag: 1.0.0@sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef
```

You do not need `pullPolicy: Always` when using pinned semver@sha256 tags.

### For Private Images

If your repository is private, you'll need to create a Kubernetes secret:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: ghcr-secret
type: kubernetes.io/dockerconfigjson
data:
  .dockerconfigjson: <base64-encoded-docker-config>
```

Reference it in your HelmRelease values as an image pull secret.

## Workflow Files

- `.github/workflows/build-custom-images.yml` — all images except `homelab-docs`
- `.github/workflows/build-homelab-docs.yml` — docs site image (repo root context)
