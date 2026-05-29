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

### Image versioning and Renovate (standard flow)

```text
Push custom_images/<name>/  →  CI bumps VERSION (patch)  →  GHCR tag 1.0.5
                           →  Renovate PR updates cluster pin  →  Flux deploys
```

1. **`custom_images/<name>/VERSION`** — semver source of truth (`1.1.4`). Edit this file yourself for **minor/major** releases.
2. **CI** (`docker/metadata-action`) pushes `ghcr.io/nerddotdad/<name>:<VERSION>` on each build. If you did not change `VERSION` in the commit, CI auto-increments **patch** and commits `VERSION` back with `[skip ci]`.
3. **Cluster pins** — TrueCharts `tag: 1.1.4@sha256:…` in `helm-release.yaml`, or `image: …:1.0.0@sha256:…` in `deployment.yaml`, each with a `# renovate: datasource=docker depName=…` comment.
4. **Renovate** (`.github/renovate.json5` regex manager) queries GHCR and opens PRs to bump tag + digest. Merge → Flux reconciles.

GHCR also gets `main-<sha>` and `latest` (on `main`); cluster pins should always use the semver@sha256 form above.

## Adding a New Custom Image

1. Create a new directory: `custom_images/my-new-image/`
2. Add your `Dockerfile` and any required files
3. Optionally add a `README.md` with build/usage instructions
4. Add `echo "1.0.0" > custom_images/my-new-image/VERSION` and push — CI builds `1.0.0`, then Renovate can pin it in the cluster

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
