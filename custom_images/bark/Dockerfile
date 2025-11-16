# Bark API Server Docker Image
# Base image with PyTorch and CUDA 11.8
FROM pytorch/pytorch:2.3.1-cuda11.8-cudnn8-runtime@sha256:ff97981d417f43767865c977591c29e1ce35b076398d5c5122bdca4d2a454e1b

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git wget curl \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir \
    flask flask-cors \
    scipy \
    numpy \
    git+https://github.com/suno-ai/bark.git

# Create directories for models and outputs
RUN mkdir -p /app/models /app/outputs

# Copy the Flask API server script
COPY api_server.py /app/api_server.py
COPY templates/ /app/templates/
RUN chmod +x /app/api_server.py

# Expose port
EXPOSE 5004

# Set environment variables for Bark
# Use smaller models if needed (<4GB VRAM)
ENV SUNO_USE_SMALL_MODELS=False
ENV SUNO_OFFLOAD_CPU=False

# Run the API server
CMD ["python3", "/app/api_server.py"]

