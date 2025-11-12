# Whisper API Integration with n8n

## Quick Setup Guide

### Step 1: HTTP Request Node Configuration

1. **Add HTTP Request Node** to your n8n workflow
2. **Configure the node:**
   - **Method**: `POST`
   - **URL**: `http://whisper-app-template.ai.svc.cluster.local:9000/asr`
   - **Authentication**: None (internal cluster access)
   - **Body Content Type**: `Form-Data` or `Multipart-Form-Data`

3. **Add Parameters:**
   - `audio_file`: `{{ $binary.data }}` (the audio file from previous node) - **Note: field name is `audio_file`, not `file`**
   - `task`: `transcribe` (or `translate` if you want translation)
   - `language`: `en` (optional - auto-detects if not specified)
   - `response_format`: `json` (or `text`, `srt`, `vtt`, etc.)

### Step 2: Example Workflow Structure

```
Webhook (receives audio file)
  ↓
HTTP Request → Whisper API
  ↓
Function Node (extract transcription)
  ↓
Process text (AI Agent, SearXNG, etc.)
  ↓
Return response
```

### Step 3: Complete HTTP Request Node Configuration

**URL:**
```
http://whisper-app-template.ai.svc.cluster.local:9000/asr
```

**Body Parameters (Form-Data):**
```json
{
  "audio_file": "={{ $binary.data }}",
  "task": "transcribe",
  "language": "en",
  "response_format": "json"
}
```

**Response:**
The API returns JSON with the transcription:
```json
{
  "text": "Your transcribed text here",
  "language": "en",
  "segments": [...]
}
```

### Step 4: Extract Transcription Text

Add a **Function Node** after the HTTP Request to extract the text:

```javascript
// Extract transcription from Whisper response
return {
  json: {
    transcription: $input.item.json.text,
    language: $input.item.json.language,
    originalAudio: $input.first().binary
  }
};
```

Or simply use in next node:
```
{{ $json.text }}
```

## Example: Voice Command Workflow

### Complete Workflow

1. **Webhook Trigger**
   - Accepts POST with audio file
   - Save webhook URL

2. **HTTP Request → Whisper**
   - Method: POST
   - URL: `http://whisper-app-template.ai.svc.cluster.local:9000/asr`
   - Body: Form-Data
     - `file`: `{{ $binary.data }}`
     - `task`: `transcribe`
     - `language`: `en`
     - `response_format`: `json`

3. **Function Node** (Optional - extract text)
   ```javascript
   return {
     json: {
       command: $input.item.json.text.toLowerCase().trim()
     }
   };
   ```

4. **Switch Node** (Route based on command)
   - If command contains "search" → SearXNG
   - If command contains "weather" → Weather API
   - Default → AI Agent response

5. **HTTP Request → SearXNG** (if search)
   - Method: GET
   - URL: `https://searxng.${DOMAIN_0}/search`
   - Query: `q={{ $json.command }}&format=json`

6. **AI Agent Node** (for conversational responses)
   - Use Ollama or OpenAI
   - Input: `{{ $json.command }}`

7. **Return Response**
   - Format and return to webhook caller

## Testing the API

You can test the Whisper API directly from n8n using a manual trigger:

1. Create a **Manual Trigger** node
2. Add **HTTP Request** node
3. Configure as above
4. For testing, you can use a sample audio file URL or upload one

## API Endpoints

- **Transcribe**: `POST /asr` - Main transcription endpoint
- **Health/Docs**: `GET /docs` - API documentation (Swagger UI)
- **Root**: `GET /` - Service info

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `file` | File | Yes | Audio file to transcribe |
| `task` | String | No | `transcribe` (default) or `translate` |
| `language` | String | No | Language code (e.g., `en`, `es`, `fr`) - auto-detects if not specified |
| `response_format` | String | No | `json` (default), `text`, `srt`, `vtt`, `verbose_json` |

## Supported Audio Formats

- WAV
- MP3
- M4A
- FLAC
- OGG
- And more (see Whisper documentation)

## Tips

1. **Large Files**: For large audio files, consider chunking or using streaming
2. **Language Detection**: Leave `language` empty to auto-detect
3. **Response Format**: Use `verbose_json` for detailed segment information
4. **Error Handling**: Wrap in try-catch or use n8n's error handling
5. **Caching**: Transcription results can be cached if processing the same audio multiple times

## Troubleshooting

- **404 Error**: Check the URL is correct (internal cluster DNS)
- **Timeout**: Increase timeout for large files
- **Format Error**: Ensure audio file is in supported format
- **Connection Refused**: Verify Whisper pod is running and service is accessible



