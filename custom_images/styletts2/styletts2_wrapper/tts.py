"""
styletts2.tts module
Imports StyleTTS2 class from StyleTTS2 repository (lazy-loaded)
"""
import sys
import os
import importlib.util

# Add repository to Python path
repo_path = '/app/StyleTTS2'
if repo_path not in sys.path:
    sys.path.insert(0, repo_path)

# Lazy-load StyleTTS2 - only search when accessed
_StyleTTS2_class = None
_import_error = None
_found_file = None

def _load_styletts2():
    """Lazy-load the StyleTTS2 class from the repository"""
    global _StyleTTS2_class, _import_error, _found_file
    
    if _StyleTTS2_class is not None:
        return _StyleTTS2_class
    if _import_error is not None:
        raise ImportError(_import_error)
    
    # Strategy 1: Search for Python files containing StyleTTS2 class
    python_files = []
    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['__pycache__', 'node_modules']]
        for file in files:
            if file.endswith('.py') and not file.startswith('_'):
                python_files.append(os.path.join(root, file))
    
    # Prioritize files with common names
    priority_files = [f for f in python_files if any(name in f.lower() for name in ['inference', 'tts', 'style', 'model'])]
    other_files = [f for f in python_files if f not in priority_files]
    search_order = priority_files + other_files
    
    for py_file in search_order:
        try:
            unique_name = f"_styletts2_search_{hash(py_file)}"
            spec = importlib.util.spec_from_file_location(unique_name, py_file)
            if spec is None or spec.loader is None:
                continue
            
            module = importlib.util.module_from_spec(spec)
            try:
                spec.loader.exec_module(module)
            except Exception:
                continue
            
            if hasattr(module, 'StyleTTS2'):
                _StyleTTS2_class = getattr(module, 'StyleTTS2')
                _found_file = py_file
                break
        except Exception:
            continue
    
    # Strategy 2: Try common import patterns
    if _StyleTTS2_class is None:
        common_modules = ['inference', 'Models.inference', 'Utils.inference']
        for module_name in common_modules:
            try:
                mod = __import__(module_name, fromlist=['StyleTTS2'])
                if hasattr(mod, 'StyleTTS2'):
                    _StyleTTS2_class = getattr(mod, 'StyleTTS2')
                    _found_file = f"module: {module_name}"
                    break
            except (ImportError, Exception):
                continue
    
    # Strategy 3: Try inference.py directly
    if _StyleTTS2_class is None:
        inference_path = os.path.join(repo_path, 'inference.py')
        if os.path.exists(inference_path):
            try:
                spec = importlib.util.spec_from_file_location("inference", inference_path)
                inference_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(inference_module)
                _StyleTTS2_class = getattr(inference_module, 'StyleTTS2', None)
                if _StyleTTS2_class:
                    _found_file = inference_path
            except Exception:
                pass
    
    if _StyleTTS2_class is None:
        _import_error = (
            f"Could not import StyleTTS2 from StyleTTS2 repository at {repo_path}. "
            f"Searched {len(python_files)} Python files. "
            f"Repository contents: {os.listdir(repo_path)[:10] if os.path.exists(repo_path) else 'not found'}"
        )
        raise ImportError(_import_error)
    
    return _StyleTTS2_class

# Create a class proxy that lazy-loads StyleTTS2
class _StyleTTS2Proxy:
    """Proxy class that lazy-loads StyleTTS2 when instantiated or accessed"""
    def __call__(self, *args, **kwargs):
        # When called like StyleTTS2(), instantiate the actual class
        cls = _load_styletts2()
        return cls(*args, **kwargs)
    
    def __getattr__(self, name):
        # When accessing attributes, get them from the actual class
        cls = _load_styletts2()
        return getattr(cls, name)
    
    def __repr__(self):
        try:
            cls = _load_styletts2()
            return f"<class 'styletts2.tts.StyleTTS2' from {_found_file}>"
        except:
            return "<class 'styletts2.tts.StyleTTS2' (not loaded)>"
    
    def __instancecheck__(self, instance):
        cls = _load_styletts2()
        return isinstance(instance, cls)
    
    def __subclasscheck__(self, subclass):
        cls = _load_styletts2()
        return issubclass(subclass, cls)

# Export StyleTTS2 as a proxy that lazy-loads
# This allows: from styletts2 import tts; model = tts.StyleTTS2()
StyleTTS2 = _StyleTTS2Proxy()

__all__ = ['StyleTTS2']

