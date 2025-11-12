# Recording Audio for Whisper Testing

## Method 1: Record with Volume Boost

### Using arecord with specific device and gain:
```bash
# List available devices first
arecord -l

# Record with boost (replace hw:2,0 with your device)
arecord -D hw:2,0 -f cd -t wav -d 5 -v /tmp/my-voice.wav

# Or try with PulseAudio (usually better)
parecord --file-format=wav --channels=1 --rate=16000 --volume=200 /tmp/my-voice.wav
# (Press Ctrl+C after speaking)
```

## Method 2: Record then Boost with ffmpeg

```bash
# Record normally
arecord -f cd -t wav -d 5 /tmp/quiet.wav

# Boost volume by 20dB
ffmpeg -i /tmp/quiet.wav -af "volume=20dB" /tmp/loud.wav

# Or normalize to maximum
ffmpeg -i /tmp/quiet.wav -af "volume=0dB:enable='between(t,0,5)'" -ar 16000 /tmp/normalized.wav
```

## Method 3: Increase System Microphone Volume

```bash
# Check current levels
amixer sget Capture

# Increase capture volume (if not already max)
amixer sset Capture 100%+

# Or set to specific percentage
amixer sset Capture 90%
```

## Method 4: Use PulseAudio Volume Control

```bash
# Check PulseAudio sources
pactl list sources short

# Increase source volume (replace SOURCE_NAME)
pactl set-source-volume SOURCE_NAME 150%

# Record with PulseAudio
parecord --file-format=wav --channels=1 --rate=16000 /tmp/my-voice.wav
```

## Method 5: Record with ffmpeg (Better Control)

```bash
# Record with higher gain
ffmpeg -f pulse -i default -ar 16000 -ac 1 -af "volume=10dB" /tmp/my-voice.wav
# (Press 'q' to stop)

# Or with ALSA directly
ffmpeg -f alsa -i hw:2,0 -ar 16000 -ac 1 -af "volume=10dB" /tmp/my-voice.wav
```

## Quick Fix: Boost Existing Recording

If you already recorded something quiet:

```bash
# Boost by 15dB (adjust as needed)
ffmpeg -i /tmp/quiet-recording.wav -af "volume=15dB" -ar 16000 /tmp/boosted.wav

# Then test:
curl -X POST "https://n8n.hoth.systems/webhook-test/2e50ef0d-9969-4db9-a5ea-d1c068490e1b" \
  -F "audio=@/tmp/boosted.wav"
```

## Recommended: Use Your Phone

Easiest solution:
1. Record on your phone (usually has good mic)
2. Transfer to computer
3. Send to webhook

## Test the Boosted Audio

After boosting, test with:
```bash
curl -X POST "https://n8n.hoth.systems/webhook-test/2e50ef0d-9969-4db9-a5ea-d1c068490e1b" \
  -F "audio=@/tmp/boosted.wav"
```



