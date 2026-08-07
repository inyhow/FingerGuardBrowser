import json
import os
import sys
from src.fingerprint.fingerprint_manager import FingerprintManager

def test_fingerprint_template_content():
    manager = FingerprintManager()
    template = manager.template if hasattr(manager, 'template') else manager.os_profiles

    assert "windows" in manager.os_profiles
    assert "macos" in manager.os_profiles
    assert "linux" in manager.os_profiles

def test_create_fingerprint_generates_all_vectors():
    manager = FingerprintManager()
    fp = manager.create_fingerprint("test_profile_1")

    # Core vectors
    assert "navigator" in fp
    assert "screen" in fp
    assert "webgl" in fp
    assert "battery" in fp
    assert "mediaDevices" in fp
    assert "timezone" in fp
    assert "fonts" in fp

    # New vectors
    assert "clientHints" in fp, "ClientHints (Sec-CH-UA) must be present"
    assert "audioContext" in fp, "AudioContext config must be present"
    assert "canvas" in fp, "Canvas noise config must be present"
    assert "geolocation" in fp, "Geolocation spoofing data must be present"
    assert "speechSynthesis" in fp, "Speech synthesis config must be present"
    assert "performance" in fp, "Performance API config must be present"

    # Seed for deterministic noise
    assert "seed" in fp, "Fingerprint must have a deterministic seed"
    assert "os_type" in fp, "Fingerprint must specify OS type"

def test_user_agents_are_current():
    """User agents should be Chrome 125+ (not 119/120 which are 2+ years old)."""
    manager = FingerprintManager()
    for ua_entry in manager.user_agents:
        version = int(ua_entry["chromeVersion"])
        assert version >= 125, f"UA version {version} is outdated — minimum is Chrome 125"

def test_fingerprint_cross_vector_consistency():
    """UA platform should match navigator.platform and clientHints.platform."""
    manager = FingerprintManager()

    # Windows fingerprint
    fp = manager.create_fingerprint("test_windows", os_type="windows")
    assert fp["navigator"]["platform"] == "Win32"
    assert fp["clientHints"]["platform"] == "Windows"
    assert "Windows" in fp["navigator"]["userAgent"]

    # macOS fingerprint
    fp = manager.create_fingerprint("test_macos", os_type="macos")
    assert fp["navigator"]["platform"] == "MacIntel"
    assert fp["clientHints"]["platform"] == "macOS"
    assert "Macintosh" in fp["navigator"]["userAgent"]

    # Linux fingerprint
    fp = manager.create_fingerprint("test_linux", os_type="linux")
    assert fp["navigator"]["platform"] == "Linux x86_64"
    assert fp["clientHints"]["platform"] == "Linux"
    assert "Linux" in fp["navigator"]["userAgent"]

def test_timezone_locale_consistency():
    """Timezone and locale should be a consistent pair."""
    manager = FingerprintManager()
    fp = manager.create_fingerprint("test_tz_locale")
    tz = fp["timezone"]
    locale = fp["locale"]

    tz_locale_map = manager.timezone_locale_map
    if tz in tz_locale_map:
        assert locale == tz_locale_map[tz], f"Timezone {tz} should map to locale {tz_locale_map[tz]}, got {locale}"

def test_injection_script_contains_all_vectors():
    manager = FingerprintManager()
    fp = manager.create_fingerprint("test_injection")
    script = manager.get_injection_script(fp)

    # Original vectors
    assert "navigator.getBattery" in script, "Battery spoofing missing"
    assert "navigator.mediaDevices.enumerateDevices" in script, "MediaDevices spoofing missing"
    assert "Intl.DateTimeFormat" in script, "Timezone spoofing missing"
    assert "HTMLCanvasElement.prototype.toDataURL" in script, "Canvas spoofing missing"
    assert "WebGLRenderingContext" in script, "WebGL spoofing missing"

    # New vectors
    assert "AnalyserNode" in script, "AudioContext fingerprint protection missing"
    assert "userAgentData" in script, "ClientHints/userAgentData spoofing missing"
    assert "getTimezoneOffset" in script, "Complete timezone spoofing (getTimezoneOffset) missing"
    assert "resolvedOptions" in script, "Complete timezone spoofing (resolvedOptions) missing"
    assert "getImageData" in script, "Canvas getImageData interception missing"
    assert "toBlob" in script, "Canvas toBlob interception missing"
    assert "geolocation" in script.lower(), "Geolocation spoofing missing"
    assert "speechSynthesis" in script, "Speech synthesis spoofing missing"
    assert "performance.memory" in script or "performance" in script, "Performance API protection missing"
    assert "fonts.check" in script, "Font enumeration protection missing"

def test_injection_script_webrtc_not_disabled():
    """WebRTC should use filtering, not disabling (disabling is a fingerprint signal)."""
    manager = FingerprintManager()
    fp = manager.create_fingerprint("test_webrtc")
    script = manager.get_injection_script(fp)

    # Should NOT throw error (old behavior)
    assert "throw new Error('WebRTC Disabled')" not in script, "WebRTC should not be disabled by throwing"
    # Should use controlled ICE candidate filtering
    assert "iceTransportPolicy" in script or "icecandidate" in script, "WebRTC ICE filtering missing"

def test_injection_script_canvas_uses_seed():
    """Canvas noise should use a deterministic seed, not trivial single-pixel modification."""
    manager = FingerprintManager()
    fp = manager.create_fingerprint("test_canvas_seed")
    script = manager.get_injection_script(fp)

    assert "mulberry32" in script, "Canvas noise should use seeded PRNG"
    assert "canvasRng" in script, "Canvas noise should use seeded random generator"
    # Should NOT use the old trivial single-pixel approach
    assert "imageData.data[0] = (imageData.data[0] + 1) % 256" not in script, "Old trivial canvas poisoning detected"

def test_deterministic_fingerprint_same_seed():
    """Same profile name should produce same fingerprint seed."""
    manager = FingerprintManager()
    fp1 = manager.create_fingerprint("deterministic_test")
    fp2 = manager.create_fingerprint("deterministic_test")
    assert fp1["seed"] == fp2["seed"], "Same name should produce same seed"

def test_clienthints_data_structure():
    """ClientHints should have proper structure with brands, mobile, platform."""
    manager = FingerprintManager()
    fp = manager.create_fingerprint("test_ch")
    ch = fp["clientHints"]

    assert "brands" in ch
    assert "mobile" in ch
    assert "platform" in ch
    assert "platformVersion" in ch
    assert "architecture" in ch
    assert "bitness" in ch
    assert "uaFullVersion" in ch
    assert isinstance(ch["brands"], list)
    assert len(ch["brands"]) >= 2

def test_injection_script_removes_automation_signals():
    """Injection script should remove cdc_ and webdriver automation signals."""
    manager = FingerprintManager()
    fp = manager.create_fingerprint("test_automation")
    script = manager.get_injection_script(fp)

    assert "cdc_" in script, "Automation signal removal (cdc_) missing"
    assert "webdriver" in script, "Webdriver flag override missing"

def test_injection_script_json_safety():
    """Injection script should use json.dumps for all string values to prevent injection."""
    manager = FingerprintManager()
    fp = manager.create_fingerprint("test_json_safety")
    script = manager.get_injection_script(fp)

    # The script should contain JSON-serialized data
    assert "FP_DATA" in script, "FP_DATA object should be present"
    assert "json.dumps" not in script, "json.dumps calls should be resolved at generation time"
