#!/usr/bin/env python3
"""
StyleTTS2 Flask API Server
Provides REST API for text-to-speech synthesis with voice cloning
"""

from flask import Flask, request, send_file, jsonify
from styletts2 import tts
import torch
import tempfile
import os
import threading
import shutil
import subprocess

app = Flask(__name__)
styletts2_model = None
loading_error = None
device = None

def download_models_if_needed():
    """Download models if they don't exist in /app/models"""
    model_path = "/app/models"
    
    # Check if models already exist
    if (os.path.exists(os.path.join(model_path, "config.json")) or
        os.path.exists(os.path.join(model_path, "Models", "LJSpeech", "config.yml")) or
        os.path.exists(os.path.join(model_path, "LJSpeech", "config.yml"))):
        print("Models already present, skipping download")
        return
    
    print("Models not found. Downloading StyleTTS2 models...")
    try:
        # Download models using gdown
        import gdown
        os.makedirs("/tmp/models", exist_ok=True)
        zip_path = "/tmp/models/Models.zip"
        
        print("Downloading models from Google Drive...")
        gdown.download(id="1K3jt1JEbtohBLUA0X75KLw36TW7U1yxq", output=zip_path, quiet=False)
        
        if os.path.exists(zip_path):
            print("Extracting models (this may take a few minutes)...")
            # Extract to /tmp first, then move to /app/models
            subprocess.run(["unzip", "-o", "-q", zip_path, "-d", "/tmp/models/"], check=True)
            
            # Move extracted files to /app/models
            if os.path.exists("/tmp/models/Models"):
                subprocess.run(["cp", "-r", "/tmp/models/Models", model_path], check=True)
                print("Models extracted successfully")
            
            # Cleanup
            shutil.rmtree("/tmp/models", ignore_errors=True)
        else:
            print("Warning: Model download failed, will use default models")
    except Exception as e:
        print(f"Warning: Model download failed: {e}. Will use default models if available.")

def load_model():
    """Load StyleTTS2 model in background"""
    global styletts2_model, loading_error, device
    try:
        print("Loading StyleTTS2 model...")
        device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"Using device: {device}")
        
        # Try to download models if needed (non-blocking)
        download_thread = threading.Thread(target=download_models_if_needed, daemon=True)
        download_thread.start()
        download_thread.join(timeout=60)  # Wait up to 60 seconds for download to start
        
        # Initialize StyleTTS2
        model_path = "/app/models"
        # Check for various possible model paths
        if os.path.exists(os.path.join(model_path, "config.json")):
            print(f"Loading model from {model_path}")
            styletts2_model = tts.StyleTTS2(model_path=model_path)
        elif os.path.exists(os.path.join(model_path, "Models", "LJSpeech", "config.yml")):
            # Models extracted from zip file
            ljspeech_path = os.path.join(model_path, "Models", "LJSpeech")
            print(f"Loading LJSpeech model from {ljspeech_path}")
            styletts2_model = tts.StyleTTS2(model_path=ljspeech_path)
        elif os.path.exists(os.path.join(model_path, "LJSpeech", "config.yml")):
            # Alternative path structure
            ljspeech_path = os.path.join(model_path, "LJSpeech")
            print(f"Loading LJSpeech model from {ljspeech_path}")
            styletts2_model = tts.StyleTTS2(model_path=ljspeech_path)
        else:
            print("Loading default StyleTTS2 model (will download if needed)...")
            styletts2_model = tts.StyleTTS2()
        
        # Move to GPU if available
        if device == "cuda":
            styletts2_model.to(device)
        
        print("StyleTTS2 model loaded successfully!")
    except Exception as e:
        loading_error = str(e)
        print(f"Failed to load model: {e}")
        import traceback
        traceback.print_exc()

# Start model loading in background
threading.Thread(target=load_model, daemon=True).start()

@app.route('/')
def index():
    if styletts2_model:
        return "StyleTTS2 Server - Ready", 200
    elif loading_error:
        return f"StyleTTS2 Server - Error: {loading_error}", 200
    else:
        return "StyleTTS2 Server - Loading model...", 200

@app.route('/ready')
def ready():
    if styletts2_model:
        return "Ready", 200
    elif loading_error:
        return f"Error: {loading_error}", 503
    else:
        return "Loading...", 503

# Voice storage directory (on persistent volume)
VOICE_DIR = "/app/voices"
os.makedirs(VOICE_DIR, exist_ok=True)

@app.route('/api/upload-voice', methods=['POST'])
def upload_voice():
    """Upload a voice file for cloning"""
    if not styletts2_model:
        return {"error": "Model still loading"}, 503
    
    if 'file' not in request.files:
        return {"error": "No file provided"}, 400
    
    file = request.files['file']
    voice_name = request.form.get('name', 'default')
    
    if file.filename == '':
        return {"error": "No file selected"}, 400
    
    # Create voice directory
    voice_path = os.path.join(VOICE_DIR, voice_name)
    os.makedirs(voice_path, exist_ok=True)
    
    # Save file
    filename = file.filename or 'voice.wav'
    filepath = os.path.join(voice_path, filename)
    file.save(filepath)
    
    return {
        "message": "Voice file uploaded successfully",
        "voice_name": voice_name,
        "filepath": filepath,
        "usage": f"Use target_voice_path={filepath} in /api/tts requests"
    }, 200

@app.route('/api/voices', methods=['GET'])
def list_voices():
    """List available voice files"""
    voices = {}
    if os.path.exists(VOICE_DIR):
        for voice_name in os.listdir(VOICE_DIR):
            voice_path = os.path.join(VOICE_DIR, voice_name)
            if os.path.isdir(voice_path):
                files = [f for f in os.listdir(voice_path) 
                        if f.lower().endswith(('.wav', '.mp3', '.flac', '.aif', '.aiff'))]
                if files:
                    voices[voice_name] = [os.path.join(voice_path, f) for f in files]
    return {"voices": voices}, 200

@app.route('/api/test-voice', methods=['POST'])
def test_voice():
    """Test a specific voice file to see quality"""
    if not styletts2_model:
        return {"error": "Model still loading"}, 503
    
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
    if not styletts2_model:
        return {"error": "Model still loading"}, 503
    
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

