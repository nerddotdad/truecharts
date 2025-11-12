# ElevenLabs Integration for Jarvis Voice

## Overview

ElevenLabs provides high-quality text-to-speech with voice cloning capabilities, perfect for creating a Jarvis-style voice.

## Setup Steps

### 1. Get ElevenLabs API Key

1. Sign up at https://elevenlabs.io
2. Go to your profile → API Keys
3. Create a new API key
4. Copy the key (starts with something like `sk-...`)

### 2. Add API Key to n8n Credentials

1. In n8n, go to **Settings** → **Credentials**
2. Click **Add Credential**
3. Search for "ElevenLabs" or create a custom HTTP Auth credential
4. Store your API key securely

### 3. Option A: Use ElevenLabs Community Node (if available)

1. Go to **Settings** → **Community Nodes**
2. Search for "elevenlabs" or "eleven labs"
3. Install the node package
4. Add the node to your workflow
5. Configure with your API key
6. Select a voice (they have Jarvis-like options)

### 4. Option B: Use HTTP Request Node (Recommended)

Since community nodes may not be available, use HTTP Request node:

#### Configuration:

**Method:** `POST`

**URL:** 
```
https://api.elevenlabs.io/v1/text-to-speech/{voice_id}
```

**Authentication:**
- Type: Header Auth
- Name: `xi-api-key`
- Value: `YOUR_ELEVENLABS_API_KEY`

**Body:**
- Content Type: `JSON`
- Body:
```json
{
  "text": "={{ $json.response }}",
  "model_id": "eleven_multilingual_v2",
  "voice_settings": {
    "stability": 0.5,
    "similarity_boost": 0.75,
    "style": 0.0,
    "use_speaker_boost": true
  }
}
```

#### Finding a Jarvis-like Voice ID

1. Go to https://elevenlabs.io/app/voices
2. Browse voices or search for "British" or "Professional" voices
3. Click on a voice you like
4. Copy the Voice ID from the URL or voice settings
5. Replace `{voice_id}` in the API URL

#### Example Voice IDs (may change):

- **British Professional:** Look for voices with "British" accent
- **Custom Voice:** Clone a voice from Jarvis audio samples

### 5. Voice Cloning (For Custom Jarvis Voice)

If you want to clone a specific Jarvis voice:

1. **Prepare Audio Samples:**
   - Collect 1-5 minutes of clear Jarvis voice audio
   - Clean audio, no background noise
   - Single speaker only
   - Format: MP3, WAV, or M4A

2. **Clone Voice via API:**
   ```
   POST https://api.elevenlabs.io/v1/voices/add
   Headers:
     xi-api-key: YOUR_API_KEY
   Body (multipart/form-data):
     name: "Jarvis"
     files: [audio_file_1.mp3, audio_file_2.mp3, ...]
     description: "Jarvis voice clone"
   ```

3. **Get Voice ID:**
   ```
   GET https://api.elevenlabs.io/v1/voices
   Headers:
     xi-api-key: YOUR_API_KEY
   ```
   Find your cloned voice in the response and copy its `voice_id`

4. **Use Cloned Voice:**
   - Use the voice_id in your TTS API calls

### 6. Complete Workflow Example

```
Webhook (receives audio)
  ↓
Whisper (STT) - transcribe to text
  ↓
AI Agent/Ollama - generate response
  ↓
HTTP Request (ElevenLabs TTS)
  - URL: https://api.elevenlabs.io/v1/text-to-speech/{jarvis_voice_id}
  - Method: POST
  - Auth: xi-api-key header
  - Body: JSON with text and voice settings
  ↓
Response contains audio file (binary)
  ↓
Return audio to user
```

### 7. n8n HTTP Request Node Configuration

**Node Settings:**
- **Method:** `POST`
- **URL:** `https://api.elevenlabs.io/v1/text-to-speech/YOUR_VOICE_ID`
- **Authentication:** Header Auth
  - **Name:** `xi-api-key`
  - **Value:** `YOUR_API_KEY` (store in n8n credentials)
- **Body Content Type:** `JSON`
- **Specify Body:**
  ```json
  {
    "text": "={{ $json.text }}",
    "model_id": "eleven_multilingual_v2",
    "voice_settings": {
      "stability": 0.5,
      "similarity_boost": 0.75,
      "style": 0.0,
      "use_speaker_boost": true
    }
  }
  ```

**Response Handling:**
- The API returns audio as binary data
- n8n will automatically handle it
- You can return it directly or save it

### 8. Voice Settings Explained

- **stability** (0.0-1.0): How stable/consistent the voice is
  - Lower = more variation, more expressive
  - Higher = more consistent, less variation
  - Recommended: 0.5 for Jarvis

- **similarity_boost** (0.0-1.0): How similar to original voice
  - Higher = closer to original
  - Recommended: 0.75 for Jarvis

- **style** (0.0-1.0): Style exaggeration
  - Higher = more dramatic
  - Recommended: 0.0 for professional Jarvis

- **use_speaker_boost**: Enhances clarity
  - Recommended: `true`

## Alternative: Free Jarvis Voice Services

If you want to avoid API costs, you can use free services via HTTP Request:

### Fish Audio J.A.R.V.I.S:
- Check if they have an API endpoint
- Use HTTP Request node to call it

### AnyVoiceLab:
- May have API access
- Check their documentation

## Troubleshooting

**Error: 401 Unauthorized**
- Check your API key is correct
- Ensure it's in the `xi-api-key` header

**Error: 422 Unprocessable Entity**
- Check voice_id is valid
- Verify text is not empty
- Check voice_settings values are in valid ranges

**Audio Quality Issues**
- Adjust `stability` and `similarity_boost`
- Try different model_id
- Use higher quality voice cloning samples

## Next Steps

1. Get ElevenLabs API key
2. Find or clone a Jarvis voice
3. Set up HTTP Request node in n8n
4. Test with a simple text input
5. Integrate into your voice assistant workflow

