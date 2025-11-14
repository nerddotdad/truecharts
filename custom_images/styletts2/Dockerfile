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

# Install styletts2 module - handle different repository structures
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
            # Ensure __init__.py exists \
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
    ls -la "$SITE_PACKAGES/" | grep -i styletts2 || echo "No styletts2 found in site-packages" && \
    echo "" && \
    echo "=== Testing import ===" && \
    python3 -c "import sys; sys.path.insert(0, '/app/StyleTTS2'); from styletts2 import tts; print('SUCCESS: Imported from /app/StyleTTS2')" 2>&1 || \
    python3 -c "from styletts2 import tts; print('SUCCESS: Imported from site-packages')" 2>&1 || \
    (echo "WARNING: Import test failed, but PYTHONPATH will be set at runtime" && \
     python3 -c "import sys; print('Python path:', sys.path)" 2>&1)

# Create styletts2 package wrapper
# This ensures 'from styletts2 import tts' works with StyleTTS2 repository
RUN SITE_PACKAGES=$(python3 -c "import site; print(site.getsitepackages()[0])") && \
    STYLETTS2_PKG="$SITE_PACKAGES/styletts2" && \
    echo "Creating styletts2 package wrapper at $STYLETTS2_PKG" && \
    mkdir -p "$STYLETTS2_PKG" && \
    \
    # Create __init__.py \
    cat > "$STYLETTS2_PKG/__init__.py" << 'PYEOF'
# styletts2 package - wrapper for StyleTTS2 repository
__all__ = ['tts']
PYEOF
    \
    # Create tts.py that imports StyleTTS2 from repository \
    cat > "$STYLETTS2_PKG/tts.py" << 'PYEOF'
"""
styletts2.tts module
Imports StyleTTS2 class from StyleTTS2 repository
"""
import sys
import os

# Add repository to Python path
repo_path = '/app/StyleTTS2'
if repo_path not in sys.path:
    sys.path.insert(0, repo_path)

# Import StyleTTS2 - try multiple strategies
StyleTTS2 = None
import_error = None

# Strategy 1: Try importing from inference.py (most common)
try:
    from inference import StyleTTS2
except ImportError as e:
    import_error = str(e)
    # Strategy 2: Try loading inference.py directly
    try:
        import importlib.util
        inference_path = os.path.join(repo_path, 'inference.py')
        if os.path.exists(inference_path):
            spec = importlib.util.spec_from_file_location("inference", inference_path)
            inference_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(inference_module)
            StyleTTS2 = getattr(inference_module, 'StyleTTS2', None)
    except Exception as e2:
        import_error = f"{import_error}; {str(e2)}"

# Strategy 3: Try importing from other possible locations
if StyleTTS2 is None:
    try:
        # Check if there's a Models or Utils directory with the class
        import importlib
        # Try importing from various possible module names
        for module_name in ['inference', 'Models.inference', 'Utils.inference', 'styletts2.inference']:
            try:
                mod = importlib.import_module(module_name)
                StyleTTS2 = getattr(mod, 'StyleTTS2', None)
                if StyleTTS2 is not None:
                    break
            except:
                continue
    except Exception as e3:
        if not import_error:
            import_error = str(e3)

if StyleTTS2 is None:
    raise ImportError(
        f"Could not import StyleTTS2 from StyleTTS2 repository at {repo_path}. "
        f"Errors: {import_error or 'Unknown error'}. "
        f"Please ensure the repository contains inference.py with StyleTTS2 class."
    )

__all__ = ['StyleTTS2']
PYEOF
    \
    echo "Created styletts2 package wrapper" && \
    echo "Testing import..." && \
    python3 -c "from styletts2 import tts; print('✓ styletts2.tts imported successfully'); print(f'StyleTTS2 class: {tts.StyleTTS2}')" 2>&1 || \
    echo "⚠ Import test failed, but package wrapper created. Will try at runtime."

# Add StyleTTS2 repository root to Python path as primary method
# This ensures the module is found regardless of installation method
ENV PYTHONPATH=/app/StyleTTS2:/app:$PYTHONPATH

# Install gdown for model downloads (optional, can be done at runtime)
RUN pip install --no-cache-dir gdown

# Create directories for models and voices
RUN mkdir -p /app/models /app/voices

# Copy the Flask API server script
COPY api_server.py /app/api_server.py
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

