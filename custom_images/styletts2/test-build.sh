#!/bin/bash
# Test script to build and test the styletts2 Docker image locally

set -e

IMAGE_NAME="styletts2-test"
IMAGE_TAG="local-test"

# Check if --no-cache flag is passed
if [ "$1" == "--no-cache" ] || [ "$1" == "-n" ]; then
    echo "=== Building Docker image (no cache) ==="
    docker build --no-cache -t ${IMAGE_NAME}:${IMAGE_TAG} .
else
    echo "=== Building Docker image (with cache) ==="
    echo "Tip: Use './test-build.sh --no-cache' to rebuild without cache"
    docker build -t ${IMAGE_NAME}:${IMAGE_TAG} .
fi

echo ""
echo "=== Testing image import ==="
echo "Running import test in container..."

# Test that the import works
docker run --rm ${IMAGE_NAME}:${IMAGE_TAG} python3 -c "
import sys
print('Python path:', sys.path)
print('')
try:
    from styletts2 import tts
    print('✓ SUCCESS: styletts2.tts imported successfully')
    print(f'StyleTTS2 class: {tts.StyleTTS2}')
    print(f'Module location: {tts.__file__ if hasattr(tts, \"__file__\") else \"built-in\"}')
except Exception as e:
    print(f'✗ FAILED: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)
"

echo ""
echo "=== Testing API server import ==="
echo "Testing that api_server.py can be imported..."

# Test that the API server can at least be imported (it will fail to load model without GPU/models, but should get past import)
docker run --rm ${IMAGE_NAME}:${IMAGE_TAG} python3 -c "
import sys
sys.path.insert(0, '/app')
try:
    # Just test that we can import the api_server module
    import api_server
    print('✓ SUCCESS: api_server.py imported successfully')
    print('API server module is ready')
except Exception as e:
    print(f'✗ FAILED to import api_server: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)
"

echo ""
echo "=== Build test complete ==="
echo "If all tests passed, the image is ready to push!"
echo ""
echo "To tag and push to GHCR:"
echo "  docker tag ${IMAGE_NAME}:${IMAGE_TAG} ghcr.io/nerddotdad/styletts2:1.0.2"
echo "  docker push ghcr.io/nerddotdad/styletts2:1.0.2"

