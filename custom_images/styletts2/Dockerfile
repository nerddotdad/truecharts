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

# Install StyleTTS2 package
RUN pip install --no-cache-dir git+https://github.com/yl4579/StyleTTS2.git

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

