import json
import os
import random
import platform
from loguru import logger
from typing import Dict, Any, Optional

class FingerprintManager:
    def __init__(self, driver=None):
        self.driver = driver
        self.fingerprints_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "src", "fingerprint", "fingerprints"
        )
        os.makedirs(self.fingerprints_dir, exist_ok=True)
        
        # 基础指纹模板 (增强型)
        self.template = {
            "navigator": {
                "userAgent": "",
                "platform": "Win32" if platform.system() == "Windows" else "MacIntel" if platform.system() == "Darwin" else "Linux x86_64",
                "language": "en-US",
                "languages": ["en-US", "en"],
                "hardwareConcurrency": 8,
                "deviceMemory": 8,
                "webdriver": False,
                "vendor": "Google Inc.",
                "maxTouchPoints": 0,
                "doNotTrack": "1"
            },
            "screen": {
                "width": 1920,
                "height": 1080,
                "availWidth": 1920,
                "availHeight": 1040,
                "colorDepth": 24,
                "pixelDepth": 24
            },
            "webgl": {
                "unmaskedVendor": "Google Inc.",
                "unmaskedRenderer": "ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0, D3D11)"
            },
            "battery": {
                "charging": True,
                "chargingTime": 0,
                "dischargingTime": float('inf'),
                "level": 1.0
            },
            "mediaDevices": [
                {"kind": "audioinput", "label": "Internal Microphone", "deviceId": "default"},
                {"kind": "videoinput", "label": "Internal Camera", "deviceId": "default"},
                {"kind": "audiooutput", "label": "Internal Speaker", "deviceId": "default"}
            ],
            "webrtc": "disable", # disable, block, reveal
            "timezone": "America/New_York",
            "fonts": [
                "Arial", "Arial Black", "Arial Unicode MS", "Calibri", "Cambria",
                "Cambria Math", "Comic Sans MS", "Courier", "Courier New", "Georgia",
                "Helvetica", "Impact", "Times", "Times New Roman", "Trebuchet MS", "Verdana"
            ]
        }
        
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ]

    def create_fingerprint(self, name: str) -> Dict[str, Any]:
        """创建商业级指纹配置"""
        fingerprint = self.template.copy()
        
        # 随机化
        fingerprint["navigator"]["userAgent"] = random.choice(self.user_agents)
        fingerprint["navigator"]["hardwareConcurrency"] = random.choice([4, 6, 8, 12, 16])
        fingerprint["navigator"]["deviceMemory"] = random.choice([4, 8, 16, 32])
        
        # 电池随机化
        fingerprint["battery"]["level"] = round(random.uniform(0.1, 1.0), 2)
        fingerprint["battery"]["charging"] = random.choice([True, False])

        # 屏幕分辨率随机化
        resolutions = [(1920, 1080), (2560, 1440), (1440, 900), (1366, 768)]
        w, h = random.choice(resolutions)
        fingerprint["screen"].update({"width": w, "height": h, "availWidth": w, "availHeight": h - 40})
        
        self.save_fingerprint(name, fingerprint)
        return fingerprint

    def save_fingerprint(self, name: str, fingerprint: Dict[str, Any]):
        filepath = os.path.join(self.fingerprints_dir, f"{name}.json")
        with open(filepath, "w") as f:
            json.dump(fingerprint, f, indent=4)

    def load_fingerprint(self, name: str) -> Dict[str, Any]:
        filepath = os.path.join(self.fingerprints_dir, f"{name}.json")
        try:
            with open(filepath, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            return self.create_fingerprint(name)

    def get_injection_script(self, fingerprint: Dict[str, Any]) -> str:
        nav = fingerprint.get('navigator', {})
        screen = fingerprint.get('screen', {})
        webgl = fingerprint.get('webgl', {})
        battery = fingerprint.get('battery', {})
        media_devices = fingerprint.get('mediaDevices', [])

        return f"""
        (function() {{
            // 1. Navigator Spoofing
            const nav_props = {{
                userAgent: {json.dumps(nav.get('userAgent'))},
                platform: {json.dumps(nav.get('platform'))},
                hardwareConcurrency: {nav.get('hardwareConcurrency')},
                deviceMemory: {nav.get('deviceMemory')},
                maxTouchPoints: {nav.get('maxTouchPoints')},
                doNotTrack: {json.dumps(nav.get('doNotTrack'))},
                webdriver: false,
                language: {json.dumps(nav.get('language'))},
                languages: {json.dumps(nav.get('languages'))}
            }};
            
            for (let [key, value] of Object.entries(nav_props)) {{
                Object.defineProperty(navigator, key, {{ get: () => value }});
            }}

            // 2. Screen Spoofing
            const screen_props = {{
                width: {screen.get('width')},
                height: {screen.get('height')},
                availWidth: {screen.get('availWidth')},
                availHeight: {screen.get('availHeight')},
                colorDepth: {screen.get('colorDepth')},
                pixelDepth: {screen.get('pixelDepth')}
            }};
            for (let [key, value] of Object.entries(screen_props)) {{
                Object.defineProperty(window.screen, key, {{ get: () => value }});
            }}

            // 3. WebGL Spoofing
            const getParameterProxyHandler = {{
                apply: function(target, thisArg, args) {{
                    const param = args[0];
                    if (param === 37445) return {json.dumps(webgl.get('unmaskedVendor'))};
                    if (param === 37446) return {json.dumps(webgl.get('unmaskedRenderer'))};
                    return target.apply(thisArg, args);
                }}
            }};
            if (window.WebGLRenderingContext) {{
                WebGLRenderingContext.prototype.getParameter = new Proxy(WebGLRenderingContext.prototype.getParameter, getParameterProxyHandler);
            }}

            // 4. Battery Status Spoofing
            if (navigator.getBattery) {{
                const originalGetBattery = navigator.getBattery;
                navigator.getBattery = function() {{
                    return Promise.resolve({{
                        charging: {str(battery.get('charging')).lower()},
                        chargingTime: {battery.get('chargingTime')},
                        dischargingTime: {battery.get('dischargingTime')},
                        level: {battery.get('level')},
                        addEventListener: () => {{}}
                    }});
                }};
            }}

            // 5. Media Devices Spoofing
            if (navigator.mediaDevices && navigator.mediaDevices.enumerateDevices) {{
                const originalEnumerateDevices = navigator.mediaDevices.enumerateDevices;
                navigator.mediaDevices.enumerateDevices = function() {{
                    return Promise.resolve({json.dumps(media_devices)});
                }};
            }}

            // 6. WebRTC Protection
            if ({json.dumps(fingerprint.get('webrtc'))} === 'disable') {{
                window.RTCPeerConnection = function() {{ throw new Error('WebRTC Disabled'); }};
            }}

            // 7. Timezone Spoofing
            const timezone = {json.dumps(fingerprint.get('timezone', 'UTC'))};
            const originalDateTimeFormat = Intl.DateTimeFormat;
            Intl.DateTimeFormat = function(locale, options) {{
                if (options && !options.timeZone) options.timeZone = timezone;
                return new originalDateTimeFormat(locale, options);
            }};

            // 8. Canvas Poisoning (Subtle)
            const originalToDataURL = HTMLCanvasElement.prototype.toDataURL;
            HTMLCanvasElement.prototype.toDataURL = function(type) {{
                // Add a small amount of noise
                const ctx = this.getContext('2d');
                if (ctx) {{
                    const imageData = ctx.getImageData(0, 0, 1, 1);
                    imageData.data[0] = (imageData.data[0] + 1) % 256;
                    ctx.putImageData(imageData, 0, 0);
                }}
                return originalToDataURL.apply(this, arguments);
            }};
        }})();
        """
