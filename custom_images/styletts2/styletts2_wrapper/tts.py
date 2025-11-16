"""
styletts2.tts module
Provides StyleTTS2 class wrapper for StyleTTS2 repository
"""
import sys
import os
import yaml
import torch
import torchaudio
import numpy as np
import librosa
from pathlib import Path

# Add repository to Python path
repo_path = '/app/StyleTTS2'
if repo_path not in sys.path:
    sys.path.insert(0, repo_path)

# Import repository modules
try:
    from models import *
    from utils import *
    from text_utils import TextCleaner
    from Utils.PLBERT.util import load_plbert
    from Modules.diffusion.sampler import DiffusionSampler, ADPM2Sampler, KarrasSchedule
    import phonemizer
except ImportError as e:
    print(f"Warning: Could not import some StyleTTS2 modules: {e}")

# Import ASR and F0 loaders from models.py (they're defined there, not in Utils submodules)
load_ASR_models = None
load_F0_models = None
try:
    from models import load_ASR_models, load_F0_models
    print("Loaded load_ASR_models and load_F0_models from models.py")
except ImportError as e:
    print(f"Warning: Could not import load functions from models: {e}")
    # Try alternative import paths as fallback
    try:
        from Utils.ASR.models import load_ASR_models
    except ImportError:
        try:
            from Utils import ASR
            if hasattr(ASR, 'load_ASR_models'):
                load_ASR_models = ASR.load_ASR_models
        except ImportError:
            pass
    
    try:
        from Utils.JDC.model import load_F0_models
    except ImportError:
        try:
            from Utils import JDC
            if hasattr(JDC, 'load_F0_models'):
                load_F0_models = JDC.load_F0_models
        except ImportError:
            pass

class StyleTTS2:
    """
    StyleTTS2 wrapper class that loads models and provides inference interface
    """
    def __init__(self, model_path=None, log_callback=None):
        """
        Initialize StyleTTS2 model
        
        Args:
            model_path: Path to model directory containing config.yml
            log_callback: Optional function to call for logging (func(message, level))
        """
        self.model_path = model_path or "/app/models"
        self.config = None
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = {}
        self.text_aligner = None
        self.pitch_extractor = None
        self.plbert = None
        self.sampler = None
        self.phonemizer = None
        self.to_mel = None
        self.log_callback = log_callback  # Callback for logging
        
        # Setup mel spectrogram transform
        self.to_mel = torchaudio.transforms.MelSpectrogram(
            n_mels=80, n_fft=2048, win_length=1200, hop_length=300
        )
        self.mean, self.std = -4, 4
        
        # Load configuration
        config_paths = [
            os.path.join(self.model_path, "config.yml"),
            os.path.join(self.model_path, "Models", "LJSpeech", "config.yml"),
            os.path.join(self.model_path, "LJSpeech", "config.yml"),
        ]
        
        for config_path in config_paths:
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    self.config = yaml.safe_load(f)
                self.model_path = os.path.dirname(config_path)
                self._log(f"Loaded config from {config_path}", "info")
                break
        
        if not self.config:
            self._log("No config.yml found, model will not be fully functional", "warning")
            # Initialize empty model dict so we can check if it's loaded
            self.model = {}
            return
        
        # Load models
        self._load_models()
    
    def _log(self, message, level="info"):
        """Log a message - uses callback if available, otherwise prints"""
        if self.log_callback:
            self.log_callback(message, level)
        else:
            print(f"[{level.upper()}] {message}")
    
    def _resolve_path(self, path):
        """Resolve a path from config - handles both absolute and relative paths"""
        if not path:
            return None
        
        # If absolute path, use as-is
        if os.path.isabs(path):
            return path if os.path.exists(path) else None
        
        # Try relative to StyleTTS2 repository root first (most common case)
        repo_root = '/app/StyleTTS2'
        repo_path = os.path.join(repo_root, path)
        if os.path.exists(repo_path):
            return repo_path
        
        # Try relative to model directory
        model_path = os.path.join(self.model_path, path)
        if os.path.exists(model_path):
            return model_path
        
        # Try relative to /app
        app_path = os.path.join('/app', path)
        if os.path.exists(app_path):
            return app_path
        
        # Return original path if none found (let the loader handle the error)
        return path
    
    def _load_models(self):
        """Load StyleTTS2 models from config"""
        try:
            # Load phonemizer
            try:
                self.phonemizer = phonemizer.backend.EspeakBackend(
                    language='en-us', preserve_punctuation=True, with_stress=True
                )
                self._log("Phonemizer loaded successfully", "info")
            except Exception as e:
                self._log(f"Could not load phonemizer: {e}", "warning")
            
            # Load ASR model
            if load_ASR_models:
                ASR_config = self.config.get('ASR_config', False)
                ASR_path = self.config.get('ASR_path', False)
                if ASR_path and ASR_config:
                    try:
                        # Resolve paths
                        resolved_ASR_path = self._resolve_path(ASR_path)
                        resolved_ASR_config = self._resolve_path(ASR_config)
                        
                        self._log(f"Loading ASR model from {resolved_ASR_path} with config {resolved_ASR_config}", "info")
                        if not resolved_ASR_path or not os.path.exists(resolved_ASR_path):
                            self._log(f"ASR model path does not exist: {resolved_ASR_path}", "error")
                        elif not resolved_ASR_config or not os.path.exists(resolved_ASR_config):
                            self._log(f"ASR config path does not exist: {resolved_ASR_config}", "error")
                        else:
                            self.text_aligner = load_ASR_models(resolved_ASR_path, resolved_ASR_config)
                            self._log(f"ASR model loaded successfully", "success")
                    except Exception as e:
                        self._log(f"Could not load ASR model: {e}", "error")
                        import traceback
                        error_trace = traceback.format_exc()
                        self._log(f"ASR loading traceback: {error_trace}", "error")
                else:
                    self._log(f"ASR paths not found in config: ASR_path={ASR_path}, ASR_config={ASR_config}", "warning")
            
            # Load F0 model
            if load_F0_models:
                F0_path = self.config.get('F0_path', False)
                if F0_path:
                    try:
                        # Resolve path
                        resolved_F0_path = self._resolve_path(F0_path)
                        
                        self._log(f"Loading F0 model from {resolved_F0_path}", "info")
                        if not resolved_F0_path or not os.path.exists(resolved_F0_path):
                            self._log(f"F0 model path does not exist: {resolved_F0_path}", "error")
                        else:
                            self.pitch_extractor = load_F0_models(resolved_F0_path)
                            self._log(f"F0 model loaded successfully", "success")
                    except Exception as e:
                        self._log(f"Could not load F0 model: {e}", "error")
                        import traceback
                        error_trace = traceback.format_exc()
                        self._log(f"F0 loading traceback: {error_trace}", "error")
                else:
                    self._log(f"F0_path not found in config", "warning")
            else:
                self._log("load_F0_models function not available", "error")
            
            # Load PL-BERT
            BERT_path = self.config.get('PLBERT_dir', False)
            if BERT_path:
                try:
                    # Resolve path
                    resolved_BERT_path = self._resolve_path(BERT_path)
                    
                    self._log(f"Loading PL-BERT from {resolved_BERT_path}", "info")
                    if not resolved_BERT_path or not os.path.exists(resolved_BERT_path):
                        self._log(f"PL-BERT path does not exist: {resolved_BERT_path}", "error")
                    else:
                        # load_plbert only takes one argument (log_dir), device is handled internally
                        self.plbert = load_plbert(resolved_BERT_path)
                        if self.plbert:
                            # Move to device after loading
                            if hasattr(self.plbert, 'to'):
                                self.plbert = self.plbert.to(self.device)
                            self._log(f"PL-BERT loaded successfully from {resolved_BERT_path}", "success")
                except Exception as e:
                    self._log(f"Could not load PL-BERT: {e}", "error")
                    import traceback
                    error_trace = traceback.format_exc()
                    self._log(f"PL-BERT loading traceback: {error_trace}", "error")
            else:
                self._log(f"PLBERT_dir not found in config", "warning")
            
            # Build main model
            if self.text_aligner and self.pitch_extractor and self.plbert:
                try:
                    self.model = build_model(
                        recursive_munch(self.config['model_params']),
                        self.text_aligner,
                        self.pitch_extractor,
                        self.plbert
                    )
                    # Load model weights
                    self._load_model_weights()
                    # Set to eval mode and device
                    _ = [self.model[key].eval() for key in self.model]
                    _ = [self.model[key].to(self.device) for key in self.model]
                    
                    # Setup diffusion sampler
                    self.sampler = DiffusionSampler(
                        self.model.diffusion.diffusion,
                        sampler=ADPM2Sampler(),
                        sigma_schedule=KarrasSchedule(sigma_min=0.0001, sigma_max=3.0, rho=9.0),
                        clamp=False
                    )
                    self._log("StyleTTS2 models loaded successfully", "success")
                except Exception as e:
                    self._log(f"Could not build model: {e}", "error")
                    import traceback
                    error_trace = traceback.format_exc()
                    self._log(f"Model building traceback: {error_trace}", "error")
        except Exception as e:
            self._log(f"Error loading models: {e}", "error")
            import traceback
            error_trace = traceback.format_exc()
            self._log(f"Model loading traceback: {error_trace}", "error")
    
    def _load_model_weights(self):
        """Load model weights from checkpoint"""
        # Try to find checkpoint file
        checkpoint_paths = [
            os.path.join(self.model_path, "epoch_2nd_00100.pth"),
            os.path.join(self.model_path, "checkpoint.pth"),
            os.path.join(os.path.dirname(self.model_path), "epoch_2nd_00100.pth"),
        ]
        
        for checkpoint_path in checkpoint_paths:
            if os.path.exists(checkpoint_path):
                try:
                    params_whole = torch.load(checkpoint_path, map_location='cpu')
                    params = params_whole.get('net', params_whole)
                    
                    for key in self.model:
                        if key in params:
                            try:
                                self.model[key].load_state_dict(params[key], strict=False)
                                self._log(f'{key} loaded', "info")
                            except Exception as e:
                                # Try with module prefix removed
                                try:
                                    from collections import OrderedDict
                                    state_dict = params[key]
                                    new_state_dict = OrderedDict()
                                    for k, v in state_dict.items():
                                        name = k[7:] if k.startswith('module.') else k
                                        new_state_dict[name] = v
                                    self.model[key].load_state_dict(new_state_dict, strict=False)
                                    self._log(f'{key} loaded (with prefix removal)', "info")
                                except Exception as e2:
                                    self._log(f'Could not load {key}: {e2}', "warning")
                    return
                except Exception as e:
                    self._log(f"Could not load checkpoint {checkpoint_path}: {e}", "warning")
                    continue
        
        self._log("No checkpoint file found, model weights not loaded", "warning")
    
    def to(self, device):
        """Move model to device"""
        self.device = device
        if self.model:
            _ = [self.model[key].to(device) for key in self.model]
        return self
    
    def _preprocess_wave(self, wave):
        """Preprocess audio wave to mel spectrogram"""
        wave_tensor = torch.from_numpy(wave).float()
        mel_tensor = self.to_mel(wave_tensor)
        mel_tensor = (torch.log(1e-5 + mel_tensor.unsqueeze(0)) - self.mean) / self.std
        return mel_tensor
    
    def inference(self, text, output_wav_file, target_voice_path=None, 
                  alpha=0.3, beta=0.7, diffusion_steps=10):
        """
        Generate speech from text using StyleTTS2
        
        Args:
            text: Input text to synthesize
            output_wav_file: Path to save output WAV file
            target_voice_path: Optional path to reference audio for voice cloning
            alpha: Style control parameter (0.0-1.0)
            beta: Style control parameter (0.0-1.0)
            diffusion_steps: Number of diffusion steps (quality vs speed)
        """
        if not self.model or len(self.model) == 0:
            raise RuntimeError("Model not loaded. Please ensure config.yml and model weights are available.")
        
        if not self.sampler:
            raise RuntimeError("Model sampler not initialized. Model may not be fully loaded.")
        
        if not self.text_aligner or not self.pitch_extractor or not self.plbert:
            raise RuntimeError("Model components not loaded. Please ensure ASR, F0, and PL-BERT models are available.")
        
        try:
            self._log(f"Starting inference: text='{text[:50]}...', alpha={alpha}, beta={beta}, steps={diffusion_steps}", "info")
            
            # Step 1: Phonemize text
            if not self.phonemizer:
                raise RuntimeError("Phonemizer not loaded. Cannot process text.")
            
            self._log("Phonemizing text...", "info")
            phonemes = self.phonemizer.phonemize([text], strip=True)[0]
            self._log(f"Phonemes: {phonemes[:100]}...", "info")
            
            # Step 2: Convert phonemes to tokens
            from text_utils import TextCleaner
            text_cleaner = TextCleaner()
            phoneme_ids = text_cleaner(phonemes)
            phoneme_ids = torch.LongTensor(phoneme_ids).unsqueeze(0).to(self.device)
            self._log(f"Converted to {len(phoneme_ids[0])} tokens", "info")
            
            # Step 3: Extract style from reference (if provided) or use default
            style = None
            if target_voice_path and os.path.exists(target_voice_path):
                self._log(f"Extracting style from reference: {target_voice_path}", "info")
                try:
                    # Load reference audio
                    ref_audio, ref_sr = librosa.load(target_voice_path, sr=24000)
                    ref_audio = torch.from_numpy(ref_audio).unsqueeze(0).to(self.device)
                    
                    # Extract mel spectrogram
                    ref_mel = self.to_mel(ref_audio)
                    ref_mel = (torch.log(1e-5 + ref_mel) - self.mean) / self.std
                    
                    # Extract style using style encoder
                    if 'style_encoder' in self.model:
                        with torch.no_grad():
                            style = self.model.style_encoder(ref_mel)
                    else:
                        self._log("Style encoder not found, using default style", "warning")
                except Exception as e:
                    self._log(f"Could not extract style from reference: {e}. Using default style.", "warning")
            
            # Step 4: Text encoding
            self._log("Encoding text...", "info")
            if 'text_encoder' not in self.model:
                raise RuntimeError("Text encoder not found in model")
            
            with torch.no_grad():
                # Get text embeddings
                text_lengths = torch.LongTensor([phoneme_ids.shape[1]]).to(self.device)
                
                # Create mask m from text_lengths
                # m is a boolean mask where True indicates valid positions
                max_len = phoneme_ids.shape[1]
                m = torch.arange(max_len).unsqueeze(0).expand(phoneme_ids.shape[0], -1).to(self.device)
                m = (m < text_lengths.unsqueeze(1)).to(self.device)
                
                # Encode text (text_encoder requires: phoneme_ids, text_lengths, m)
                text_encoded = self.model.text_encoder(phoneme_ids, text_lengths, m)
                
                # If no style provided, use default or extract from text
                if style is None:
                    # Use a default style vector (zeros or learned default)
                    style_dim = self.config.get('model_params', {}).get('style_dim', 128)
                    style = torch.zeros(1, style_dim).to(self.device)
                    self._log("Using default style", "info")
            
            # Step 5: Generate audio with diffusion sampler
            self._log(f"Generating audio with {diffusion_steps} diffusion steps...", "info")
            
            # Prepare conditioning
            # This is a simplified version - full implementation would need proper conditioning
            try:
                # Generate mel spectrogram using diffusion
                # Note: This is a simplified version. Full implementation requires proper conditioning
                # including duration prediction, prosody, etc.
                
                # For now, generate a basic mel spectrogram
                # The actual StyleTTS2 pipeline is more complex and requires:
                # - Duration prediction
                # - Prosody prediction  
                # - Proper conditioning for diffusion
                
                # Simplified: Generate mel from text encoding
                mel_length = text_encoded.shape[1] * 2  # Rough estimate
                
                # Use diffusion sampler if available
                if self.sampler and 'diffusion' in self.model:
                    # Sample from diffusion model
                    # This is simplified - actual implementation needs proper conditioning
                    noise = torch.randn(1, 80, mel_length).to(self.device)
                    
                    # Sample (simplified - would need proper conditioning)
                    # For now, raise an informative error
                    raise NotImplementedError(
                        "Full StyleTTS2 inference pipeline not yet implemented. "
                        "This requires: duration prediction, prosody prediction, and proper diffusion conditioning. "
                        "The model components are loaded, but the inference pipeline needs to be completed."
                    )
                else:
                    raise RuntimeError("Diffusion sampler or model not available")
                    
            except NotImplementedError:
                # Re-raise with better message
                raise
            except Exception as e:
                self._log(f"Error during audio generation: {e}", "error")
                raise RuntimeError(f"Audio generation failed: {str(e)}")
            
        except NotImplementedError as e:
            # Return a clear error instead of silent audio
            self._log(f"Inference not fully implemented: {e}", "error")
            raise RuntimeError(
                "TTS inference is not yet fully implemented. "
                "The model is loaded, but the inference pipeline needs to be completed. "
                "This requires implementing: duration prediction, prosody prediction, and diffusion sampling. "
                f"Error: {str(e)}"
            )
        except Exception as e:
            self._log(f"Error during inference: {e}", "error")
            import traceback
            error_trace = traceback.format_exc()
            self._log(f"Inference traceback: {error_trace}", "error")
            raise

# Export StyleTTS2 class
__all__ = ['StyleTTS2']
