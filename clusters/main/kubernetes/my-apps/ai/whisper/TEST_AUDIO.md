# Getting Test Audio Files for Whisper

## Option 1: Use Your Own Audio File

If you have any audio file on your system:
```bash
curl -X POST "https://n8n.hoth.systems/webhook-test/2e50ef0d-9969-4db9-a5ea-d1c068490e1b" \
  -F "audio=@/path/to/your/file.wav"
```

## Option 2: Create a Test Audio with ffmpeg

If you have ffmpeg installed:
```bash
# Create a 5-second silent audio (for testing)
ffmpeg -f lavfi -i "sine=frequency=440:duration=5" -ar 16000 -ac 1 test.wav

# Or create with actual speech (if you have text-to-speech)
# Or record yourself saying something
```

## Option 3: Use Online Audio Samples

Try these alternative sources:

```bash
# Archive.org sample
wget https://archive.org/download/testmp3testfile/mpthreetest.mp3 -O test.mp3

# Or convert any YouTube video to audio (if you have yt-dlp)
yt-dlp -x --audio-format wav "https://www.youtube.com/watch?v=YOUR_VIDEO_ID" -o test.wav
```

## Option 4: Record Your Own (Quick Test)

If you're on Linux with PulseAudio:
```bash
# Record 5 seconds of audio
parecord --file-format=wav --channels=1 --rate=16000 test.wav
# (Press Ctrl+C after speaking)

# Or use arecord (ALSA)
arecord -f cd -t wav -d 5 test.wav
```

## Option 5: Use n8n's Built-in Test

In n8n:
1. Go to your workflow
2. Click the Webhook node
3. Click "Listen for Test Event"
4. Use the file upload button in the test interface
5. Upload any audio file from your computer

## Option 6: Simple Test - Use Text First

For initial testing, you could also:
1. Send text to the webhook first to test the workflow
2. Then add audio file support once the workflow is working

## Quick Test with Any Audio File

If you have ANY audio file (music, podcast, etc.), just use it:
```bash
curl -X POST "https://n8n.hoth.systems/webhook-test/2e50ef0d-9969-4db9-a5ea-d1c068490e1b" \
  -F "audio=@your-existing-file.mp3"
```

## Recommended: Use Your Phone

The easiest way:
1. Record a short audio message on your phone
2. Transfer it to your computer
3. Send it to the webhook

## Minimal Test File

If you just want to test that the workflow works, you can create a minimal WAV file:

```bash
# Create a 1-second test tone (requires sox or ffmpeg)
sox -n -r 16000 -c 1 test.wav synth 1 sine 440

# Or with ffmpeg:
ffmpeg -f lavfi -i "sine=frequency=440:duration=1" -ar 16000 test.wav
```



