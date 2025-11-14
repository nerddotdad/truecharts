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

# Add StyleTTS2 to Python path
ENV PYTHONPATH=/app/StyleTTS2:$PYTHONPATH

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

