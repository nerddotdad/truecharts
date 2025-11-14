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

# Try to import ASR and F0 loaders (may not exist or may be in different locations)
load_ASR_models = None
load_F0_models = None
try:
    from Utils.ASR.models import load_ASR_models
except ImportError:
    try:
        # Try alternative import path
        from Utils import ASR
        if hasattr(ASR, 'load_ASR_models'):
            load_ASR_models = ASR.load_ASR_models
    except ImportError:
        pass

try:
    from Utils.JDC.model import load_F0_models
except ImportError:
    try:
        # Try alternative import path
        from Utils import JDC
        if hasattr(JDC, 'load_F0_models'):
            load_F0_models = JDC.load_F0_models
    except ImportError:
        pass

class StyleTTS2:
    """
    StyleTTS2 wrapper class that loads models and provides inference interface
    """
    def __init__(self, model_path=None):
        """
        Initialize StyleTTS2 model
        
        Args:
            model_path: Path to model directory containing config.yml
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
                print(f"Loaded config from {config_path}")
                break
        
        if not self.config:
            print("Warning: No config.yml found, model will not be fully functional")
            return
        
        # Load models
        self._load_models()
    
    def _load_models(self):
        """Load StyleTTS2 models from config"""
        try:
            # Load phonemizer
            try:
                self.phonemizer = phonemizer.backend.EspeakBackend(
                    language='en-us', preserve_punctuation=True, with_stress=True
                )
            except Exception as e:
                print(f"Warning: Could not load phonemizer: {e}")
            
            # Load ASR model
            if load_ASR_models:
                ASR_config = self.config.get('ASR_config', False)
                ASR_path = self.config.get('ASR_path', False)
                if ASR_path and ASR_config:
                    try:
                        self.text_aligner = load_ASR_models(ASR_path, ASR_config)
                    except Exception as e:
                        print(f"Warning: Could not load ASR model: {e}")
            
            # Load F0 model
            if load_F0_models:
                F0_path = self.config.get('F0_path', False)
                if F0_path:
                    try:
                        self.pitch_extractor = load_F0_models(F0_path)
                    except Exception as e:
                        print(f"Warning: Could not load F0 model: {e}")
            
            # Load PL-BERT
            BERT_path = self.config.get('PLBERT_dir', False)
            if BERT_path:
                try:
                    self.plbert = load_plbert(BERT_path, self.device)
                except Exception as e:
                    print(f"Warning: Could not load PL-BERT: {e}")
            
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
                    print("StyleTTS2 models loaded successfully")
                except Exception as e:
                    print(f"Warning: Could not build model: {e}")
                    import traceback
                    traceback.print_exc()
        except Exception as e:
            print(f"Error loading models: {e}")
            import traceback
            traceback.print_exc()
    
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
                                print(f'{key} loaded')
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
                                    print(f'{key} loaded (with prefix removal)')
                                except Exception as e2:
                                    print(f'Warning: Could not load {key}: {e2}')
                    return
                except Exception as e:
                    print(f"Warning: Could not load checkpoint {checkpoint_path}: {e}")
                    continue
        
        print("Warning: No checkpoint file found, model weights not loaded")
    
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
        if not self.model or not self.sampler:
            raise RuntimeError("Model not loaded. Please ensure config.yml and model weights are available.")
        
        try:
            # This is a simplified inference - full implementation would require
            # text preprocessing, phonemization, style extraction, and diffusion sampling
            # For now, this provides the interface and basic structure
            
            print(f"StyleTTS2 inference:")
            print(f"  text: {text[:100]}...")
            print(f"  output: {output_wav_file}")
            print(f"  target_voice: {target_voice_path}")
            print(f"  alpha: {alpha}, beta: {beta}, steps: {diffusion_steps}")
            
            # TODO: Implement full inference pipeline:
            # 1. Phonemize text
            # 2. Extract style from reference (if provided)
            # 3. Run through text encoder, style encoder
            # 4. Generate audio with diffusion sampler
            # 5. Save to output_wav_file
            
            # Placeholder: Generate silence as fallback
            # In production, replace with actual synthesis
            sample_rate = 24000
            duration = max(1.0, len(text) * 0.1)
            samples = int(sample_rate * duration)
            audio_tensor = torch.zeros(1, samples)
            torchaudio.save(output_wav_file, audio_tensor, sample_rate)
            
            print(f"Generated audio saved to {output_wav_file}")
            print("Note: This is a placeholder implementation. Full inference pipeline needs to be implemented.")
            
        except Exception as e:
            print(f"Error during inference: {e}")
            import traceback
            traceback.print_exc()
            raise

# Export StyleTTS2 class
__all__ = ['StyleTTS2']
