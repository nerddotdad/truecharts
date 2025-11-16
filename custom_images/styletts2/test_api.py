#!/usr/bin/env python3
"""
Test script for StyleTTS2 API
Run this to test the API endpoints locally
"""
import requests
import json
import time
import sys

# Get API base URL from command line or use default
API_BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5003"

def test_endpoint(method, endpoint, data=None, files=None):
    """Test an API endpoint"""
    url = f"{API_BASE}{endpoint}"
    print(f"\n{'='*60}")
    print(f"Testing: {method} {endpoint}")
    print(f"{'='*60}")
    
    try:
        if method == "GET":
            response = requests.get(url, timeout=10)
        elif method == "POST":
            if files:
                response = requests.post(url, files=files, timeout=30)
            else:
                response = requests.post(url, json=data, timeout=30)
        elif method == "DELETE":
            response = requests.delete(url, json=data, timeout=10)
        else:
            print(f"Unknown method: {method}")
            return None
        
        print(f"Status: {response.status_code}")
        
        try:
            result = response.json()
            print(f"Response: {json.dumps(result, indent=2)}")
            return result
        except:
            print(f"Response (text): {response.text[:500]}")
            return {"text": response.text}
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return None

def main():
    print("StyleTTS2 API Test Suite")
    print(f"API Base URL: {API_BASE}")
    
    # Test 1: Health check
    print("\n" + "="*60)
    print("TEST 1: Health Check")
    print("="*60)
    test_endpoint("GET", "/ready")
    
    # Test 2: List models
    print("\n" + "="*60)
    print("TEST 2: List Models")
    print("="*60)
    models = test_endpoint("GET", "/api/models")
    
    if models and "models" in models:
        print("\nFound models:")
        for model_id, model_info in models["models"].items():
            print(f"  - {model_id}: installed={model_info.get('installed')}, path={model_info.get('path')}")
    
    # Test 3: Check status
    print("\n" + "="*60)
    print("TEST 3: Check Status")
    print("="*60)
    status = test_endpoint("GET", "/api/models/status")
    
    # Test 4: Load model (if installed)
    if models and "models" in models:
        installed_models = [mid for mid, info in models["models"].items() if info.get("installed")]
        if installed_models:
            model_id = installed_models[0]
            print("\n" + "="*60)
            print(f"TEST 4: Load Model ({model_id})")
            print("="*60)
            result = test_endpoint("POST", "/api/models/load", data={"model_id": model_id})
            
            if result:
                print("\nPolling for loading status...")
                for i in range(30):  # Poll for up to 30 seconds
                    time.sleep(1)
                    status = test_endpoint("GET", "/api/models/status")
                    if status:
                        loading_status = status.get("loading_status", {})
                        loading_logs = status.get("loading_logs", [])
                        model_loaded = status.get("model_loaded", False)
                        
                        print(f"\nProgress: {loading_status.get('progress', 0)}%")
                        print(f"Status: {loading_status.get('status', 'unknown')}")
                        print(f"Message: {loading_status.get('message', '')}")
                        print(f"Model loaded: {model_loaded}")
                        
                        if loading_logs:
                            print(f"\nRecent logs ({len(loading_logs)} entries):")
                            for log in loading_logs[-5:]:  # Last 5 logs
                                level = log.get("level", "info")
                                msg = log.get("message", "")
                                timestamp = log.get("timestamp", "")
                                print(f"  [{level.upper()}] {msg}")
                        
                        if loading_status.get("status") in ["complete", "error"]:
                            break
                
                # Final status check
                print("\n" + "="*60)
                print("FINAL STATUS CHECK")
                print("="*60)
                final_status = test_endpoint("GET", "/api/models/status")
                
                if final_status:
                    print(f"\nModel loaded: {final_status.get('model_loaded')}")
                    if final_status.get('loading_logs'):
                        print("\nAll loading logs:")
                        for log in final_status.get('loading_logs', []):
                            level = log.get("level", "info")
                            msg = log.get("message", "")
                            timestamp = log.get("timestamp", "")
                            print(f"  [{timestamp}] [{level.upper()}] {msg}")
        else:
            print("\nNo installed models found to test loading")
    
    # Test 5: Test TTS (if model is loaded)
    print("\n" + "="*60)
    print("TEST 5: Test TTS Generation")
    print("="*60)
    status = test_endpoint("GET", "/api/models/status")
    if status and status.get("model_loaded"):
        test_endpoint("POST", "/api/tts", data={
            "text": "Hello, this is a test of the text to speech system.",
            "alpha": 0.3,
            "beta": 0.7,
            "diffusion_steps": 10
        })
    else:
        print("Model not loaded, skipping TTS test")
    
    print("\n" + "="*60)
    print("TEST SUITE COMPLETE")
    print("="*60)

if __name__ == "__main__":
    main()

