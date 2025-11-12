# Coqui TTS - Text-to-Speech Service

## Overview

Coqui TTS is a fully self-hosted text-to-speech service that supports voice cloning and custom voice models. Perfect for creating a Jarvis-style voice assistant.

## Features

- **Fully Self-Hosted**: No external API dependencies
- **Voice Cloning**: Train custom voices from audio samples
- **Multiple Models**: Various pre-trained models available
- **GPU Support**: Can use GPU acceleration (when CUDA driver is updated)
- **REST API**: Simple HTTP API for integration

## Access

- **Internal Service**: `http://coqui-tts-app-template.ai.svc.cluster.local:5002`
- **Ingress**: `https://coqui-tts.${DOMAIN_0}` (internal access only)

## API Usage

### Basic Text-to-Speech

```bash
curl -X POST "http://coqui-tts-app-template.ai.svc.cluster.local:5002/api/tts" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Hello, I am Jarvis. How may I assist you today?",
    "speaker_wav": null,
    "language": "en"
  }' \
  --output response.wav
```

### Using Custom Voice (After Cloning)

```bash
curl -X POST "http://coqui-tts-app-template.ai.svc.cluster.local:5002/api/tts" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Hello, I am Jarvis.",
    "speaker_wav": "/path/to/jarvis_voice_sample.wav",
    "language": "en"
  }' \
  --output jarvis_response.wav
```

## Voice Cloning for Jarvis

### Step 1: Prepare Audio Samples

1. **Collect Jarvis Voice Samples:**
   - Get 1-5 minutes of clear Jarvis voice audio
   - Clean audio, no background noise
   - Single speaker only
   - Format: WAV, 16kHz or 22kHz recommended

2. **Upload Samples to Pod:**
   ```bash
   kubectl cp jarvis_samples/ coqui-tts-app-template-xxx:/tmp/jarvis_samples/
   ```

### Step 2: Clone Voice

1. **Access the Pod:**
   ```bash
   kubectl exec -it -n ai deployment/coqui-tts-app-template -- bash
   ```

2. **Use Coqui TTS Voice Cloning:**
   ```bash
   # Install additional dependencies if needed
   pip install TTS
   
   # Clone voice from samples
   tts --text "This is a test" \
       --model_path tts_models/en/ljspeech/tacotron2-DDC \
       --speaker_wav /tmp/jarvis_samples/sample1.wav \
       --out_path /tmp/jarvis_test.wav
   ```

3. **Train Custom Model (Advanced):**
   - Requires more setup and training time
   - See Coqui TTS documentation for full voice cloning guide

### Step 3: Use Cloned Voice in API

Once you have a voice sample file, use it in API calls:

```json
{
  "text": "Your text here",
  "speaker_wav": "/path/to/jarvis_sample.wav",
  "language": "en"
}
```

## n8n Integration

### HTTP Request Node Configuration

**Method:** `POST`

**URL:**
```
http://coqui-tts-app-template.ai.svc.cluster.local:5002/api/tts
```

**Headers:**
```
Content-Type: application/json
```

**Body (JSON):**
```json
{
  "text": "={{ $json.response }}",
  "speaker_wav": null,
  "language": "en"
}
```

**Response:**
- Returns WAV audio file as binary data
- n8n will handle it automatically
- Can be returned to user or saved

### Complete Voice Assistant Workflow

```
Webhook (voice input)
  ↓
Whisper (STT) - transcribe audio to text
  ↓
AI Agent/Ollama - process & generate response
  ↓
HTTP Request (Coqui TTS) - convert text to speech
  - URL: http://coqui-tts-app-template.ai.svc.cluster.local:5002/api/tts
  - Method: POST
  - Body: JSON with text and optional speaker_wav
  ↓
Response contains audio file (binary)
  ↓
Return audio to user
```

## Available Models

Coqui TTS supports many pre-trained models. Common ones:

- `tts_models/en/ljspeech/tacotron2-DDC` - Default English model
- `tts_models/en/ljspeech/vits` - VITS model (faster)
- `tts_models/en/vctk/vits` - Multi-speaker model
- `tts_models/en/ljspeech/glow-tts` - Glow-TTS model

List all available models:
```bash
kubectl exec -it -n ai deployment/coqui-tts-app-template -- tts --list_models
```

## Storage

Models and voice samples are stored in:
- **NFS Path**: `${NFS_APP_CONFIGS}/coqui-tts/models`
- **Container Path**: `/root/.local/share/tts`

Models are downloaded automatically on first use and persisted across pod restarts.

## GPU Support

Currently configured for CPU-only due to CUDA driver compatibility (12.2 vs required 12.6+).

To enable GPU when driver is updated:
1. Change image tag to `v0.22.0-cuda11.8.0`
2. Uncomment GPU resource requests/limits
3. Uncomment `runtimeClassName: "nvidia"`
4. Uncomment GPU tolerations

## Troubleshooting

### Models Not Downloading
- Check pod logs: `kubectl logs -n ai deployment/coqui-tts-app-template`
- Ensure NFS persistence is mounted correctly
- Check network connectivity for model downloads

### Voice Cloning Not Working
- Ensure audio samples are clean and clear
- Check audio format (WAV recommended)
- Verify speaker_wav path is correct

### High Memory Usage
- Coqui TTS can use significant memory
- Current limits: 4Gi (adjust if needed)
- Consider using lighter models for lower memory usage

## Resources

- [Coqui TTS Documentation](https://github.com/coqui-ai/TTS)
- [Voice Cloning Guide](https://github.com/coqui-ai/TTS/wiki/Voice-Cloning)
- [API Documentation](https://github.com/coqui-ai/TTS/wiki/Using-the-server-API)

