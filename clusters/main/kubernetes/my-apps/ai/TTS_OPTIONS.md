# Text-to-Speech (TTS) Options for Voice Assistant

## Overview

Whisper handles **Speech-to-Text** (STT) - converting audio to text.
For **Text-to-Speech** (TTS) - converting text to audio - you need a separate service.

## Self-Hosted TTS Options

### Option 1: Piper TTS (Recommended - Lightweight)

**Pros:**
- Very lightweight and fast
- Low resource usage
- Good quality voices
- Easy to deploy
- Fully local/private

**Deployment:**
- Docker image: `rhasspy/piper` or `mozilla/piper-tts`
- API endpoint for text-to-speech
- Multiple voice models available

**n8n Integration:**
- HTTP Request node to Piper API
- Returns audio file (WAV/MP3)
- Can be played back or saved

### Option 2: Coqui TTS (Advanced)

**Pros:**
- High-quality neural TTS
- Multiple voice models
- More natural sounding
- GPU acceleration supported

**Cons:**
- Higher resource usage
- More complex setup

### Option 3: n8n Community Nodes

**ElevenLabs Node:**
- High-quality voices
- Requires API key (not fully self-hosted)
- Easy integration

**Google Cloud TTS Node:**
- Good quality
- Requires API key
- Free tier available

## Recommended: Piper TTS

For a fully self-hosted solution, **Piper TTS** is the best choice:
- Lightweight (can run on CPU)
- Fast response times
- Good quality
- Multiple voice options
- Simple API

## Complete Voice Assistant Pipeline

```
1. Voice Input (Webhook)
   ↓
2. Whisper (STT) - Convert audio → text
   ↓
3. AI Agent/Ollama - Process command, generate response
   ↓
4. Piper TTS (TTS) - Convert text → audio
   ↓
5. Return audio file to user
```

## Next Steps

Would you like me to:
1. Deploy Piper TTS in your cluster?
2. Set up the complete voice assistant workflow?
3. Configure n8n to integrate TTS?

Let me know and I'll create the deployment configuration!

