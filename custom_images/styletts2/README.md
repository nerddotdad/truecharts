# StyleTTS2 Docker Image

Docker image for StyleTTS2 TTS API server with voice cloning support.

## What's Included

- PyTorch 2.1.0 with CUDA 11.8 support
- StyleTTS2 package and all dependencies
- Flask API server for REST API
- Build tools (gcc, g++) for compiling Python extensions

## Building

The image is automatically built by GitHub Actions when files in this directory change.

### Local Testing (Recommended)

Before pushing changes, test the build locally:

```bash
# Run the test script (builds and tests the image)
./test-build.sh

# Or build manually and test
docker build -t styletts2-test:local .
docker run --rm styletts2-test:local python3 -c "from styletts2 import tts; print('Import successful!')"
```

The test script will:
1. Build the Docker image
2. Test that `styletts2.tts` can be imported
3. Test that `api_server.py` can be imported
4. Report any errors before you push

### Manual Build

To build and push manually:

```bash
docker build -t ghcr.io/nerddotdad/styletts2:latest .
docker push ghcr.io/nerddotdad/styletts2:latest
```

## Usage

The image expects:
- Models mounted at `/app/models` (persistent volume)
- Voices mounted at `/app/voices` (persistent volume)

Models are automatically downloaded on first startup if not present.

## API

The container runs a Flask server on port 5003 with the following endpoints:

- `GET /` - Health check
- `GET /ready` - Readiness probe
- `POST /api/tts` - Generate speech
- `POST /api/upload-voice` - Upload voice samples
- `GET /api/voices` - List voices
- `POST /api/test-voice` - Test voice quality
- `DELETE /api/delete-voice` - Delete voices

See the main StyleTTS2 deployment README for usage examples.

