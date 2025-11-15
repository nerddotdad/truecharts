#!/usr/bin/env python3
"""
StyleTTS2 Flask API Server
Provides REST API for text-to-speech synthesis with voice cloning
"""

from flask import Flask, request, send_file, jsonify, render_template
from styletts2 import tts
import torch
import tempfile
import os
import threading
import shutil
import subprocess
import json
from datetime import datetime

app = Flask(__name__)
styletts2_model = None
loading_error = None
device = None
model_loading = False
download_status = {"status": "idle", "progress": 0, "message": ""}
loading_status = {"status": "idle", "progress": 0, "message": ""}

# Available models configuration
AVAILABLE_MODELS = {
    "LJSpeech": {
        "name": "LJSpeech",
        "description": "Single-speaker English model trained on LJSpeech dataset",
        "size": "~2GB",
        "drive_id": "1K3jt1JEbtohBLUA0X75KLw36TW7U1yxq",
        "path": "Models/LJSpeech"
    },
    "LibriTTS": {
        "name": "LibriTTS",
        "description": "Multi-speaker English model trained on LibriTTS dataset",
        "size": "~2GB",
        "drive_id": "1K3jt1JEbtohBLUA0X75KLw36TW7U1yxq",  # Same zip, different subfolder
        "path": "Models/LibriTTS"
    }
}

def check_installed_models():
    """Check which models are installed"""
    model_path = "/app/models"
    installed = {}
    
    for model_id, model_info in AVAILABLE_MODELS.items():
        config_paths = [
            os.path.join(model_path, model_info["path"], "config.yml"),
            os.path.join(model_path, "Models", model_info["name"], "config.yml"),
            os.path.join(model_path, model_info["name"], "config.yml"),
        ]
        
        for config_path in config_paths:
            if os.path.exists(config_path):
                installed[model_id] = {
                    "installed": True,
                    "path": os.path.dirname(config_path),
                    "config": config_path
                }
                break
        else:
            installed[model_id] = {"installed": False}
    
    return installed

def download_model(model_id):
    """Download a specific model"""
    global download_status
    
    if model_id not in AVAILABLE_MODELS:
        download_status = {"status": "error", "progress": 0, "message": f"Unknown model: {model_id}"}
        return False
    
    model_info = AVAILABLE_MODELS[model_id]
    model_path = "/app/models"
    
    try:
        download_status = {"status": "downloading", "progress": 0, "message": f"Starting download of {model_info['name']}..."}
        
        import gdown
        import time
        os.makedirs("/tmp/models", exist_ok=True)
        zip_path = "/tmp/models/Models.zip"
        
        download_status["message"] = "Connecting to Google Drive..."
        download_status["progress"] = 5
        
        # Download using gdown - try multiple methods
        download_success = False
        last_size = 0
        stall_count = 0
        
        def check_download_progress():
            """Check if download is progressing"""
            nonlocal last_size, stall_count
            if os.path.exists(zip_path):
                current_size = os.path.getsize(zip_path)
                if current_size == last_size:
                    stall_count += 1
                else:
                    stall_count = 0
                    # Update progress based on file size (assuming ~2GB file)
                    estimated_total = 2 * 1024 * 1024 * 1024  # 2GB
                    progress = min(50, 10 + int((current_size / estimated_total) * 40))
                    download_status["progress"] = progress
                    download_status["message"] = f"Downloading... {current_size // (1024*1024)}MB"
                last_size = current_size
                return stall_count < 60  # Allow 60 seconds of no progress
            return True
        
        # Start download in a way that allows progress checking
        try:
            # Method 1: Direct download
            print(f"Attempting to download model {model_id} from Google Drive...")
            gdown.download(
                id=model_info["drive_id"], 
                output=zip_path, 
                quiet=True,  # Set to True to avoid output issues
                use_cookies=False
            )
            download_success = True
        except Exception as e:
            print(f"Method 1 failed: {e}, trying alternative...")
            try:
                # Method 2: URL-based download
                url = f"https://drive.google.com/uc?id={model_info['drive_id']}"
                gdown.download(url, zip_path, quiet=True, use_cookies=False)
                download_success = True
            except Exception as e2:
                print(f"Method 2 failed: {e2}")
                download_status = {"status": "error", "progress": 0, "message": f"Download failed: {str(e2)}"}
                return False
        
        # Verify download
        if not download_success or not os.path.exists(zip_path):
            download_status = {"status": "error", "progress": 0, "message": "Download failed: File not created"}
            return False
            
        file_size = os.path.getsize(zip_path)
        if file_size == 0:
            download_status = {"status": "error", "progress": 0, "message": "Download failed: File is empty"}
            return False
        
        # Check if file is suspiciously small (likely an error page)
        if file_size < 1024 * 1024:  # Less than 1MB
            download_status = {"status": "error", "progress": 0, "message": f"Download failed: File too small ({file_size} bytes) - may be an error page"}
            return False
        
        download_status["progress"] = 50
        download_status["message"] = f"Download complete ({file_size // (1024*1024)}MB). Extracting..."
        
        # Extract
        result = subprocess.run(
            ["unzip", "-o", "-q", zip_path, "-d", "/tmp/models/"], 
            check=True,
            capture_output=True,
            text=True
        )
        
        download_status["progress"] = 75
        download_status["message"] = "Installing model files..."
        
        # Move extracted files
        if os.path.exists("/tmp/models/Models"):
            os.makedirs(model_path, exist_ok=True)
            subprocess.run(["cp", "-r", "/tmp/models/Models", model_path], check=True)
        else:
            download_status = {"status": "error", "progress": 0, "message": "Extraction failed: Models directory not found"}
            return False
        
        # Cleanup
        shutil.rmtree("/tmp/models", ignore_errors=True)
        
        download_status = {"status": "complete", "progress": 100, "message": f"{model_info['name']} installed successfully"}
        return True
        
    except subprocess.CalledProcessError as e:
        error_msg = f"Command failed: {e.stderr.decode() if e.stderr else str(e)}"
        download_status = {"status": "error", "progress": 0, "message": f"Download failed: {error_msg}"}
        import traceback
        traceback.print_exc()
        return False
    except Exception as e:
        download_status = {"status": "error", "progress": 0, "message": f"Download failed: {str(e)}"}
        import traceback
        traceback.print_exc()
        return False

def load_model(model_path=None):
    """Load StyleTTS2 model"""
    global styletts2_model, loading_error, device, model_loading, loading_status
    
    if model_loading:
        return
    
    model_loading = True
    loading_status = {"status": "loading", "progress": 0, "message": "Initializing model loading..."}
    
    try:
        print(f"Loading StyleTTS2 model from {model_path or 'default'}...")
        device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"Using device: {device}")
        
        loading_status["progress"] = 20
        loading_status["message"] = f"Using device: {device}"
        
        if model_path and os.path.exists(model_path):
            loading_status["progress"] = 30
            loading_status["message"] = f"Loading model from {model_path}..."
            styletts2_model = tts.StyleTTS2(model_path=model_path)
        else:
            # Try to find any installed model
            installed = check_installed_models()
            loading_status["progress"] = 30
            loading_status["message"] = "Searching for installed models..."
            for model_id, info in installed.items():
                if info.get("installed") and "path" in info:
                    print(f"Loading {model_id} from {info['path']}")
                    loading_status["message"] = f"Loading {model_id} from {info['path']}..."
                    styletts2_model = tts.StyleTTS2(model_path=info["path"])
                    break
            else:
                # No model found, create empty instance
                loading_status["message"] = "No model found, creating empty instance..."
                styletts2_model = tts.StyleTTS2()
        
        loading_status["progress"] = 60
        loading_status["message"] = "Moving model to device..."
        
        # Move to GPU if available
        if device == "cuda" and styletts2_model:
            styletts2_model.to(device)
        
        loading_status["progress"] = 100
        loading_status["status"] = "complete"
        loading_status["message"] = "Model loaded successfully!"
        print("StyleTTS2 model loaded successfully!")
        loading_error = None
    except Exception as e:
        loading_error = str(e)
        loading_status = {"status": "error", "progress": 0, "message": f"Failed to load model: {str(e)}"}
        print(f"Failed to load model: {e}")
        import traceback
        traceback.print_exc()
    finally:
        model_loading = False

# Initialize device (but don't load models yet)
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"StyleTTS2 Server initialized. Device: {device}")
print("Models will be loaded on-demand or via API")

@app.route('/')
def index():
    """Serve the web UI"""
    return render_template('index.html')

@app.route('/ready')
def ready():
    """Health check - server is ready if Flask is running"""
    # Server is always ready, models are optional
    return "Ready", 200

@app.route('/api/models', methods=['GET'])
def list_models():
    """List available models and their installation status"""
    installed = check_installed_models()
    
    models = {}
    for model_id, model_info in AVAILABLE_MODELS.items():
        models[model_id] = {
            **model_info,
            "installed": installed.get(model_id, {}).get("installed", False),
            "path": installed.get(model_id, {}).get("path")
        }
    
    return {
        "models": models,
        "download_status": download_status,
        "model_loaded": styletts2_model is not None and hasattr(styletts2_model, 'model') and styletts2_model.model
    }, 200

@app.route('/api/models/download', methods=['POST'])
def download_model_endpoint():
    """Download a specific model"""
    global download_status
    
    if download_status["status"] == "downloading":
        return {"error": "A download is already in progress"}, 409
    
    data = request.json if request.is_json else request.form
    model_id = data.get('model_id') or data.get('model')
    
    if not model_id:
        return {"error": "model_id parameter required"}, 400
    
    if model_id not in AVAILABLE_MODELS:
        return {"error": f"Unknown model: {model_id}. Available: {list(AVAILABLE_MODELS.keys())}"}, 400
    
    # Check if already installed
    installed = check_installed_models()
    if installed.get(model_id, {}).get("installed"):
        return {"message": f"{model_id} is already installed", "model_id": model_id}, 200
    
    # Start download in background
    def download_thread():
        download_model(model_id)
        # Auto-load model after download
        if download_status["status"] == "complete":
            installed = check_installed_models()
            if model_id in installed and installed[model_id].get("installed"):
                load_model(installed[model_id]["path"])
    
    threading.Thread(target=download_thread, daemon=True).start()
    
    return {"message": f"Download started for {model_id}", "model_id": model_id}, 202

@app.route('/api/models/status', methods=['GET'])
def model_download_status():
    """Get model download and loading status"""
    return {
        "download_status": download_status,
        "loading_status": loading_status,
        "model_loaded": styletts2_model is not None and hasattr(styletts2_model, 'model') and styletts2_model.model,
        "loading_error": loading_error
    }, 200

@app.route('/api/models/load', methods=['POST'])
def load_model_endpoint():
    """Load a specific installed model"""
    global model_loading, loading_status
    
    if model_loading:
        return {"error": "Model is already loading", "loading_status": loading_status}, 409
    
    data = request.json if request.is_json else request.form
    model_id = data.get('model_id') or data.get('model')
    
    installed = check_installed_models()
    
    if model_id:
        if model_id not in installed or not installed[model_id].get("installed"):
            return {"error": f"Model {model_id} is not installed"}, 404
        model_path = installed[model_id]["path"]
    else:
        # Load first available model
        for mid, info in installed.items():
            if info.get("installed") and "path" in info:
                model_path = info["path"]
                model_id = mid
                break
        else:
            return {"error": "No models installed. Please download a model first."}, 404
    
    # Reset loading status
    loading_status = {"status": "loading", "progress": 0, "message": f"Starting to load {model_id}..."}
    
    # Load in background
    threading.Thread(target=lambda: load_model(model_path), daemon=True).start()
    
    return {"message": f"Loading {model_id}...", "model_id": model_id, "loading_status": loading_status}, 202

# Voice storage directory (on persistent volume)
VOICE_DIR = "/app/voices"
os.makedirs(VOICE_DIR, exist_ok=True)

@app.route('/api/upload-voice', methods=['POST'])
def upload_voice():
    """Upload voice file(s) for cloning - supports multiple files"""
    if not styletts2_model or not (hasattr(styletts2_model, 'model') and styletts2_model.model):
        return {"error": "No model loaded. Please download and load a model first."}, 503
    
    if 'files' not in request.files and 'file' not in request.files:
        return {"error": "No file provided"}, 400
    
    voice_name = request.form.get('name', 'default')
    if not voice_name or voice_name.strip() == '':
        return {"error": "Voice name is required"}, 400
    
    # Create voice directory
    voice_path = os.path.join(VOICE_DIR, voice_name)
    os.makedirs(voice_path, exist_ok=True)
    
    uploaded_files = []
    
    # Handle multiple files (files[]) or single file (file)
    files = request.files.getlist('files') if 'files' in request.files else [request.files.get('file')]
    
    for file in files:
        if file and file.filename:
            # Sanitize filename
            filename = os.path.basename(file.filename)
            filepath = os.path.join(voice_path, filename)
            file.save(filepath)
            uploaded_files.append({
                "filename": filename,
                "path": filepath
            })
    
    if not uploaded_files:
        return {"error": "No valid files uploaded"}, 400
    
    return {
        "message": f"Uploaded {len(uploaded_files)} file(s) successfully",
        "voice_name": voice_name,
        "files": uploaded_files,
        "voice_path": voice_path
    }, 200

@app.route('/api/voices', methods=['GET'])
def list_voices():
    """List available voice files with detailed information"""
    voices = {}
    if os.path.exists(VOICE_DIR):
        for voice_name in os.listdir(VOICE_DIR):
            voice_path = os.path.join(VOICE_DIR, voice_name)
            if os.path.isdir(voice_path):
                files = []
                for f in os.listdir(voice_path):
                    if f.lower().endswith(('.wav', '.mp3', '.flac', '.aif', '.aiff')):
                        filepath = os.path.join(voice_path, f)
                        file_size = os.path.getsize(filepath)
                        files.append({
                            "filename": f,
                            "path": filepath,
                            "size": file_size,
                            "size_mb": round(file_size / (1024 * 1024), 2)
                        })
                if files:
                    voices[voice_name] = {
                        "name": voice_name,
                        "path": voice_path,
                        "files": files,
                        "file_count": len(files)
                    }
    return {"voices": voices}, 200

@app.route('/api/test-voice', methods=['POST'])
def test_voice():
    """Test a specific voice file to see quality"""
    if not styletts2_model or not (hasattr(styletts2_model, 'model') and styletts2_model.model):
        return {"error": "No model loaded"}, 503
    
    if request.is_json:
        data = request.json
        target_voice_path = data.get('target_voice_path', None)
        text = data.get('text', 'Hello, this is a test of the voice quality.')
    else:
        target_voice_path = request.form.get('target_voice_path', None)
        text = request.form.get('text', 'Hello, this is a test of the voice quality.')
    
    if not target_voice_path:
        return {"error": "target_voice_path parameter required"}, 400
    
    # Handle voice name or path
    if not target_voice_path.startswith('/'):
        voice_path = os.path.join(VOICE_DIR, target_voice_path)
        if os.path.exists(voice_path):
            if os.path.isdir(voice_path):
                # Find first audio file in directory
                audio_files = [f for f in os.listdir(voice_path) 
                              if f.lower().endswith(('.wav', '.mp3', '.flac', '.aif', '.aiff'))]
                if audio_files:
                    target_voice_path = os.path.join(voice_path, audio_files[0])
                else:
                    return {"error": f"No audio files found for voice '{target_voice_path}'"}, 404
            else:
                target_voice_path = voice_path
        else:
            return {"error": f"Voice '{target_voice_path}' not found"}, 404
    
    if not os.path.exists(target_voice_path):
        return {"error": f"Voice file not found: {target_voice_path}"}, 404
    
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as f:
            output_path = f.name
        
        # StyleTTS2 inference with voice cloning
        styletts2_model.inference(
            text=text,
            target_voice_path=target_voice_path,
            output_wav_file=output_path
        )
        
        return send_file(output_path, mimetype='audio/wav')
    except Exception as e:
        return {"error": f"TTS generation failed: {str(e)}"}, 500

@app.route('/api/delete-voice', methods=['DELETE', 'POST'])
def delete_voice():
    """Delete a voice file or entire voice directory"""
    if request.is_json:
        data = request.json
        voice_name = data.get('name', '')
        filename = data.get('filename', None)
    else:
        voice_name = request.form.get('name', '')
        filename = request.form.get('filename', None)
    
    if not voice_name:
        return {"error": "voice name required"}, 400
    
    voice_path = os.path.join(VOICE_DIR, voice_name)
    
    if not os.path.exists(voice_path):
        return {"error": f"Voice '{voice_name}' not found"}, 404
    
    try:
        if filename:
            filepath = os.path.join(voice_path, filename)
            if os.path.exists(filepath):
                os.remove(filepath)
                return {"message": f"Deleted file: {filename}"}, 200
            else:
                return {"error": f"File '{filename}' not found"}, 404
        else:
            shutil.rmtree(voice_path)
            return {"message": f"Deleted voice: {voice_name}"}, 200
    except Exception as e:
        return {"error": f"Failed to delete: {str(e)}"}, 500

@app.route('/api/tts', methods=['POST'])
def synthesize():
    if not styletts2_model or not (hasattr(styletts2_model, 'model') and styletts2_model.model):
        return {"error": "No model loaded. Please download and load a model first."}, 503
    
    # Get parameters from form-data or JSON
    if request.is_json:
        data = request.json
        text = data.get('text', '')
        target_voice_path = data.get('target_voice_path', None)  # For voice cloning
        alpha = data.get('alpha', 0.3)  # Style control parameter (0.0-1.0)
        beta = data.get('beta', 0.7)  # Style control parameter (0.0-1.0)
        diffusion_steps = data.get('diffusion_steps', 10)  # Quality vs speed tradeoff
    else:
        text = request.form.get('text', '')
        target_voice_path = request.form.get('target_voice_path', None)
        alpha = float(request.form.get('alpha', 0.3))
        beta = float(request.form.get('beta', 0.7))
        diffusion_steps = int(request.form.get('diffusion_steps', 10))
    
    if not text:
        return {"error": "text parameter required"}, 400
    
    # Handle voice path (voice cloning)
    if target_voice_path:
        if not target_voice_path.startswith('/'):
            voice_path = os.path.join(VOICE_DIR, target_voice_path)
            if os.path.exists(voice_path):
                if os.path.isdir(voice_path):
                    # Find first audio file in directory
                    audio_files = [f for f in os.listdir(voice_path) 
                                  if f.lower().endswith(('.wav', '.mp3', '.flac', '.aif', '.aiff'))]
                    if audio_files:
                        target_voice_path = os.path.join(voice_path, audio_files[0])
                    else:
                        return {"error": f"No audio files found for voice '{target_voice_path}'"}, 404
                else:
                    target_voice_path = voice_path
            else:
                return {"error": f"Voice '{target_voice_path}' not found"}, 404
        
        if not os.path.exists(target_voice_path):
            return {"error": f"Voice file not found: {target_voice_path}"}, 404
    
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as f:
            output_path = f.name
        
        # StyleTTS2 inference
        if target_voice_path:
            # Voice cloning mode
            styletts2_model.inference(
                text=text,
                target_voice_path=target_voice_path,
                output_wav_file=output_path,
                alpha=alpha,
                beta=beta,
                diffusion_steps=diffusion_steps
            )
        else:
            # Default voice mode
            styletts2_model.inference(
                text=text,
                output_wav_file=output_path,
                alpha=alpha,
                beta=beta,
                diffusion_steps=diffusion_steps
            )
        
        return send_file(output_path, mimetype='audio/wav')
    except Exception as e:
        return {"error": f"TTS generation failed: {str(e)}"}, 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5003, debug=False)
