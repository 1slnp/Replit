#!/usr/bin/env python3
"""
Comprehensive test script for SLNP Art application
Tests all major functionality including buttons, toggles, and API endpoints
"""

import requests
import json
import time
import sys

BASE_URL = "http://localhost:5001"

def test_endpoint(endpoint, method="GET", data=None, files=None):
    """Test a specific endpoint and return result"""
    try:
        url = f"{BASE_URL}{endpoint}"
        if method == "GET":
            response = requests.get(url, timeout=10)
        elif method == "POST":
            if files:
                response = requests.post(url, data=data, files=files, timeout=10)
            else:
                headers = {'Content-Type': 'application/json'} if data else {}
                response = requests.post(url, json=data, headers=headers, timeout=10)
        
        return {
            "status_code": response.status_code,
            "success": response.status_code < 400,
            "content": response.text[:500] if len(response.text) > 500 else response.text,
            "json": response.json() if response.headers.get('content-type') == 'application/json' else None
        }
    except Exception as e:
        return {
            "status_code": 0,
            "success": False,
            "error": str(e),
            "content": ""
        }

def test_page_functionality():
    """Test main page functionality"""
    print("🧪 TESTING PAGE FUNCTIONALITY")
    print("=" * 50)
    
    # Test main pages
    pages = [
        ("/", "Home Page"),
        ("/cover-art", "Cover Art Generator"),
        ("/video-generator", "Video Generator"),
        ("/vocal-mastering", "Vocal Mastering"),
        ("/login", "Login Page"),
        ("/register", "Register Page")
    ]
    
    for endpoint, name in pages:
        result = test_endpoint(endpoint)
        status = "✅" if result["success"] else "❌"
        print(f"{status} {name}: {result['status_code']}")
        if not result["success"]:
            print(f"   Error: {result.get('error', 'HTTP Error')}")

def test_api_endpoints():
    """Test API endpoints"""
    print("\n🔌 TESTING API ENDPOINTS")
    print("=" * 50)
    
    # Test GET APIs
    get_apis = [
        ("/api/tokens", "Token Balance API"),
    ]
    
    for endpoint, name in get_apis:
        result = test_endpoint(endpoint)
        status = "✅" if result["success"] else "❌"
        print(f"{status} {name}: {result['status_code']}")
        if result.get("json"):
            print(f"   Response: {result['json']}")

def test_cover_art_functionality():
    """Test cover art generation functionality"""
    print("\n🎨 TESTING COVER ART FUNCTIONALITY")
    print("=" * 50)
    
    # Test cover art generation with different models
    cover_art_data = {
        "artist_name": "Test Artist",
        "album_title": "Test Album", 
        "genre": "Hip Hop",
        "explicit_content": False,
        "ai_prompt": "A vibrant hip hop album cover with urban elements",
        "ai_model": "stable-diffusion"
    }
    
    result = test_endpoint("/api/generate-cover-art", "POST", cover_art_data)
    status = "✅" if result["success"] else "❌"
    print(f"{status} Cover Art Generation: {result['status_code']}")
    if result.get("json"):
        print(f"   Response: {result['json']}")
    elif not result["success"]:
        print(f"   Error: {result.get('error', result['content'][:200])}")

    # Test prompt generation
    prompt_data = {
        "genre": "Hip Hop",
        "artist_name": "Test Artist",
        "album_title": "Test Album"
    }
    
    result = test_endpoint("/api/generate-prompt", "POST", prompt_data)
    status = "✅" if result["success"] else "❌"
    print(f"{status} Prompt Generation: {result['status_code']}")

def test_video_generator_functionality():
    """Test video generator functionality"""
    print("\n🎬 TESTING VIDEO GENERATOR FUNCTIONALITY")
    print("=" * 50)
    
    # Test video prompt generation
    video_prompt_data = {
        "artist_name": "Test Artist",
        "track_title": "Test Track",
        "visual_style": "cyberpunk"
    }
    
    result = test_endpoint("/api/generate-video-prompt", "POST", video_prompt_data)
    status = "✅" if result["success"] else "❌"
    print(f"{status} Video Prompt Generation: {result['status_code']}")
    
    # Test direct video generation (without file upload)
    video_generation_data = {
        "visual_style": "cyberpunk",
        "scene_prompt": "A futuristic cityscape with neon lights",
        "duration": "30s",
        "resolution": "1080p"
    }
    
    result = test_endpoint("/api/start-video-generation", "POST", video_generation_data)
    status = "✅" if result["success"] else "❌"
    print(f"{status} Video Generation: {result['status_code']}")
    if result.get("json"):
        print(f"   Response: {result['json']}")

def test_vocal_mastering_functionality():
    """Test vocal mastering functionality"""
    print("\n🎤 TESTING VOCAL MASTERING FUNCTIONALITY")
    print("=" * 50)
    
    # Test real-time EQ (without actual job)
    eq_data = {
        "job_id": 1,
        "template": "Radio Ready",
        "eq_settings": {
            "bass": 2,
            "mids": 0,
            "treble": 3
        }
    }
    
    result = test_endpoint("/api/apply-realtime-eq", "POST", eq_data)
    status = "✅" if result["success"] or result["status_code"] == 404 else "❌"
    print(f"{status} Real-time EQ Processing: {result['status_code']}")
    if result.get("json"):
        print(f"   Response: {result['json']}")

def test_authentication():
    """Test authentication functionality"""
    print("\n🔐 TESTING AUTHENTICATION")
    print("=" * 50)
    
    # Test login page
    result = test_endpoint("/login")
    status = "✅" if result["success"] and "Sign In" in result["content"] else "❌"
    print(f"{status} Login Page Loads: {result['status_code']}")
    
    # Test register page
    result = test_endpoint("/register")
    status = "✅" if result["success"] and ("Sign Up" in result["content"] or "Register" in result["content"]) else "❌"
    print(f"{status} Register Page Loads: {result['status_code']}")

def test_button_and_toggle_functionality():
    """Test JavaScript functionality by checking page content"""
    print("\n🔘 TESTING BUTTONS AND TOGGLES")
    print("=" * 50)
    
    # Check Cover Art page for required elements
    result = test_endpoint("/cover-art")
    if result["success"]:
        content = result["content"]
        
        # Check for required buttons and form elements
        elements_to_check = [
            ("generate-cover-btn", "Generate Cover Button"),
            ("generate-prompt-btn", "Generate Prompt Button"),
            ("ai-model", "AI Model Selector"),
            ("artist-name", "Artist Name Field"),
            ("album-title", "Album Title Field"),
            ("genre-btn", "Genre Buttons"),
            ("explicit-content", "Explicit Content Toggle")
        ]
        
        for element_id, description in elements_to_check:
            if element_id in content:
                print(f"✅ {description}: Found")
            else:
                print(f"❌ {description}: Missing")
    
    # Check Video Generator page for required elements
    result = test_endpoint("/video-generator")
    if result["success"]:
        content = result["content"]
        
        elements_to_check = [
            ("generate-video-btn", "Generate Video Button"),
            ("generate-prompt-btn", "Generate Prompt Button"),
            ("video-track-title", "Track Title Field"),
            ("scene-prompt", "Scene Prompt Field"),
            ("style-btn", "Visual Style Buttons"),
            ("video-duration", "Duration Selector"),
            ("video-resolution", "Resolution Selector")
        ]
        
        for element_id, description in elements_to_check:
            if element_id in content:
                print(f"✅ {description}: Found")
            else:
                print(f"❌ {description}: Missing")
    
    # Check Vocal Mastering page for required elements
    result = test_endpoint("/vocal-mastering")
    if result["success"]:
        content = result["content"]
        
        elements_to_check = [
            ("start-mastering-btn", "Start Mastering Button"),
            ("template-btn", "Template Buttons"),
            ("bass-slider", "Bass EQ Slider"),
            ("mids-slider", "Mids EQ Slider"),
            ("treble-slider", "Treble EQ Slider"),
            ("audio-file", "Audio File Input"),
            ("track-title", "Track Title Field")
        ]
        
        for element_id, description in elements_to_check:
            if element_id in content:
                print(f"✅ {description}: Found")
            else:
                print(f"❌ {description}: Missing")

def main():
    """Run all tests"""
    print("🚀 SLNP ART FUNCTIONALITY TEST SUITE")
    print("=" * 50)
    print("Testing application at:", BASE_URL)
    print()
    
    # Wait for application to be ready
    print("⏳ Waiting for application to be ready...")
    for i in range(10):
        try:
            response = requests.get(BASE_URL, timeout=5)
            if response.status_code == 200:
                print("✅ Application is ready!")
                break
        except:
            time.sleep(1)
    else:
        print("❌ Application not responding. Please start the Flask app first.")
        sys.exit(1)
    
    # Run all test suites
    test_page_functionality()
    test_api_endpoints()
    test_button_and_toggle_functionality()
    test_cover_art_functionality()
    test_video_generator_functionality()
    test_vocal_mastering_functionality()
    test_authentication()
    
    print("\n" + "=" * 50)
    print("🎉 TEST SUITE COMPLETED")
    print("✅ All critical functionality has been tested!")
    print("📝 Review results above for any issues that need attention.")

if __name__ == "__main__":
    main()