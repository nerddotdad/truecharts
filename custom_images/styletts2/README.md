# StyleTTS2 Docker Image

Docker image for StyleTTS2 TTS API server with voice cloning support.

## What's Included

- PyTorch 2.1.0 with CUDA 11.8 support
- StyleTTS2 package and all dependencies
- Flask API server for REST API
- Build tools (gcc, g++) for compiling Python extensions

## Building

The image is automatically built by GitHub Actions when files in this directory change.

To build manually:

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

