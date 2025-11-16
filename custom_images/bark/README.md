# Bark Docker Image

Docker image for Bark TTS API server with text-to-audio synthesis support.

## What's Included

- PyTorch 2.3.1 with CUDA 11.8 support
- Bark package and all dependencies
- Flask API server for REST API
- Support for 100+ voice presets
- Multilingual support (13 languages)

## Building

The image is automatically built by GitHub Actions when files in this directory change.

### Local Testing (Recommended)

Before pushing changes, test the build locally:

```bash
# Build and test the image
docker build -t bark-test:local .
docker run --rm bark-test:local python3 -c "from bark import SAMPLE_RATE; print('Import successful!')"
```

### Manual Build

To build and push manually:

```bash
docker build -t ghcr.io/nerddotdad/bark:latest .
docker push ghcr.io/nerddotdad/bark:latest
```

## Usage

The image expects:
- Models are automatically downloaded from Hugging Face on first use
- Outputs can be saved to `/app/outputs` (optional persistent volume)

## API

The container runs a Flask server on port 5004 with the following endpoints:

- `GET /` - Web UI
- `GET /ready` - Readiness probe
- `GET /api/status` - Server and model status
- `POST /api/models/load` - Preload models
- `POST /api/tts` - Generate speech from text
- `GET /api/voices` - List available voice presets

## Text Formatting

Bark supports special text tags for various effects:

- `[laughter]` or `[laughs]` - Laughing
- `[sighs]` - Sighing
- `[music]` - Music generation
- `[gasps]` - Gasping
- `[clears throat]` - Throat clearing
- `—` or `...` - Hesitations
- `♪` - Song lyrics
- CAPITALIZATION - Emphasis
- `[MAN]` and `[WOMAN]` - Gender bias

Example:
```
Hello, my name is Suno. And, uh — and I like pizza. [laughs]
```

## Voice Presets

Bark supports 100+ voice presets across 13 languages. Common presets:
- `v2/en_speaker_1` through `v2/en_speaker_9` (English)
- `v2/de_speaker_1` (German)
- `v2/es_speaker_1` (Spanish)
- `v2/fr_speaker_1` (French)
- And many more...

See the `/api/voices` endpoint for a list of available presets.

## Hardware Requirements

- **Full models**: ~12GB VRAM
- **Small models**: ~4GB VRAM (set `SUNO_USE_SMALL_MODELS=True`)
- **CPU**: Works but significantly slower

## Environment Variables

- `SUNO_USE_SMALL_MODELS`: Set to `True` for smaller models (<4GB VRAM)
- `SUNO_OFFLOAD_CPU`: Set to `True` to offload to CPU when needed

