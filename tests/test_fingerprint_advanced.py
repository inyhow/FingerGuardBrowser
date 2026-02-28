import json
from src.fingerprint.fingerprint_manager import FingerprintManager

def test_fingerprint_template_content():
    manager = FingerprintManager()
    template = manager.template

    assert "battery" in template
    assert "mediaDevices" in template
    assert "navigator" in template
    assert "screen" in template
    assert template["navigator"]["hardwareConcurrency"] == 8

def test_get_injection_script_contains_new_attributes():
    manager = FingerprintManager()
    fingerprint = manager.template
    script = manager.get_injection_script(fingerprint)

    assert "navigator.getBattery" in script
    assert "navigator.mediaDevices.enumerateDevices" in script
    assert "Intl.DateTimeFormat" in script
    assert "HTMLCanvasElement.prototype.toDataURL" in script
    # Verify json.dumps was used by checking for quoted values from template
    assert '"Internal Microphone"' in script
