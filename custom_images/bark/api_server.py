#!/usr/bin/env python3
"""
Bark Flask API Server
Provides REST API for text-to-audio synthesis with Bark
"""

from flask import Flask, request, send_file, jsonify, render_template
from bark import SAMPLE_RATE, generate_audio, preload_models
from scipy.io.wavfile import write as write_wav
import tempfile
import os
import threading
import json
from datetime import datetime

app = Flask(__name__)
bark_models_loaded = False
loading_error = None
model_loading = False
loading_status = {"status": "idle", "progress": 0, "message": ""}

# Available voice presets (Bark supports 100+ presets)
# Common presets: v2/en_speaker_1 through v2/en_speaker_9
# See: https://github.com/suno-ai/bark#voice-presets
DEFAULT_VOICE_PRESET = "v2/en_speaker_1"

# Server initialized
print("Bark Server initialized")
print("Models will be loaded on first request or via API")

def get_cache_size(cache_dir):
    """Get total size of Hugging Face cache directory"""
    total_size = 0
    try:
        if os.path.exists(cache_dir):
            for dirpath, dirnames, filenames in os.walk(cache_dir):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    try:
                        total_size += os.path.getsize(filepath)
                    except (OSError, FileNotFoundError):
                        pass
    except Exception:
        pass
    return total_size

def load_models():
    """Load Bark models"""
    global bark_models_loaded, loading_error, model_loading, loading_status
    import time
    import sys
    import threading
    
    if model_loading or bark_models_loaded:
        return
    
    model_loading = True
    loading_status = {"status": "loading", "progress": 0, "message": "Initializing Bark models..."}
    start_time = time.time()
    last_cache_size = 0
    last_update_time = start_time
    
    # Heartbeat function to monitor download progress
    def heartbeat_monitor():
        nonlocal last_cache_size, last_update_time
        cache_dir = os.environ.get("HF_HOME", os.path.expanduser("~/.cache/huggingface"))
        
        while model_loading and not bark_models_loaded:
            elapsed = time.time() - start_time
            current_cache_size = get_cache_size(cache_dir)
            cache_size_mb = current_cache_size / (1024 * 1024)
            
            # Update progress based on cache growth (rough estimate)
            if current_cache_size > last_cache_size:
                # Cache is growing - download is progressing
                # Rough estimate: models are ~2-3GB, so estimate progress
                estimated_total = 2.5 * 1024 * 1024 * 1024  # 2.5GB
                estimated_progress = min(90, 20 + int((current_cache_size / estimated_total) * 70))
                loading_status["progress"] = estimated_progress
                loading_status["message"] = f"Downloading models... ({cache_size_mb:.1f} MB downloaded, {elapsed:.0f}s elapsed)"
                last_cache_size = current_cache_size
                last_update_time = time.time()
                print(f"[{elapsed:.1f}s] Cache size: {cache_size_mb:.1f} MB (estimated {estimated_progress}% complete)")
                sys.stdout.flush()
            elif elapsed - last_update_time > 30:
                # No progress for 30 seconds - still show we're alive
                loading_status["message"] = f"Downloading models... ({cache_size_mb:.1f} MB, {elapsed:.0f}s elapsed) - Still working..."
                print(f"[{elapsed:.1f}s] Still downloading... (cache: {cache_size_mb:.1f} MB)")
                sys.stdout.flush()
                last_update_time = time.time()
            
            time.sleep(5)  # Check every 5 seconds
    
    try:
        print("=" * 60)
        print("Loading Bark models (this may take 5-15 minutes on first run)...")
        print("Models will be downloaded from Hugging Face (~2-3GB total)")
        print("=" * 60)
        sys.stdout.flush()
        
        loading_status["progress"] = 10
        loading_status["message"] = "Initializing Bark library..."
        print(f"[{time.time() - start_time:.1f}s] Initializing Bark library...")
        sys.stdout.flush()
        
        # Check Hugging Face cache location
        cache_dir = os.environ.get("HF_HOME", os.path.expanduser("~/.cache/huggingface"))
        print(f"[{time.time() - start_time:.1f}s] Hugging Face cache: {cache_dir}")
        initial_cache_size = get_cache_size(cache_dir)
        initial_cache_mb = initial_cache_size / (1024 * 1024)
        print(f"[{time.time() - start_time:.1f}s] Initial cache size: {initial_cache_mb:.1f} MB")
        sys.stdout.flush()
        
        # Check if models might already be cached (rough check - if cache is > 500MB, likely has models)
        if initial_cache_mb > 500:
            loading_status["progress"] = 30
            loading_status["message"] = f"Found existing cache ({initial_cache_mb:.1f} MB) - loading models from cache..."
            print(f"[{time.time() - start_time:.1f}s] Found existing cache ({initial_cache_mb:.1f} MB) - models may already be downloaded")
            print(f"[{time.time() - start_time:.1f}s] Loading models from cache (this should be faster)...")
            sys.stdout.flush()
        else:
            loading_status["progress"] = 20
            loading_status["message"] = "Downloading models from Hugging Face (this may take 10-30 minutes if slow)..."
            print(f"[{time.time() - start_time:.1f}s] Starting model download from Hugging Face...")
            print(f"[{time.time() - start_time:.1f}s] WARNING: If download is very slow, consider pre-downloading models manually")
            print(f"[{time.time() - start_time:.1f}s] See README.md for pre-download instructions")
            print(f"[{time.time() - start_time:.1f}s] Starting heartbeat monitor...")
            sys.stdout.flush()
            
            # Start heartbeat monitor in background
            heartbeat_thread = threading.Thread(target=heartbeat_monitor, daemon=True)
            heartbeat_thread.start()
        
        # Preload all models - this is a blocking call that downloads models if not cached
        # It can take 5-15 minutes (or much longer if network is slow)
        print(f"[{time.time() - start_time:.1f}s] Calling preload_models()...")
        sys.stdout.flush()
        
        preload_models()
        
        elapsed = time.time() - start_time
        final_cache_size = get_cache_size(cache_dir)
        print(f"[{elapsed:.1f}s] ✓ preload_models() completed!")
        print(f"[{elapsed:.1f}s] Final cache size: {final_cache_size / (1024*1024):.1f} MB")
        sys.stdout.flush()
        
        loading_status["progress"] = 80
        loading_status["message"] = "Models downloaded! Finalizing..."
        print(f"[{elapsed:.1f}s] Models downloaded successfully!")
        sys.stdout.flush()
        
        # Verify models are loaded by checking SAMPLE_RATE
        try:
            sample_rate = SAMPLE_RATE
            print(f"[{elapsed:.1f}s] Sample rate: {sample_rate} Hz")
            sys.stdout.flush()
        except Exception as e:
            print(f"[{elapsed:.1f}s] Warning: Could not verify SAMPLE_RATE: {e}")
            sys.stdout.flush()
        
        # Check GPU memory usage if CUDA is available
        try:
            import torch
            if torch.cuda.is_available():
                gpu_memory_allocated = torch.cuda.memory_allocated() / (1024**3)  # GB
                gpu_memory_reserved = torch.cuda.memory_reserved() / (1024**3)  # GB
                print(f"[{elapsed:.1f}s] GPU Memory - Allocated: {gpu_memory_allocated:.2f} GB, Reserved: {gpu_memory_reserved:.2f} GB")
                sys.stdout.flush()
            else:
                print(f"[{elapsed:.1f}s] Warning: CUDA not available - models may be running on CPU")
                sys.stdout.flush()
        except Exception as e:
            print(f"[{elapsed:.1f}s] Could not check GPU memory: {e}")
            sys.stdout.flush()
        
        bark_models_loaded = True
        loading_status["status"] = "complete"
        loading_status["progress"] = 100
        loading_status["message"] = f"Bark models ready! (took {elapsed:.1f} seconds)"
        loading_error = None
        
        print("=" * 60)
        print(f"✓ Bark models loaded successfully in {elapsed:.1f} seconds!")
        print("=" * 60)
        sys.stdout.flush()
        
    except Exception as e:
        elapsed = time.time() - start_time
        loading_status["status"] = "error"
        loading_status["progress"] = 100
        loading_status["message"] = f"Error after {elapsed:.1f}s: {str(e)}"
        loading_error = str(e)
        print(f"[{elapsed:.1f}s] ERROR during model loading: {str(e)}")
        import traceback
        error_trace = traceback.format_exc()
        print(error_trace)
        sys.stdout.flush()
    finally:
        model_loading = False

@app.route('/')
def index():
    """Serve the web UI"""
    return render_template('index.html')

@app.route('/ready')
def ready():
    """Health check - server is ready if Flask is running"""
    # Server is always ready, models are optional
    return "Ready", 200

@app.route('/api/status', methods=['GET'])
def status():
    """Get server and model status"""
    return {
        "models_loaded": bark_models_loaded,
        "loading_status": loading_status,
        "loading_error": loading_error,
        "sample_rate": SAMPLE_RATE if bark_models_loaded else None
    }, 200

@app.route('/api/models/load', methods=['POST'])
def load_models_endpoint():
    """Load Bark models"""
    global model_loading
    
    if model_loading:
        return {"error": "Models are already loading", "loading_status": loading_status}, 409
    
    if bark_models_loaded:
        return {"message": "Models are already loaded", "loading_status": loading_status}, 200
    
    # Load in background
    threading.Thread(target=load_models, daemon=True).start()
    
    return {"message": "Loading Bark models...", "loading_status": loading_status}, 202

@app.route('/api/tts', methods=['POST'])
def synthesize():
    """Generate audio from text using Bark"""
    global bark_models_loaded, model_loading, loading_status
    
    # Check if models are ready
    if not bark_models_loaded:
        # Auto-start loading if not already started
        if not model_loading:
            threading.Thread(target=load_models, daemon=True).start()
            return {
                "error": "Models are not loaded. Starting model download now...",
                "message": "Bark models are being downloaded from Hugging Face. This may take 5-15 minutes on first run.",
                "status": "loading",
                "loading_status": loading_status,
                "suggestion": "Check /api/status endpoint for progress, or wait a few minutes and try again."
            }, 503
        
        # Models are currently loading
        return {
            "error": "Models are still loading. Please wait and try again.",
            "message": f"Bark models are being downloaded/loaded. Current status: {loading_status.get('message', 'Loading...')}",
            "status": "loading",
            "loading_status": loading_status,
            "progress": loading_status.get("progress", 0),
            "suggestion": "Check /api/status endpoint for detailed progress, or wait a few minutes and try again."
        }, 503
    
    # Get parameters from form-data or JSON
    if request.is_json:
        data = request.json
        text = data.get('text', '')
        voice_preset = data.get('voice_preset', DEFAULT_VOICE_PRESET)
        output_format = data.get('format', 'wav')  # wav, mp3
    else:
        text = request.form.get('text', '')
        voice_preset = request.form.get('voice_preset', DEFAULT_VOICE_PRESET)
        output_format = request.form.get('format', 'wav')
    
    if not text:
        return {"error": "text parameter required"}, 400
    
    try:
        # Generate audio using Bark
        print(f"Generating audio for text: {text[:50]}...")
        audio_array = generate_audio(text, history_prompt=voice_preset)
        
        # Save to temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as f:
            output_path = f.name
            write_wav(output_path, SAMPLE_RATE, audio_array)
        
        return send_file(output_path, mimetype='audio/wav', as_attachment=True, download_name='bark_output.wav')
        
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"TTS Error: {str(e)}")
        print(f"Traceback: {error_trace}")
        return {"error": f"TTS generation failed: {str(e)}", "details": error_trace}, 500

@app.route('/api/voices', methods=['GET'])
def list_voices():
    """List available voice presets"""
    # Bark supports 100+ presets, but we'll list the most common ones
    # Full list: https://github.com/suno-ai/bark#voice-presets
    common_presets = {
        "v2/en_speaker_1": "English Speaker 1 (Male)",
        "v2/en_speaker_2": "English Speaker 2 (Female)",
        "v2/en_speaker_3": "English Speaker 3 (Male)",
        "v2/en_speaker_4": "English Speaker 4 (Female)",
        "v2/en_speaker_5": "English Speaker 5 (Male)",
        "v2/en_speaker_6": "English Speaker 6 (Female)",
        "v2/en_speaker_7": "English Speaker 7 (Male)",
        "v2/en_speaker_8": "English Speaker 8 (Female)",
        "v2/en_speaker_9": "English Speaker 9 (Male)",
    }
    
    # Add multilingual presets
    multilingual_presets = {
        "v2/de_speaker_1": "German Speaker 1",
        "v2/es_speaker_1": "Spanish Speaker 1",
        "v2/fr_speaker_1": "French Speaker 1",
        "v2/hi_speaker_1": "Hindi Speaker 1",
        "v2/it_speaker_1": "Italian Speaker 1",
        "v2/ja_speaker_1": "Japanese Speaker 1",
        "v2/ko_speaker_1": "Korean Speaker 1",
        "v2/pl_speaker_1": "Polish Speaker 1",
        "v2/pt_speaker_1": "Portuguese Speaker 1",
        "v2/ru_speaker_1": "Russian Speaker 1",
        "v2/tr_speaker_1": "Turkish Speaker 1",
        "v2/zh_speaker_1": "Chinese Speaker 1",
    }
    
    return {
        "voices": {**common_presets, **multilingual_presets},
        "default": DEFAULT_VOICE_PRESET,
        "note": "Bark supports 100+ voice presets. See https://github.com/suno-ai/bark#voice-presets for full list"
    }, 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5004, debug=False)

