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

# Find and install styletts2 module to site-packages so Python can import it
RUN python3 -c "import site; print(site.getsitepackages())" && \
    SITE_PACKAGES=$(python3 -c "import site; print(site.getsitepackages()[0])") && \
    echo "Site packages location: $SITE_PACKAGES" && \
    STYLETTS2_MODULE=$(find /app/StyleTTS2 -type d -name "styletts2" 2>/dev/null | head -1) && \
    if [ -n "$STYLETTS2_MODULE" ]; then \
        echo "Found styletts2 module at: $STYLETTS2_MODULE" && \
        echo "Copying to site-packages: $SITE_PACKAGES" && \
        cp -r "$STYLETTS2_MODULE" "$SITE_PACKAGES/" && \
        echo "Successfully installed styletts2 to site-packages"; \
    else \
        echo "styletts2 directory not found, checking repository structure..." && \
        echo "Repository contents:" && \
        ls -la /app/StyleTTS2/ | head -20 && \
        echo "Searching for styletts2..." && \
        find /app/StyleTTS2 -name "*styletts2*" -o -name "*tts*" | head -10 && \
        echo "If styletts2 is at repository root, we'll use PYTHONPATH instead"; \
    fi

# Add StyleTTS2 repository root to Python path as fallback
# This ensures Python can find the module even if it's structured differently
ENV PYTHONPATH=/app/StyleTTS2:/app:$PYTHONPATH

# Install gdown for model downloads (optional, can be done at runtime)
RUN pip install --no-cache-dir gdown

# Create directories for models and voices
RUN mkdir -p /app/models /app/voices

# Copy the Flask API server script
COPY api_server.py /app/api_server.py
RUN chmod +x /app/api_server.py

# Expose port
EXPOSE 5003

# Run the API server
CMD ["python3", "/app/api_server.py"]

