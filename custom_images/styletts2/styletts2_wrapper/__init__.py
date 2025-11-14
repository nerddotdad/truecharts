# styletts2 package - wrapper for StyleTTS2 repository
import sys
import types

# Try to import tts module
try:
    from . import tts
except Exception as e:
    # If import fails, create a minimal tts module that will fail gracefully
    import traceback
    error_msg = str(e)
    error_trace = traceback.format_exc()
    
    # Create a dummy tts module
    tts = types.ModuleType('styletts2.tts')
    tts.__error__ = error_msg
    tts.__traceback__ = error_trace
    
    # Make StyleTTS2 raise an informative error when accessed
    class _ErrorClass:
        def __call__(self, *args, **kwargs):
            raise ImportError(
                f"Failed to import styletts2.tts module. Original error: {error_msg}\n"
                f"Traceback: {error_trace}"
            )
        def __getattr__(self, name):
            raise ImportError(
                f"Failed to import styletts2.tts module. Original error: {error_msg}\n"
                f"Traceback: {error_trace}"
            )
    
    tts.StyleTTS2 = _ErrorClass()
    sys.modules['styletts2.tts'] = tts

__all__ = ['tts']

