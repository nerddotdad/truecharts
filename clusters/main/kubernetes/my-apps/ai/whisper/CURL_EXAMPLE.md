# Whisper API cURL Examples

## Basic Transcription

```bash
curl -X POST "http://whisper-app-template.ai.svc.cluster.local:9000/asr" \
  -F "audio_file=@/path/to/your/audio.wav" \
  -F "task=transcribe" \
  -F "language=en" \
  -F "response_format=json"
```

## For n8n "Convert curl to Request"

Use this version (n8n will handle the file upload from binary data):

```bash
curl -X POST "http://whisper-app-template.ai.svc.cluster.local:9000/asr" \
  -F "audio_file=@audio.wav" \
  -F "task=transcribe" \
  -F "language=en" \
  -F "response_format=json"
```

## With Auto-Detect Language

```bash
curl -X POST "http://whisper-app-template.ai.svc.cluster.local:9000/asr" \
  -F "audio_file=@audio.wav" \
  -F "task=transcribe" \
  -F "response_format=json"
```

## Translation (instead of transcription)

```bash
curl -X POST "http://whisper-app-template.ai.svc.cluster.local:9000/asr" \
  -F "audio_file=@audio.wav" \
  -F "task=translate" \
  -F "response_format=json"
```

## Text Response Format

```bash
curl -X POST "http://whisper-app-template.ai.svc.cluster.local:9000/asr" \
  -F "audio_file=@audio.wav" \
  -F "task=transcribe" \
  -F "language=en" \
  -F "response_format=text"
```

## Verbose JSON (with segments and timestamps)

```bash
curl -X POST "http://whisper-app-template.ai.svc.cluster.local:9000/asr" \
  -F "audio_file=@audio.wav" \
  -F "task=transcribe" \
  -F "language=en" \
  -F "response_format=verbose_json"
```

## Notes for n8n

When using "Convert curl to Request" in n8n:
1. Paste the curl command
2. n8n will automatically detect it's a POST request with form-data
3. Replace `@audio.wav` with `{{ $binary.data }}` in the `audio_file` parameter
4. Make sure the parameter name is `audio_file` (not `file`)
5. The other parameters will be automatically added

## Response Example

```json
{
  "text": "Hello, this is a test transcription.",
  "language": "en",
  "segments": [
    {
      "id": 0,
      "seek": 0,
      "start": 0.0,
      "end": 2.5,
      "text": "Hello, this is a test transcription.",
      "tokens": [1234, 5678, ...],
      "temperature": 0.0,
      "avg_logprob": -0.5,
      "compression_ratio": 1.2,
      "no_speech_prob": 0.1
    }
  ]
}
```



