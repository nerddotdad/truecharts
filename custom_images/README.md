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

For example:
- `ghcr.io/nerddotdad/styletts2:latest`
- `ghcr.io/nerddotdad/styletts2:main-<sha>`

### GitHub Container Registry

GHCR is **free** for:
- Public repositories (unlimited)
- Private repositories (generous free tier)

No authentication needed for public images. For private images, use a GitHub Personal Access Token with `read:packages` scope.

## Adding a New Custom Image

1. Create a new directory: `custom_images/my-new-image/`
2. Add your `Dockerfile` and any required files
3. Optionally add a `README.md` with build/usage instructions
4. Commit and push - the image will be built automatically

## Using Images in Kubernetes

Update your HelmRelease to use the GHCR image:

```yaml
image:
  repository: ghcr.io/nerddotdad/styletts2
  pullPolicy: IfNotPresent
  tag: "latest"  # or use a specific tag like "main-abc123"
```

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

