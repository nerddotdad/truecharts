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

### Image Registry

Images are pushed to: `ghcr.io/nerddotdad/<image-name>`

### Image Versioning

Images are tagged with multiple tags:

1. **Semantic Version** (primary tag) - From `VERSION` file or date-based
   - If `custom_images/<image>/VERSION` exists, uses that version (e.g., `1.0.0`)
   - Otherwise uses date-based versioning (e.g., `2025.01.14-1706`)
   - **Use this tag in your Helm charts** to ensure Kubernetes pulls new images

2. **SHA-based tag** - `main-<sha>` (e.g., `main-abc123def456`)
   - Unique per commit, useful for tracking specific builds

3. **Latest tag** - `latest` (only on main branch)
   - Always points to the newest build, but Kubernetes won't auto-pull with `IfNotPresent` policy

**Example tags for styletts2:**
- `ghcr.io/nerddotdad/styletts2:1.0.0` (semantic version - use this!)
- `ghcr.io/nerddotdad/styletts2:main-abc123def456` (SHA-based)
- `ghcr.io/nerddotdad/styletts2:latest` (always latest)

### GitHub Container Registry

GHCR is **free** for:
- Public repositories (unlimited)
- Private repositories (generous free tier)

No authentication needed for public images. For private images, use a GitHub Personal Access Token with `read:packages` scope.

## Adding a New Custom Image

1. Create a new directory: `custom_images/my-new-image/`
2. Add your `Dockerfile` and any required files
3. Optionally create a `VERSION` file with semantic version (e.g., `1.0.0`)
   - If no `VERSION` file exists, date-based versioning will be used
4. Optionally add a `README.md` with build/usage instructions
5. Commit and push - the image will be built automatically

### Versioning Your Image

To use semantic versioning, create a `VERSION` file in your image directory:

```bash
echo "1.0.0" > custom_images/my-new-image/VERSION
```

When you make changes and want to release a new version, update the `VERSION` file:
- Patch: `1.0.1` (bug fixes)
- Minor: `1.1.0` (new features, backwards compatible)
- Major: `2.0.0` (breaking changes)

## Using Images in Kubernetes

Update your HelmRelease to use the GHCR image with the semantic version tag:

```yaml
image:
  repository: ghcr.io/nerddotdad/styletts2
  pullPolicy: IfNotPresent
  tag: "1.0.0"  # Use semantic version from VERSION file
```

**Important:** Always use the semantic version tag (not `latest`) to ensure Kubernetes pulls new images when you update the version. The `latest` tag doesn't change, so Kubernetes won't detect updates with `IfNotPresent` pull policy.

### Updating Image Versions

1. Make your changes to the Dockerfile or source files
2. Update the `VERSION` file in the image directory (e.g., `1.0.0` → `1.0.1`)
3. Update the `tag` in your HelmRelease to match the new version
4. Commit and push - the new image will be built with the new version tag
5. Flux will detect the HelmRelease change and pull the new image

### For Private Images

If your repository is private, you'll need to create a Kubernetes secret:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: ghcr-secret
  namespace: your-namespace
type: kubernetes.io/dockerconfigjson
data:
  .dockerconfigjson: <base64-encoded-docker-config>
```

Or use a GitHub Personal Access Token in your HelmRelease values.

## Manual Build

To build an image manually:

```bash
cd custom_images/styletts2
docker build -t ghcr.io/nerddotdad/styletts2:latest .
docker push ghcr.io/nerddotdad/styletts2:latest
```

## Current Images

- **styletts2** - StyleTTS2 TTS API server with voice cloning support

