#!/bin/bash
# StyleTTS2 API Test Script
# Usage: ./test-api.sh [service-url]
# Example: ./test-api.sh http://styletts2.yourdomain.com
#          ./test-api.sh http://localhost:5003
#          ./test-api.sh http://styletts2.ai.svc.cluster.local:5003

SERVICE_URL="${1:-http://styletts2.${DOMAIN_0:-localhost:5003}}"

echo "Testing StyleTTS2 API at: $SERVICE_URL"
echo "========================================"
echo ""

# Test 1: Check server status
echo "1. Testing server status..."
curl -s "$SERVICE_URL/" | jq -r '.' 2>/dev/null || curl -s "$SERVICE_URL/"
echo ""
echo ""

# Test 2: Check readiness
echo "2. Testing readiness endpoint..."
curl -s "$SERVICE_URL/ready"
echo ""
echo ""

# Test 3: List available voices
echo "3. Listing available voices..."
curl -s "$SERVICE_URL/api/voices" | jq '.' 2>/dev/null || curl -s "$SERVICE_URL/api/voices"
echo ""
echo ""

# Test 4: Basic TTS (no voice cloning)
echo "4. Testing basic TTS (default voice)..."
echo "   This will generate audio and save it to test-output.wav"
curl -X POST "$SERVICE_URL/api/tts" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Hello, this is a test of the StyleTTS2 text to speech system.",
    "alpha": 0.3,
    "beta": 0.7,
    "diffusion_steps": 10
  }' \
  --output test-output.wav \
  --write-out "\nHTTP Status: %{http_code}\n"
echo ""

# Test 5: TTS with voice cloning (if you have a voice uploaded)
echo "5. Testing TTS with voice cloning..."
echo "   (This will fail if no voices are uploaded)"
curl -X POST "$SERVICE_URL/api/tts" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Hello, this is a test with voice cloning.",
    "target_voice_path": "default/voice.wav",
    "alpha": 0.3,
    "beta": 0.7,
    "diffusion_steps": 10
  }' \
  --output test-voice-clone.wav \
  --write-out "\nHTTP Status: %{http_code}\n" \
  2>&1 | head -20
echo ""

echo "========================================"
echo "Test complete!"
echo ""
echo "If test-output.wav was created, you can play it with:"
echo "  aplay test-output.wav  # Linux"
echo "  afplay test-output.wav  # macOS"
echo "  # Or use any audio player"
echo ""
echo "To upload a voice for cloning:"
echo "  curl -X POST $SERVICE_URL/api/upload-voice \\"
echo "    -F 'file=@your-voice.wav' \\"
echo "    -F 'name=myvoice'"
echo ""

