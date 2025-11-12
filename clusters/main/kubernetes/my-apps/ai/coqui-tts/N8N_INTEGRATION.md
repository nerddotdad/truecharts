# Coqui TTS n8n Integration Guide

## Overview

This guide shows how to integrate Coqui TTS into your n8n workflow to generate speech from text, including using custom Jarvis voice.

## Basic Setup

### Step 1: Add HTTP Request Node

After your AI Agent/Ollama node that generates the text response:

1. **Add HTTP Request Node**
2. **Configure:**
   - **Method**: `POST`
   - **URL**: `http://coqui-tts-app-template.ai.svc.cluster.local:5002/api/tts`
   - **Authentication**: None (internal cluster)
   - **Body Content Type**: `JSON`

### Step 2: Configure Request Body

**Specify Body (JSON):**
```json
{
  "text": "={{ $json.text }}",
  "speaker_wav": null,
  "language": "en"
}
```

Or if you have a custom Jarvis voice sample:
```json
{
  "text": "={{ $json.text }}",
  "speaker_wav": "/path/to/jarvis_sample.wav",
  "language": "en"
}
```

### Step 3: Handle Response

The API returns a WAV audio file as binary data. n8n will automatically handle it.

**To return audio:**
- The response will be in `$json.binary` or `$binary`
- You can pass it directly to your webhook response

## Complete Workflow Example

```
1. Webhook (receives voice input)
   ↓
2. Whisper (STT) - transcribe audio
   - HTTP Request to: http://whisper-app-template.ai.svc.cluster.local:9000/asr
   - Extract text from response
   ↓
3. AI Agent/Ollama - generate response
   - Process transcribed text
   - Generate AI response
   ↓
4. Coqui TTS - convert text to speech
   - HTTP Request to: http://coqui-tts-app-template.ai.svc.cluster.local:5002/api/tts
   - Body: { "text": "={{ $json.text }}", "language": "en" }
   ↓
5. Return audio to user
   - Response contains binary audio data
```

## Using Custom Jarvis Voice

### Option 1: Voice Cloning with Speaker WAV

If you've cloned a voice and have a sample file:

1. **Upload voice sample to Coqui TTS pod:**
   ```bash
   kubectl cp jarvis_sample.wav coqui-tts-app-template-xxx:/tmp/jarvis_sample.wav
   ```

2. **Use in API call:**
   ```json
   {
     "text": "={{ $json.text }}",
     "speaker_wav": "/tmp/jarvis_sample.wav",
     "language": "en"
   }
   ```

### Option 2: Trained Custom Model

If you've trained a custom model:

1. **Load custom model in server** (requires server restart with model path)
2. **Use model name in API:**
   ```json
   {
     "text": "={{ $json.text }}",
     "model_name": "jarvis_custom_model",
     "language": "en"
   }
   ```

## Advanced: Voice Cloning Setup

### Step 1: Prepare Audio Samples

1. Collect 1-5 minutes of Jarvis voice audio
2. Clean, clear recordings
3. Single speaker
4. WAV format, 16kHz or 22kHz

### Step 2: Clone Voice

Access the Coqui TTS pod and clone the voice:

```bash
kubectl exec -it -n ai deployment/coqui-tts-app-template -- bash

# Inside pod
tts --text "This is a test of the Jarvis voice" \
    --model_path tts_models/en/ljspeech/tacotron2-DDC \
    --speaker_wav /tmp/jarvis_samples/sample1.wav \
    --out_path /tmp/jarvis_test.wav
```

### Step 3: Use in n8n

Once you have a working voice sample, reference it in your HTTP Request:

```json
{
  "text": "={{ $json.text }}",
  "speaker_wav": "/tmp/jarvis_sample.wav",
  "language": "en"
}
```

## Response Handling

The Coqui TTS API returns audio as binary data. In n8n:

**Check Response:**
- Add a Function node after HTTP Request to inspect:
  ```javascript
  return {
    json: {
      hasBinary: !!$input.first().binary,
      binaryKeys: Object.keys($input.first().binary || {}),
      contentType: $input.first().headers?.['content-type']
    }
  };
  ```

**Return Audio:**
- The binary data can be returned directly in your webhook response
- n8n will handle the binary data automatically

## Error Handling

Add error handling in your workflow:

```javascript
// Function node after HTTP Request
try {
  const response = $input.first();
  if (response.statusCode === 200 && response.binary) {
    return response;
  } else {
    throw new Error(`TTS failed: ${response.statusCode}`);
  }
} catch (error) {
  return {
    json: {
      error: error.message,
      fallback: "Text response only"
    }
  };
}
```

## Testing

Test the integration:

1. **Test TTS directly:**
   ```bash
   curl -X POST "http://coqui-tts-app-template.ai.svc.cluster.local:5002/api/tts" \
     -H "Content-Type: application/json" \
     -d '{"text": "Hello, I am Jarvis.", "language": "en"}' \
     --output test.wav
   ```

2. **Test in n8n:**
   - Create a simple workflow with just the HTTP Request node
   - Use static text first
   - Verify audio is returned correctly

3. **Test full workflow:**
   - Send voice input via webhook
   - Verify end-to-end: voice → text → AI → speech → audio

## Troubleshooting

**No audio returned:**
- Check pod logs: `kubectl logs -n ai deployment/coqui-tts-app-template`
- Verify service is running: `kubectl get pods -n ai | grep coqui`
- Test API directly with curl

**Wrong voice:**
- Try different models
- Check speaker_wav path is correct
- Verify voice sample is valid

**Slow response:**
- Coqui TTS can be slower on CPU
- Consider using lighter models
- Enable GPU when CUDA driver is updated

## Next Steps

1. Deploy Coqui TTS (configuration is ready)
2. Test basic TTS with default voice
3. Collect Jarvis voice samples
4. Clone voice using Coqui TTS
5. Integrate into n8n workflow
6. Test complete voice assistant pipeline

