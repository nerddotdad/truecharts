#!/usr/bin/env python3
"""
Pre-download Bark models manually
Run this script to download models before deploying the container
This avoids slow downloads during pod startup
"""

import os
import sys

# Set cache location to match container
cache_dir = os.environ.get("HF_HOME", os.path.expanduser("~/.cache/huggingface"))
os.environ["HF_HOME"] = cache_dir
os.environ["HF_HUB_CACHE"] = os.path.join(cache_dir, "hub")
os.environ["TRANSFORMERS_CACHE"] = os.path.join(cache_dir, "transformers")

print(f"Downloading Bark models to: {cache_dir}")
print("This may take 10-30 minutes depending on your connection...")
print("=" * 60)

try:
    from bark import preload_models
    print("Starting model download...")
    preload_models()
    print("=" * 60)
    print("✓ Models downloaded successfully!")
    print(f"Models cached at: {cache_dir}")
except Exception as e:
    print(f"Error downloading models: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

