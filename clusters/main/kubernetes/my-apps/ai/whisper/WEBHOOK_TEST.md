# Testing Whisper Webhook in n8n

## Your Webhook Endpoint
```
https://n8n.hoth.systems/webhook-test/2e50ef0d-9969-4db9-a5ea-d1c068490e1b
```

## Method 1: cURL Command

### Basic Test (with audio file)
```bash
curl -X POST "https://n8n.hoth.systems/webhook-test/2e50ef0d-9969-4db9-a5ea-d1c068490e1b" \
  -F "audio=@/path/to/your/audio.wav" \
  -H "Content-Type: multipart/form-data"
```

### Alternative field names (depending on your webhook config)
```bash
# Try these if "audio" doesn't work:
curl -X POST "https://n8n.hoth.systems/webhook-test/2e50ef0d-9969-4db9-a5ea-d1c068490e1b" \
  -F "file=@/path/to/your/audio.wav"

curl -X POST "https://n8n.hoth.systems/webhook-test/2e50ef0d-9969-4db9-a5ea-d1c068490e1b" \
  -F "data=@/path/to/your/audio.wav"
```

## Method 2: Using a Test Audio File

### Download a sample audio file first:
```bash
# Download a test audio file (example)
wget https://www2.cs.uic.edu/~i101/SoundFiles/StarWars60.wav -O test-audio.wav

# Then send it:
curl -X POST "https://n8n.hoth.systems/webhook-test/2e50ef0d-9969-4db9-a5ea-d1c068490e1b" \
  -F "audio=@test-audio.wav"
```

## Method 3: Create a Simple Test Audio

### Using ffmpeg (if installed):
```bash
# Create a 5-second test audio saying "Hello, this is a test"
ffmpeg -f lavfi -i "sine=frequency=440:duration=5" -ar 16000 test.wav

# Send it:
curl -X POST "https://n8n.hoth.systems/webhook-test/2e50ef0d-9969-4db9-a5ea-d1c068490e1b" \
  -F "audio=@test.wav"
```

## Method 4: Using n8n's Webhook Test Interface

1. Go to your n8n workflow
2. Click on the Webhook node
3. Click "Test URL" or "Listen for Test Event"
4. Use the file upload option in the test interface

## Method 5: Browser/Postman

### Using Postman:
1. Method: POST
2. URL: `https://n8n.hoth.systems/webhook-test/2e50ef0d-9969-4db9-a5ea-d1c068490e1b`
3. Body: form-data
4. Key: `audio` (or `file`, `data` - check your webhook node)
5. Type: File
6. Select your audio file

## Supported Audio Formats

- WAV (recommended)
- MP3
- M4A
- FLAC
- OGG
- WebM

## Quick Test Script

Save this as `test-whisper.sh`:

```bash
#!/bin/bash
WEBHOOK_URL="https://n8n.hoth.systems/webhook-test/2e50ef0d-9969-4db9-a5ea-d1c068490e1b"
AUDIO_FILE="$1"

if [ -z "$AUDIO_FILE" ]; then
  echo "Usage: $0 <audio-file.wav>"
  exit 1
fi

curl -X POST "$WEBHOOK_URL" \
  -F "audio=@$AUDIO_FILE" \
  -v

echo ""
```

Make it executable and use:
```bash
chmod +x test-whisper.sh
./test-whisper.sh your-audio.wav
```

## Troubleshooting

### Check Webhook Node Configuration
In your n8n workflow, check the Webhook node:
- **HTTP Method**: Should be POST
- **Path**: `/webhook-test/2e50ef0d-9969-4db9-a5ea-d1c068490e1b`
- **Response Mode**: Usually "Last Node" or "When Last Node Finishes"
- **Binary Data**: Should be enabled if receiving files

### Common Issues

1. **404 Not Found**: Check the webhook path is correct
2. **400 Bad Request**: Check the field name (might be `file`, `data`, or `audio`)
3. **File too large**: Check n8n's file size limits
4. **Wrong format**: Ensure audio file is in supported format

### Check n8n Logs
In your n8n workflow execution, check:
- Did the webhook receive the file?
- Is the binary data being passed to Whisper?
- What's the response from Whisper API?

## Expected Workflow Flow

```
Webhook receives audio file
  ↓
HTTP Request → Whisper API (transcribe)
  ↓
Function Node (extract {{ $json.text }})
  ↓
Process transcription (AI Agent, SearXNG, etc.)
  ↓
Return response
```

## Response Format

Your webhook should return the transcription or processed result. Check your workflow's final node to see what gets returned.



