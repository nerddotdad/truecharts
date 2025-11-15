# StyleTTS2 API Server Docker Image
# Base image with PyTorch and CUDA 11.8
FROM pytorch/pytorch:2.3.1-cuda11.8-cudnn8-runtime@sha256:ff97981d417f43767865c977591c29e1ce35b076398d5c5122bdca4d2a454e1b

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git wget curl unzip \
    espeak-ng libespeak-ng-dev libsndfile1 \
    build-essential gcc g++ \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir \
    SoundFile munch pydub pyyaml \
    librosa nltk matplotlib accelerate transformers \
    phonemizer einops einops-exts tqdm typing-extensions \
    flask flask-cors \
    git+https://github.com/resemble-ai/monotonic_align.git

# Clone StyleTTS2 repository (not installable via pip, needs to be in Python path)
RUN git clone https://github.com/yl4579/StyleTTS2.git /app/StyleTTS2 && \
    cd /app/StyleTTS2 && \
    git checkout 5cedc71c333f8d8b8551ca59378bdcc7af4c9529

# Install StyleTTS2 dependencies if there's a requirements file
RUN if [ -f /app/StyleTTS2/requirements.txt ]; then \
        pip install --no-cache-dir -r /app/StyleTTS2/requirements.txt; \
    fi

# Debug: Show repository structure to understand layout
RUN echo "=== StyleTTS2 Repository Structure ===" && \
    ls -la /app/StyleTTS2/ && \
    echo "" && \
    echo "=== Top-level directories ===" && \
    find /app/StyleTTS2 -maxdepth 1 -type d && \
    echo "" && \
    echo "=== Looking for styletts2 module ===" && \
    find /app/StyleTTS2 -type d -name "styletts2" 2>/dev/null && \
    echo "" && \
    echo "=== Looking for tts.py or similar ===" && \
    find /app/StyleTTS2 -name "*tts*.py" -type f | head -10

# Copy styletts2 wrapper package early (before installation attempts)
COPY styletts2_wrapper/ /app/styletts2_wrapper/

# Install styletts2 module - handle different repository structures
# Note: We'll overwrite with our wrapper afterwards
RUN SITE_PACKAGES=$(python3 -c "import site; print(site.getsitepackages()[0])") && \
    echo "Site packages: $SITE_PACKAGES" && \
    \
    # Method 1: Look for styletts2 directory in repository \
    STYLETTS2_DIR=$(find /app/StyleTTS2 -type d -name "styletts2" 2>/dev/null | head -1) && \
    \
    if [ -n "$STYLETTS2_DIR" ]; then \
        echo "Method 1: Found styletts2 directory at: $STYLETTS2_DIR" && \
        STYLETTS2_PARENT=$(dirname "$STYLETTS2_DIR") && \
        echo "Parent directory: $STYLETTS2_PARENT" && \
        # Copy the entire parent directory structure to preserve imports \
        if [ "$STYLETTS2_PARENT" != "/app/StyleTTS2" ]; then \
            # If styletts2 is in a subdirectory, copy parent to site-packages \
            cp -r "$STYLETTS2_PARENT"/* "$SITE_PACKAGES/" 2>/dev/null || true; \
        else \
            # If styletts2 is at root, just copy it \
            cp -r "$STYLETTS2_DIR" "$SITE_PACKAGES/"; \
        fi && \
        echo "Copied styletts2 structure to site-packages"; \
    else \
        echo "Method 1 failed: styletts2 directory not found" && \
        \
        # Method 2: Check if repository root contains the package files \
        if [ -f "/app/StyleTTS2/inference.py" ] || [ -d "/app/StyleTTS2/Utils" ] || [ -d "/app/StyleTTS2/Models" ]; then \
            echo "Method 2: Repository root appears to contain package files" && \
            # Create styletts2 package and copy everything \
            mkdir -p "$SITE_PACKAGES/styletts2" && \
            cp -r /app/StyleTTS2/* "$SITE_PACKAGES/styletts2/" 2>/dev/null || true && \
            # Ensure __init__.py exists (will be overwritten by our wrapper) \
            [ ! -f "$SITE_PACKAGES/styletts2/__init__.py" ] && touch "$SITE_PACKAGES/styletts2/__init__.py" || true && \
            echo "Created styletts2 package from repository root"; \
        else \
            echo "Method 2 failed: Repository root doesn't contain expected files" && \
            \
            # Method 3: Look for any Python package structure \
            echo "Method 3: Searching for Python package structure..." && \
            find /app/StyleTTS2 -name "__init__.py" -type f | head -5 && \
            # Try to find the actual package location \
            PACKAGE_ROOT=$(find /app/StyleTTS2 -name "__init__.py" -type f | head -1 | xargs dirname) && \
            if [ -n "$PACKAGE_ROOT" ] && [ "$PACKAGE_ROOT" != "/app/StyleTTS2" ]; then \
                echo "Found package root at: $PACKAGE_ROOT" && \
                PACKAGE_NAME=$(basename "$PACKAGE_ROOT") && \
                if [ "$PACKAGE_NAME" = "styletts2" ]; then \
                    cp -r "$PACKAGE_ROOT" "$SITE_PACKAGES/"; \
                else \
                    # Package has different name, create styletts2 and copy \
                    mkdir -p "$SITE_PACKAGES/styletts2" && \
                    cp -r "$PACKAGE_ROOT"/* "$SITE_PACKAGES/styletts2/" 2>/dev/null || true; \
                fi; \
            fi; \
        fi; \
    fi && \
    \
    # Final verification \
    echo "" && \
    echo "=== Final structure in site-packages ===" && \
    ls -la "$SITE_PACKAGES/" | grep -i styletts2 || echo "No styletts2 found in site-packages"

# Install our styletts2 package wrapper (overwrites any files from above)
# This ensures 'from styletts2 import tts' works with StyleTTS2 repository
RUN SITE_PACKAGES=$(python3 -c "import site; print(site.getsitepackages()[0])") && \
    STYLETTS2_PKG="$SITE_PACKAGES/styletts2" && \
    echo "=== Installing styletts2 package wrapper ===" && \
    echo "Package directory: $STYLETTS2_PKG" && \
    mkdir -p "$STYLETTS2_PKG" && \
    cp -r /app/styletts2_wrapper/* "$STYLETTS2_PKG/" && \
    echo "Copied wrapper files to $STYLETTS2_PKG" && \
    ls -lh "$STYLETTS2_PKG/__init__.py" "$STYLETTS2_PKG/tts.py" && \
    \
    # Test import \
    echo "=== Testing import ===" && \
    python3 -c "from styletts2 import tts; print('✓ Import successful'); print(f'tts module: {tts}'); print(f'Has StyleTTS2: {hasattr(tts, \"StyleTTS2\")}')" || \
    (echo "⚠ Import test failed" && python3 -c "import sys; import os; pkg = os.path.join(sys.path[-1], 'styletts2'); print(f'Package: {pkg}'); print(f'Exists: {os.path.exists(pkg)}'); print(f'Contents: {os.listdir(pkg)[:10] if os.path.exists(pkg) else []}')")

# Add StyleTTS2 repository root to Python path as primary method
# This ensures the module is found regardless of installation method
ENV PYTHONPATH=/app/StyleTTS2:/app:$PYTHONPATH

# Install gdown for model downloads (optional, can be done at runtime)
RUN pip install --no-cache-dir gdown

# Create directories for models and voices
RUN mkdir -p /app/models /app/voices

# Copy the Flask API server script
COPY api_server.py /app/api_server.py
COPY templates/ /app/templates/
RUN chmod +x /app/api_server.py

# Final import test before finishing build (non-fatal for debugging)
RUN echo "=== Final Import Test ===" && \
    python3 << 'EOF' || echo "WARNING: Import test failed, but continuing build. Check runtime logs."
import sys
sys.path.insert(0, '/app/StyleTTS2')
sys.path.insert(0, '/app')

print("Python path:", sys.path)
print("\nSearching for styletts2 module...")
import os
found_paths = []
for path in sys.path:
    styletts2_path = os.path.join(path, 'styletts2')
    if os.path.exists(styletts2_path):
        found_paths.append(styletts2_path)
        print(f"  Found styletts2 at: {styletts2_path}")
        if os.path.isdir(styletts2_path):
            try:
                contents = os.listdir(styletts2_path)
                print(f"    Contents ({len(contents)} items): {contents[:10]}")
            except:
                pass

print(f"\nFound {len(found_paths)} potential styletts2 locations")

try:
    from styletts2 import tts
    print("✓ SUCCESS: styletts2.tts imported successfully")
    print(f"  Module location: {tts.__file__ if hasattr(tts, '__file__') else 'built-in'}")
except ImportError as e:
    print(f"✗ FAILED: Could not import styletts2.tts")
    print(f"  Error: {e}")
    print(f"  Error type: {type(e).__name__}")
    if hasattr(e, 'msg'):
        print(f"  Error message: {e.msg}")
    if hasattr(e, 'name'):
        print(f"  Missing module: {e.name}")
    print("\nRepository structure check:")
    if os.path.exists('/app/StyleTTS2'):
        print("  /app/StyleTTS2 exists")
        try:
            repo_contents = os.listdir('/app/StyleTTS2')
            print(f"  Repository contents: {repo_contents[:20]}")
        except:
            pass
    # Don't exit with error - let build continue so we can debug at runtime
    print("\nBuild will continue. PYTHONPATH is set, import may work at runtime.")
EOF

# Expose port
EXPOSE 5003

# Run the API server
CMD ["python3", "/app/api_server.py"]

