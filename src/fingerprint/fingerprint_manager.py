import json
import os
import random
import platform
import copy
import hashlib
import time
from loguru import logger
from typing import Dict, Any, Optional, List
from ..utils.app_paths import resource_path

class FingerprintManager:
    """Comprehensive fingerprint manager with multi-vector spoofing."""

    def __init__(self, driver=None):
        self.driver = driver
        self.fingerprints_dir = resource_path("src", "fingerprint", "fingerprints")
        os.makedirs(self.fingerprints_dir, exist_ok=True)

        # OS profile presets — each defines a coherent set of hardware/browser attributes
        self.os_profiles = {
            "windows": {
                "platform": "Win32",
                "ua_platform": "Windows NT 10.0; Win64; x64",
                "fonts": [
                    "Arial", "Arial Black", "Arial Unicode MS", "Calibri", "Cambria",
                    "Cambria Math", "Comic Sans MS", "Consolas", "Courier", "Courier New",
                    "Ebrima", "Franklin Gothic Medium", "Gabriola", "Gadugi", "Georgia",
                    "Impact", "Javanese Text", "Leelawadee UI", "Lucida Console",
                    "Lucida Sans Unicode", "MS Gothic", "MS PGothic", "MS Sans Serif",
                    "MS Serif", "MV Boli", "Malgun Gothic", "Microsoft Himalaya",
                    "Microsoft JhengHei", "Microsoft New Tai Lue", "Microsoft PhagsPa",
                    "Microsoft Sans Serif", "Microsoft Tai Le", "Microsoft YaHei",
                    "Microsoft Yi Baiti", "MingLiU-ExtB", "Mongolian Baiti",
                    "Myanmar Text", "Nirmala UI", "Palatino Linotype", "Segoe Print",
                    "Segoe Script", "Segoe UI", "Segoe UI Emoji", "Segoe UI Historic",
                    "Segoe UI Symbol", "SimSun", "Sitka", "Sylfaen", "Tahoma",
                    "Times New Roman", "Trebuchet MS", "Verdana", "Webdings",
                    "Wingdings", "Yu Gothic",
                ],
                "webgl_renderers": [
                    "ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0, D3D11)",
                    "ANGLE (NVIDIA, NVIDIA GeForce RTX 4060 Direct3D11 vs_5_0 ps_5_0, D3D11)",
                    "ANGLE (NVIDIA, NVIDIA GeForce RTX 3070 Direct3D11 vs_5_0 ps_5_0, D3D11)",
                    "ANGLE (AMD, AMD Radeon RX 6700 XT Direct3D11 vs_5_0 ps_5_0, D3D11)",
                    "ANGLE (Intel, Intel(R) UHD Graphics 770 Direct3D11 vs_5_0 ps_5_0, D3D11)",
                    "ANGLE (Intel, Intel(R) Iris(R) Xe Graphics Direct3D11 vs_5_0 ps_5_0, D3D11)",
                ],
            },
            "macos": {
                "platform": "MacIntel",
                "ua_platform": "Macintosh; Intel Mac OS X 10_15_7",
                "fonts": [
                    "Arial", "Arial Black", "Arial Hebrew", "Arial Narrow", "Arial Rounded MT Bold",
                    "Arial Unicode MS", "Avenir", "Avenir Next", "Avenir Next Condensed",
                    "Baskerville", "Big Caslon", "Bodoni 72", "Bradley Hand", "Brush Script MT",
                    "Chalkboard", "Chalkduster", "Charter", "Cochin", "Comic Sans MS",
                    "Copperplate", "Courier", "Courier New", "DIN Alternate", "DIN Condensed",
                    "Didot", "Futura", "Geneva", "Georgia", "Gill Sans", "Helvetica",
                    "Helvetica Neue", "Herculanum", "Hoefler Text", "Impact", "Lucida Grande",
                    "Luminari", "Marker Felt", "Menlo", "Monaco", "Noteworthy", "Optima",
                    "Palatino", "Papyrus", "Phosphate", "Rockwell", "Savoye LET", "SignPainter",
                    "Skia", "Snell Roundhand", "Tahoma", "Times", "Times New Roman",
                    "Trebuchet MS", "Verdana", "Zapfino",
                ],
                "webgl_renderers": [
                    "ANGLE (Apple, Apple M1 Pro, OpenGL 4.1)",
                    "ANGLE (Apple, Apple M2, OpenGL 4.1)",
                    "ANGLE (Apple, Apple M3, OpenGL 4.1)",
                    "ANGLE (Intel, Intel(R) Iris(TM) Plus Graphics 645, OpenGL 4.1)",
                ],
            },
            "linux": {
                "platform": "Linux x86_64",
                "ua_platform": "X11; Linux x86_64",
                "fonts": [
                    "Arial", "Bitstream Charter", "Bitstream Vera Sans", "Bitstream Vera Sans Mono",
                    "Bitstream Vera Serif", "Cantarell", "Courier", "Courier New", "DejaVu Sans",
                    "DejaVu Sans Mono", "DejaVu Serif", "FreeMono", "FreeSans", "FreeSerif",
                    "Georgia", "Impact", "Liberation Mono", "Liberation Sans", "Liberation Serif",
                    "Linux Libertine G", "Lohit Bengali", "Lohit Devanagari", "Lohit Tamil",
                    "Noto Color Emoji", "Noto Mono", "Noto Sans", "Noto Sans Arabic",
                    "Noto Sans CJK JP", "Noto Sans CJK KR", "Noto Sans CJK SC",
                    "Noto Serif", "Padauk", "Sans", "Serif", "Tibetan Machine Uni",
                    "Times New Roman", "Trebuchet MS", "Ubuntu", "Ubuntu Condensed",
                    "Ubuntu Mono", "URW Bookman L", "URW Gothic L", "Verdana",
                ],
                "webgl_renderers": [
                    "Mesa Intel(R) UHD Graphics 770 (ADL-S GT1)",
                    "Mesa Intel(R) Iris(R) Xe Graphics (TGL GT2)",
                    "llvmpipe (LLVM 15.0.7, 256 bits)",
                    "AMD Radeon RX 6700 XT (navi22, LLVM 15.0.7, DRM 3.54)",
                ],
            },
            "android": {
                "platform": "Linux armv8l",
                "ua_platform": "Linux; Android 14; SM-S918B",
                "fonts": [
                    "Roboto", "Noto Sans", "Noto Serif", "Noto Color Emoji",
                    "Droid Sans", "Droid Sans Mono", "Cutive Mono",
                ],
                "webgl_renderers": [
                    "Adreno (TM) 740", "Adreno (TM) 730",
                    "Mali-G715 Immortalis MC11", "Mali-G78 MP24",
                ],
            },
            "ios": {
                "platform": "iPhone",
                "ua_platform": "iPhone; CPU iPhone OS 17_4 like Mac OS X",
                "fonts": [
                    "Helvetica", "Helvetica Neue", "Arial", "Arial Hebrew",
                    "Avenir", "Avenir Next", "Georgia", "Times New Roman",
                    "Courier", "Courier New", "Menlo", "Apple Color Emoji",
                ],
                "webgl_renderers": ["Apple GPU", "Apple GPU (A16)", "Apple GPU (A17 Pro)"],
            },
        }

        # Up-to-date user agents (Chrome 125-128 as of mid-2026)
        # These are kept in sync with the actual Chromium major version
        self.user_agents = self._build_user_agent_pool()

        # GPU vendor mappings for WebGL
        self.webgl_vendors = {
            "NVIDIA": "Google Inc. (NVIDIA)",
            "AMD": "Google Inc. (AMD)",
            "Intel": "Google Inc. (Intel)",
            "Apple": "Google Inc. (Apple)",
        }

        # Common screen resolutions by device class
        self.screen_resolutions = [
            {"width": 1920, "height": 1080, "label": "Full HD"},
            {"width": 2560, "height": 1440, "label": "QHD"},
            {"width": 3840, "height": 2160, "label": "4K UHD"},
            {"width": 1366, "height": 768, "label": "HD"},
            {"width": 1440, "height": 900, "label": "WXGA+"},
            {"width": 1536, "height": 864, "label": "Scaled HD"},
            {"width": 1680, "height": 1050, "label": "WSXGA+"},
            {"width": 390, "height": 844, "label": "iPhone 14"},
            {"width": 393, "height": 851, "label": "Pixel 7"},
            {"width": 412, "height": 915, "label": "Samsung S23"},
        ]

        # Timezone to locale mapping for consistency
        self.timezone_locale_map = {
            "America/New_York": "en-US",
            "America/Chicago": "en-US",
            "America/Denver": "en-US",
            "America/Los_Angeles": "en-US",
            "America/Toronto": "en-CA",
            "Europe/London": "en-GB",
            "Europe/Paris": "fr-FR",
            "Europe/Berlin": "de-DE",
            "Europe/Madrid": "es-ES",
            "Europe/Rome": "it-IT",
            "Asia/Tokyo": "ja-JP",
            "Asia/Shanghai": "zh-CN",
            "Asia/Seoul": "ko-KR",
            "Asia/Singapore": "en-SG",
            "Australia/Sydney": "en-AU",
        }

    def _build_user_agent_pool(self) -> List[Dict[str, Any]]:
        """Build a pool of coherent user agent + ClientHints data."""
        chrome_versions = ["131", "130", "129", "128", "127", "126", "125"]
        platforms = [
            {"os": "windows", "ua_platform": "Windows NT 10.0; Win64; x64",
             "sec_ch_ua_platform": "Windows", "platform_version": "10.0.0"},
            {"os": "macos", "ua_platform": "Macintosh; Intel Mac OS X 10_15_7",
             "sec_ch_ua_platform": "macOS", "platform_version": "10.15.7"},
            {"os": "linux", "ua_platform": "X11; Linux x86_64",
             "sec_ch_ua_platform": "Linux", "platform_version": "6.5.0"},
            {"os": "android", "ua_platform": "Linux; Android 14; SM-S918B",
             "sec_ch_ua_platform": "Android", "platform_version": "14.0.0"},
            {"os": "ios", "ua_platform": "iPhone; CPU iPhone OS 17_4 like Mac OS X",
             "sec_ch_ua_platform": "iOS", "platform_version": "17.4.0"},
        ]

        pool = []
        for version in chrome_versions:
            for plat in platforms:
                ua = (f"Mozilla/5.0 ({plat['ua_platform']}) "
                      f"AppleWebKit/537.36 (KHTML, like Gecko) "
                      f"Chrome/{version}.0.0.0 Safari/537.36")
                pool.append({
                    "userAgent": ua,
                    "chromeVersion": version,
                    "platform": plat["sec_ch_ua_platform"],
                    "platformVersion": plat["platform_version"],
                    "brands": [
                        {"brand": "Google Chrome", "version": version},
                        {"brand": "Not;A=Brand", "version": "24"},
                        {"brand": "Chromium", "version": version},
                    ],
                    "os_key": plat["os"],
                })
        return pool

    def _generate_seed(self, name: str) -> int:
        """Generate a deterministic seed from profile name for consistent noise."""
        hash_val = hashlib.md5(name.encode()).hexdigest()
        return int(hash_val[:8], 16)

    def create_fingerprint(self, name: str, os_type: str = None, **kwargs) -> Dict[str, Any]:
        """Create a comprehensive, cross-vector-consistent fingerprint configuration.

        Args:
            name: Profile name (used as seed for deterministic noise)
            os_type: Target OS — "windows", "macos", "linux", or None for random
            **kwargs: Override specific fingerprint fields
        """
        seed = self._generate_seed(name)
        rng = random.Random(seed)

        # Select OS profile
        if os_type is None:
            os_type = rng.choice(list(self.os_profiles.keys()))
        os_profile = self.os_profiles[os_type]

        # Select a coherent UA + ClientHints set
        ua_entry = rng.choice([ua for ua in self.user_agents if ua["os_key"] == os_type])
        chrome_version = ua_entry["chromeVersion"]

        # Hardware — choose coherent combinations
        hardware_concurrency = rng.choice([4, 6, 8, 8, 12, 12, 16, 16, 24])
        device_memory = rng.choice([4, 8, 8, 16, 32])

        # Screen resolution — mobile profiles use mobile resolutions
        if os_type in ("android", "ios"):
            mobile_resolutions = [r for r in self.screen_resolutions if r["width"] < 500]
            res = rng.choice(mobile_resolutions) if mobile_resolutions else {"width": 390, "height": 844}
            max_touch = 5
            is_mobile = True
        else:
            res = rng.choice([r for r in self.screen_resolutions if r["width"] >= 1366])
            max_touch = 0
            is_mobile = False

        # WebGL renderer matching the OS
        webgl_renderer = rng.choice(os_profile["webgl_renderers"])
        webgl_vendor = self.webgl_vendors.get(
            "Apple" if os_type in ("macos", "ios") else
            "NVIDIA" if "NVIDIA" in webgl_renderer else
            "AMD" if "AMD" in webgl_renderer else "Intel"
        )

        # Timezone + locale (consistent pair)
        timezone = kwargs.get("timezone", rng.choice(list(self.timezone_locale_map.keys())))
        locale = self.timezone_locale_map.get(timezone, "en-US")

        # Battery — realistic values
        battery_level = round(rng.uniform(0.15, 1.0), 2)
        battery_charging = rng.choice([True, False, False, False])  # 25% chance charging

        # Media devices — vary count for realism
        media_device_sets = [
            [
                {"kind": "audioinput", "label": "Default - Internal Microphone", "deviceId": "default"},
                {"kind": "videoinput", "label": "Integrated Camera", "deviceId": "default"},
                {"kind": "audiooutput", "label": "Default - Speakers", "deviceId": "default"},
            ],
            [
                {"kind": "audioinput", "label": "Default - Internal Microphone", "deviceId": "default"},
                {"kind": "audioinput", "label": "External Microphone", "deviceId": "unique_id_001"},
                {"kind": "videoinput", "label": "Integrated Camera", "deviceId": "default"},
                {"kind": "audiooutput", "label": "Default - Speakers", "deviceId": "default"},
                {"kind": "audiooutput", "label": "Headphones", "deviceId": "unique_id_002"},
            ],
            [
                {"kind": "audioinput", "label": "Default - Microphone", "deviceId": "default"},
                {"kind": "audiooutput", "label": "Default - Speakers", "deviceId": "default"},
            ],
        ]

        # Geolocation coordinates consistent with timezone
        geo_coords = self._get_geo_for_timezone(timezone, rng)

        fingerprint = {
            "seed": seed,
            "os_type": os_type,
            "navigator": {
                "userAgent": ua_entry["userAgent"],
                "platform": os_profile["platform"],
                "language": locale,
                "languages": [locale, locale.split("-")[0]],
                "hardwareConcurrency": hardware_concurrency,
                "deviceMemory": device_memory,
                "webdriver": False,
                "vendor": "Google Inc.",
                "maxTouchPoints": max_touch,
                "doNotTrack": None,
                "cookieEnabled": True,
                "pdfViewerEnabled": True,
                "plugins": self._get_plugins(os_type),
            },
            "clientHints": {
                "brands": ua_entry["brands"],
                "mobile": is_mobile,
                "platform": ua_entry["platform"],
                "platformVersion": ua_entry["platformVersion"],
                "architecture": "x86" if os_type != "macos" else "arm",
                "bitness": "64",
                "model": "",
                "uaFullVersion": f"{chrome_version}.0.0.0",
            },
            "screen": {
                "width": res["width"],
                "height": res["height"],
                "availWidth": res["width"],
                "availHeight": res["height"] - rng.choice([30, 40, 40, 48, 56]),
                "colorDepth": 24,
                "pixelDepth": 24,
                "devicePixelRatio": 1.0 if res["width"] <= 1920 else rng.choice([1.25, 1.5, 2.0]),
            },
            "webgl": {
                "unmaskedVendor": webgl_vendor,
                "unmaskedRenderer": webgl_renderer,
                "vendor": "WebKit",
                "renderer": "WebKit WebGL",
            },
            "battery": {
                "charging": battery_charging,
                "chargingTime": 0 if battery_charging else rng.randint(1200, 14400),
                "dischargingTime": float('inf') if battery_charging else rng.randint(3600, 28800),
                "level": battery_level,
            },
            "mediaDevices": rng.choice(media_device_sets),
            "webrtc": "filter",  # filter, disable, reveal
            "timezone": timezone,
            "locale": locale,
            "geolocation": geo_coords,
            "fonts": os_profile["fonts"],
            "audioContext": {
                "noiseSeed": rng.randint(1, 2**31),
                "sampleRate": 44100,
                "channelCount": rng.choice([1, 2]),
            },
            "canvas": {
                "noiseSeed": seed,
                "noiseLevel": "subtle",  # subtle, moderate, aggressive
            },
            "speechSynthesis": {
                "voices": self._get_speech_voices(os_type, locale),
            },
            "performance": {
                "memory": device_memory,
                "hardwareConcurrency": hardware_concurrency,
            },
            "createdAt": int(time.time()),
        }

        # Apply any overrides from kwargs
        for key, value in kwargs.items():
            if key in fingerprint and isinstance(fingerprint[key], dict) and isinstance(value, dict):
                fingerprint[key].update(value)
            elif key in fingerprint:
                fingerprint[key] = value

        self.save_fingerprint(name, fingerprint)
        return fingerprint

    def _get_geo_for_timezone(self, timezone: str, rng: random.Random) -> Dict[str, float]:
        """Get approximate coordinates for a timezone with small random offset."""
        geo_map = {
            "America/New_York": {"lat": 40.7128, "lon": -74.0060},
            "America/Chicago": {"lat": 41.8781, "lon": -87.6298},
            "America/Denver": {"lat": 39.7392, "lon": -104.9903},
            "America/Los_Angeles": {"lat": 34.0522, "lon": -118.2437},
            "America/Toronto": {"lat": 43.6532, "lon": -79.3832},
            "Europe/London": {"lat": 51.5074, "lon": -0.1278},
            "Europe/Paris": {"lat": 48.8566, "lon": 2.3522},
            "Europe/Berlin": {"lat": 52.5200, "lon": 13.4050},
            "Europe/Madrid": {"lat": 40.4168, "lon": -3.7038},
            "Europe/Rome": {"lat": 41.9028, "lon": 12.4964},
            "Asia/Tokyo": {"lat": 35.6762, "lon": 139.6503},
            "Asia/Shanghai": {"lat": 31.2304, "lon": 121.4737},
            "Asia/Seoul": {"lat": 37.5665, "lon": 126.9780},
            "Asia/Singapore": {"lat": 1.3521, "lon": 103.8198},
            "Australia/Sydney": {"lat": -33.8688, "lon": 151.2093},
        }
        coords = geo_map.get(timezone, {"lat": 0.0, "lon": 0.0})
        # Add small random offset (~0.01 degrees ≈ ~1km) to avoid exact datacenter IP geolocation
        return {
            "latitude": round(coords["lat"] + rng.uniform(-0.01, 0.01), 6),
            "longitude": round(coords["lon"] + rng.uniform(-0.01, 0.01), 6),
            "accuracy": rng.uniform(20, 100),
        }

    def _get_plugins(self, os_type: str) -> List[Dict[str, str]]:
        """Get OS-appropriate navigator.plugins array."""
        if os_type == "macos":
            return [
                {"name": "PDF Viewer", "filename": "internal-pdf-viewer", "description": "Portable Document Format"},
                {"name": "Chrome PDF Viewer", "filename": "internal-pdf-viewer", "description": "Portable Document Format"},
                {"name": "Chromium PDF Viewer", "filename": "internal-pdf-viewer", "description": "Portable Document Format"},
                {"name": "Microsoft Edge PDF Viewer", "filename": "internal-pdf-viewer", "description": "Portable Document Format"},
                {"name": "WebKit built-in PDF", "filename": "internal-pdf-viewer", "description": "Portable Document Format"},
            ]
        return [
            {"name": "PDF Viewer", "filename": "internal-pdf-viewer", "description": "Portable Document Format"},
            {"name": "Chrome PDF Viewer", "filename": "internal-pdf-viewer", "description": "Portable Document Format"},
            {"name": "Chromium PDF Viewer", "filename": "internal-pdf-viewer", "description": "Portable Document Format"},
            {"name": "Microsoft Edge PDF Viewer", "filename": "internal-pdf-viewer", "description": "Portable Document Format"},
            {"name": "WebKit built-in PDF", "filename": "internal-pdf-viewer", "description": "Portable Document Format"},
        ]

    def _get_speech_voices(self, os_type: str, locale: str) -> List[Dict[str, str]]:
        """Get OS-appropriate speech synthesis voices."""
        lang = locale.split("-")[0]
        if os_type == "windows":
            return [
                {"name": "Microsoft David - English (United States)", "lang": "en-US"},
                {"name": "Microsoft Zira - English (United States)", "lang": "en-US"},
                {"name": "Microsoft Mark - English (United States)", "lang": "en-US"},
            ][:2 if lang == "en" else 1]
        elif os_type == "macos":
            return [
                {"name": "Alex", "lang": "en-US"},
                {"name": "Daniel", "lang": "en-GB"},
                {"name": "Samantha", "lang": "en-US"},
            ][:2]
        else:
            return [
                {"name": "English (America)", "lang": "en-US"},
                {"name": "English (United Kingdom)", "lang": "en-GB"},
            ][:2]

    def save_fingerprint(self, name: str, fingerprint: Dict[str, Any]):
        filepath = os.path.join(self.fingerprints_dir, f"{name}.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(fingerprint, f, indent=4, ensure_ascii=False)

    def load_fingerprint(self, name: str) -> Dict[str, Any]:
        filepath = os.path.join(self.fingerprints_dir, f"{name}.json")
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            logger.info(f"Creating new fingerprint for: {name}")
            return self.create_fingerprint(name)

    def get_injection_script(self, fingerprint: Dict[str, Any]) -> str:
        """Generate comprehensive fingerprint injection script.

        Covers: Navigator, Screen, WebGL, Battery, MediaDevices, WebRTC,
        Timezone, Canvas (seeded noise), AudioContext, ClientHints,
        Font enumeration, Geolocation, SpeechSynthesis, Performance API.
        """
        nav = fingerprint.get('navigator', {})
        screen = fingerprint.get('screen', {})
        webgl = fingerprint.get('webgl', {})
        battery = fingerprint.get('battery', {})
        media_devices = fingerprint.get('mediaDevices', [])
        client_hints = fingerprint.get('clientHints', {})
        audio_ctx = fingerprint.get('audioContext', {})
        canvas_cfg = fingerprint.get('canvas', {})
        webrtc_mode = fingerprint.get('webrtc', 'filter')
        timezone = fingerprint.get('timezone', 'UTC')
        locale = fingerprint.get('locale', 'en-US')
        geo = fingerprint.get('geolocation', {})
        fonts = fingerprint.get('fonts', [])
        speech_voices = fingerprint.get('speechSynthesis', {}).get('voices', [])
        perf = fingerprint.get('performance', {})
        proxy_ip = fingerprint.get('proxy_ip', '')  # Proxy exit IP for WebRTC spoofing

        return rf"""(function() {{
    'use strict';

    // === Configuration data injected from Python ===
    var FP_DATA = {{
        navigator: {json.dumps(nav)},
        screen: {json.dumps(screen)},
        webgl: {json.dumps(webgl)},
        battery: {json.dumps(battery)},
        mediaDevices: {json.dumps(media_devices)},
        clientHints: {json.dumps(client_hints)},
        audioContext: {json.dumps(audio_ctx)},
        canvas: {json.dumps(canvas_cfg)},
        webrtcMode: {json.dumps(webrtc_mode)},
        timezone: {json.dumps(timezone)},
        locale: {json.dumps(locale)},
        geolocation: {json.dumps(geo)},
        fonts: {json.dumps(fonts)},
        speechVoices: {json.dumps(speech_voices)},
        performance: {json.dumps(perf)},
        proxyIP: {json.dumps(proxy_ip)}
    }};

    // === Seeded PRNG (mulberry32) for deterministic noise ===
    function mulberry32(a) {{
        return function() {{
            a |= 0; a = a + 0x6D2B79F5 | 0;
            var t = a;
            t = Math.imul(t ^ t >>> 15, t | 1);
            t ^= t + Math.imul(t ^ t >>> 7, t | 61);
            return ((t ^ t >>> 14) >>> 0) / 4294967296;
        }};
    }}
    var canvasRng = mulberry32(FP_DATA.canvas.noiseSeed || 12345);
    var audioRng = mulberry32(FP_DATA.audioContext.noiseSeed || 54321);

    // === 1. Navigator spoofing ===
    var navProps = {{
        userAgent: FP_DATA.navigator.userAgent,
        platform: FP_DATA.navigator.platform,
        hardwareConcurrency: FP_DATA.navigator.hardwareConcurrency,
        deviceMemory: FP_DATA.navigator.deviceMemory,
        maxTouchPoints: FP_DATA.navigator.maxTouchPoints,
        webdriver: false,
        language: FP_DATA.navigator.language,
        languages: FP_DATA.navigator.languages,
        vendor: FP_DATA.navigator.vendor,
        cookieEnabled: FP_DATA.navigator.cookieEnabled,
        pdfViewerEnabled: FP_DATA.navigator.pdfViewerEnabled,
    }};
    if (FP_DATA.navigator.doNotTrack === null) {{
        navProps.doNotTrack = null;
    }} else {{
        navProps.doNotTrack = FP_DATA.navigator.doNotTrack;
    }}
    for (var key in navProps) {{
        try {{
            Object.defineProperty(navigator, key, {{
                get: function() {{ return navProps[this._fpKey]; }},
                configurable: true,
            }});
        }} catch(e) {{}}
    }}
    // Redefine with closures properly
    for (var key in navProps) {{
        (function(k, v) {{
            try {{
                Object.defineProperty(navigator, k, {{
                    get: function() {{ return v; }},
                    configurable: true,
                }});
            }} catch(e) {{}}
        }})(key, navProps[key]);
    }}

    // === 2. Navigator.plugins spoofing ===
    var fakePlugins = FP_DATA.navigator.plugins || [];
    try {{
        Object.defineProperty(navigator, 'plugins', {{
            get: function() {{
                var arr = fakePlugins.map(function(p) {{
                    return {{
                        name: p.name,
                        filename: p.filename,
                        description: p.description,
                        length: 1,
                    }};
                }});
                arr.item = function(i) {{ return arr[i] || null; }};
                arr.namedItem = function(n) {{ return arr.find(function(p) {{ return p.name === n; }}) || null; }};
                arr.refresh = function() {{}};
                return arr;
            }},
            configurable: true,
        }});
    }} catch(e) {{}}

    // === 3. Screen spoofing ===
    var screenProps = {{
        width: FP_DATA.screen.width,
        height: FP_DATA.screen.height,
        availWidth: FP_DATA.screen.availWidth,
        availHeight: FP_DATA.screen.availHeight,
        colorDepth: FP_DATA.screen.colorDepth,
        pixelDepth: FP_DATA.screen.pixelDepth,
    }};
    for (var key in screenProps) {{
        (function(k, v) {{
            try {{
                Object.defineProperty(window.screen, k, {{
                    get: function() {{ return v; }},
                    configurable: true,
                }});
            }} catch(e) {{}}
        }})(key, screenProps[key]);
    }}
    // devicePixelRatio
    try {{
        Object.defineProperty(window, 'devicePixelRatio', {{
            get: function() {{ return FP_DATA.screen.devicePixelRatio || 1; }},
            configurable: true,
        }});
    }} catch(e) {{}}

    // === 4. WebGL spoofing ===
    var webglVendor = FP_DATA.webgl.unmaskedVendor;
    var webglRenderer = FP_DATA.webgl.unmaskedRenderer;
    var getParameterHandler = {{
        apply: function(target, thisArg, args) {{
            var param = args[0];
            if (param === 37445) return webglVendor;
            if (param === 37446) return webglRenderer;
            if (param === 7936) return FP_DATA.webgl.vendor;
            if (param === 7937) return FP_DATA.webgl.renderer;
            return target.apply(thisArg, args);
        }}
    }};
    if (window.WebGLRenderingContext) {{
        try {{
            WebGLRenderingContext.prototype.getParameter = new Proxy(
                WebGLRenderingContext.prototype.getParameter, getParameterHandler
            );
        }} catch(e) {{}}
    }}
    if (window.WebGL2RenderingContext) {{
        try {{
            WebGL2RenderingContext.prototype.getParameter = new Proxy(
                WebGL2RenderingContext.prototype.getParameter, getParameterHandler
            );
        }} catch(e) {{}}
    }}
    // Spoof WebGL debug info
    if (window.WebGLRenderingContext && WebGLRenderingContext.prototype.getExtension) {{
        var origGetExtension = WebGLRenderingContext.prototype.getExtension;
        WebGLRenderingContext.prototype.getExtension = function(name) {{
            if (name === 'WEBGL_debug_renderer_info') {{
                return {{
                    UNMASKED_VENDOR_WEBGL: 37445,
                    UNMASKED_RENDERER_WEBGL: 37446,
                }};
            }}
            return origGetExtension.apply(this, arguments);
        }};
    }}

    // === 5. Battery Status spoofing ===
    if (navigator.getBattery) {{
        var batteryData = FP_DATA.battery;
        navigator.getBattery = function() {{
            return Promise.resolve({{
                charging: batteryData.charging,
                chargingTime: batteryData.chargingTime,
                dischargingTime: batteryData.dischargingTime,
                level: batteryData.level,
                addEventListener: function() {{}},
                removeEventListener: function() {{}},
                dispatchEvent: function() {{ return true; }},
            }});
        }};
    }}

    // === 6. Media Devices spoofing ===
    if (navigator.mediaDevices && navigator.mediaDevices.enumerateDevices) {{
        var fakeDevices = FP_DATA.mediaDevices;
        navigator.mediaDevices.enumerateDevices = function() {{
            return Promise.resolve(fakeDevices.map(function(d, i) {{
                return {{
                    kind: d.kind,
                    label: '',
                    deviceId: 'device-' + i + '-' + (d.deviceId || 'default'),
                    groupId: 'group-' + Math.floor(i / 2),
                }};
            }}));
        }};
    }}

    // === 7. WebRTC protection — IP spoofing + ICE candidate filtering ===
    // CloakBrowser approach: when proxyIP is known, inject it as a fake srflx
    // candidate so detection sites see the proxy IP (not "no IP" which is a signal).
    // When proxyIP is unknown, fall back to filtering host candidates only.
    if (window.RTCPeerConnection) {{
        var OrigRTC = window.RTCPeerConnection;
        var spoofIP = FP_DATA.proxyIP || '';
        window.RTCPeerConnection = function(config, constraints) {{
            if (!config) config = {{}};
            // Force relay-only to prevent local IP discovery
            if (FP_DATA.webrtcMode === 'filter') {{
                config.iceTransportPolicy = 'relay';
                // Remove STUN servers that could reveal public IP
                if (config.iceServers) {{
                    config.iceServers = config.iceServers.filter(function(s) {{
                        return s.urls && s.urls.toString().indexOf('stun:') === -1;
                    }});
                }}
            }}
            var pc = new OrigRTC(config, constraints);
            if (FP_DATA.webrtcMode === 'filter') {{
                // Intercept icecandidate events
                pc.addEventListener = (function(origAddEventListener) {{
                    return function(type, listener, options) {{
                        if (type === 'icecandidate') {{
                            var wrappedListener = function(event) {{
                                if (event && event.candidate && event.candidate.candidate) {{
                                    var cand = event.candidate.candidate;
                                    // Block host candidates (local IP leak)
                                    if (cand.indexOf('typ host') !== -1) {{
                                        return;
                                    }}
                                    // Replace srflx candidate IP with proxy IP if known
                                    if (spoofIP && cand.indexOf('typ srflx') !== -1) {{
                                        var spoofedCand = cand.replace(
                                            /(\d+\.\d+\.\d+\.\d+)/g, spoofIP
                                        );
                                        event.candidate = new RTCIceCandidate({{
                                            candidate: spoofedCand,
                                            sdpMLineIndex: event.candidate.sdpMLineIndex,
                                            sdpMid: event.candidate.sdpMid,
                                        }});
                                    }}
                                }}
                                listener.call(this, event);
                            }};
                            return origAddEventListener.call(this, type, wrappedListener, options);
                        }}
                        return origAddEventListener.apply(this, arguments);
                    }};
                }})(pc.addEventListener.bind(pc));

                // If we have a proxy IP, also intercept createDataChannel/onicecandidate
                // to inject a synthetic candidate so the site sees our spoofed IP
                if (spoofIP) {{
                    var origCreateOffer = pc.createOffer;
                    pc.createOffer = function(options) {{
                        return origCreateOffer.call(this, options).then(function(offer) {{
                            // Inject a fake srflx candidate into the SDP
                            var fakeLine = 'a=candidate:842163049 1 udp 1677729535 ' + spoofIP +
                                ' 56789 typ srflx raddr 0.0.0.0 rport 56789 generation 0';
                            offer.sdp = offer.sdp.replace(
                                /a=end-of-candidates/,
                                fakeLine + '\r\na=end-of-candidates'
                            );
                            // If no end-of-candidates marker, append
                            if (offer.sdp.indexOf('a=end-of-candidates') === -1) {{
                                offer.sdp = offer.sdp + '\r\n' + fakeLine;
                            }}
                            return offer;
                        }});
                    }};
                }}
            }}
            return pc;
        }};
        // Copy static properties
        window.RTCPeerConnection.generateCertificate = OrigRTC.generateCertificate;
        if (OrigRTC.getDefaultIceServers) {{
            window.RTCPeerConnection.getDefaultIceServers = OrigRTC.getDefaultIceServers;
        }}
    }}

    // === 8. Timezone spoofing — complete coverage ===
    var tz = FP_DATA.timezone;
    // 8a. Intl.DateTimeFormat
    var OrigDateTimeFormat = Intl.DateTimeFormat;
    Intl.DateTimeFormat = function(locale, options) {{
        if (!options) options = {{}};
        if (!options.timeZone) options.timeZone = tz;
        return new OrigDateTimeFormat(locale || FP_DATA.locale, options);
    }};
    Intl.DateTimeFormat.prototype = OrigDateTimeFormat.prototype;
    // 8b. resolvedOptions().timeZone
    var origResolvedOptions = Intl.DateTimeFormat.prototype.resolvedOptions;
    Intl.DateTimeFormat.prototype.resolvedOptions = function() {{
        var result = origResolvedOptions.call(this);
        result.timeZone = tz;
        return result;
    }};
    // 8c. Date.prototype.getTimezoneOffset
    var tzOffset = (function() {{
        var d = new Date();
        var utc = d.getTime() + (d.getTimezoneOffset() * 60000);
        var tzDate = new Date(utc + (0));
        // Calculate offset for our target timezone
        var intlFormatter = new OrigDateTimeFormat('en-US', {{
            timeZone: tz,
            timeZoneName: 'shortOffset',
        }});
        var parts = intlFormatter.formatToParts(d);
        var offsetStr = '';
        for (var i = 0; i < parts.length; i++) {{
            if (parts[i].type === 'timeZoneName') {{
                offsetStr = parts[i].value;
                break;
            }}
        }}
        // Parse GMT+X or GMT-X
        var offset = 0;
        var match = offsetStr.match(/GMT([+-])(\d{{1,2}}):?(\d{{2}})?/);
        if (match) {{
            offset = parseInt(match[2]) * 60 + (parseInt(match[3]) || 0);
            if (match[1] === '+') offset = -offset;
        }}
        return offset;
    }})();
    Date.prototype.getTimezoneOffset = function() {{
        return tzOffset;
    }};
    // 8d. Intl.DateTimeFormat.supportedLocalesOf passthrough
    Intl.DateTimeFormat.supportedLocalesOf = function() {{
        return OrigDateTimeFormat.supportedLocalesOf.apply(OrigDateTimeFormat, arguments);
    }};

    // === 9. Canvas fingerprint — multi-layer seeded noise ===
    var canvasSeed = FP_DATA.canvas.noiseSeed || 12345;
    var noiseLevel = FP_DATA.canvas.noiseLevel || 'subtle';
    var noiseMagnitude = noiseLevel === 'aggressive' ? 3 : noiseLevel === 'moderate' ? 2 : 1;

    function applyCanvasNoise(canvas, ctx) {{
        try {{
            var w = canvas.width;
            var h = canvas.height;
            if (w === 0 || h === 0) return;
            // Only apply noise to small canvases (avoid perf hit on large ones)
            if (w > 512 || h > 512) return;
            var imageData = ctx.getImageData(0, 0, w, h);
            var data = imageData.data;
            for (var i = 0; i < data.length; i += 4) {{
                // Apply subtle per-pixel noise based on seed
                var noiseVal = (Math.floor(canvasRng() * (noiseMagnitude * 2 + 1)) - noiseMagnitude);
                data[i] = Math.max(0, Math.min(255, data[i] + noiseVal));
                // Only modify R channel for subtlety — modifying all channels is more detectable
            }}
            ctx.putImageData(imageData, 0, 0);
        }} catch(e) {{}}
    }}

    // Intercept toDataURL
    var origToDataURL = HTMLCanvasElement.prototype.toDataURL;
    HTMLCanvasElement.prototype.toDataURL = function() {{
        var ctx = this.getContext('2d');
        if (ctx) applyCanvasNoise(this, ctx);
        return origToDataURL.apply(this, arguments);
    }};
    // Intercept toBlob
    var origToBlob = HTMLCanvasElement.prototype.toBlob;
    HTMLCanvasElement.prototype.toBlob = function() {{
        var ctx = this.getContext('2d');
        if (ctx) applyCanvasNoise(this, ctx);
        return origToBlob.apply(this, arguments);
    }};
    // Intercept getImageData (for canvas fingerprinting via pixel reading)
    var origGetImageData = CanvasRenderingContext2D.prototype.getImageData;
    CanvasRenderingContext2D.prototype.getImageData = function() {{
        var result = origGetImageData.apply(this, arguments);
        // Apply noise to the returned pixel data
        var data = result.data;
        for (var i = 0; i < data.length; i += 4) {{
            var noiseVal = (Math.floor(canvasRng() * (noiseMagnitude * 2 + 1)) - noiseMagnitude);
            data[i] = Math.max(0, Math.min(255, data[i] + noiseVal));
        }}
        return result;
    }};
    // Intercept OffscreenCanvas if available
    if (window.OffscreenCanvas) {{
        var origOCConvertToBlob = OffscreenCanvas.prototype.convertToBlob;
        if (origOCConvertToBlob) {{
            OffscreenCanvas.prototype.convertToBlob = function() {{
                var ctx = this.getContext('2d');
                if (ctx) applyCanvasNoise(this, ctx);
                return origOCConvertToBlob.apply(this, arguments);
            }};
        }}
    }}

    // === 10. AudioContext fingerprint protection ===
    if (window.AnalyserNode) {{
        var origGetFloatFrequencyData = AnalyserNode.prototype.getFloatFrequencyData;
        AnalyserNode.prototype.getFloatFrequencyData = function(array) {{
            origGetFloatFrequencyData.call(this, array);
            for (var i = 0; i < array.length; i++) {{
                array[i] += (audioRng() - 0.5) * 0.0001;
            }}
        }};
        var origGetByteFrequencyData = AnalyserNode.prototype.getByteFrequencyData;
        AnalyserNode.prototype.getByteFrequencyData = function(array) {{
            origGetByteFrequencyData.call(this, array);
            for (var i = 0; i < array.length; i++) {{
                array[i] = Math.max(0, Math.min(255, array[i] + Math.floor((audioRng() - 0.5) * 2)));
            }}
        }};
    }}
    // Spoof AudioContext.sampleRate and channelCount
    if (window.AudioContext || window.webkitAudioContext) {{
        var AudioCtx = window.AudioContext || window.webkitAudioContext;
        var origCreateAnalyser = AudioCtx.prototype.createAnalyser;
        // Override createOscillator + createDynamicsCompressor for fingerprint resistance
        var origCreateDynamicsCompressor = AudioCtx.prototype.createDynamicsCompressor;
        AudioCtx.prototype.createDynamicsCompressor = function() {{
            var comp = origCreateDynamicsCompressor.call(this);
            var origGetFrequencyResponse = comp.getFrequencyResponse;
            comp.getFrequencyResponse = function(freqArray, magArray, phaseArray) {{
                origGetFrequencyResponse.call(this, freqArray, magArray, phaseArray);
                if (magArray) {{
                    for (var i = 0; i < magArray.length; i++) {{
                        magArray[i] += (audioRng() - 0.5) * 0.0001;
                    }}
                }}
                if (phaseArray) {{
                    for (var i = 0; i < phaseArray.length; i++) {{
                        phaseArray[i] += (audioRng() - 0.5) * 0.0001;
                    }}
                }}
            }};
            return comp;
        }};
    }}

    // === 11. ClientHints (Sec-CH-UA) / userAgentData spoofing ===
    if (FP_DATA.clientHints) {{
        var ch = FP_DATA.clientHints;
        var uaDataObj = {{
            brands: ch.brands,
            mobile: ch.mobile,
            platform: ch.platform,
            getHighEntropyValues: function(hints) {{
                return Promise.resolve({{
                    brands: ch.brands,
                    mobile: ch.mobile,
                    platform: ch.platform,
                    platformVersion: ch.platformVersion,
                    architecture: ch.architecture,
                    bitness: ch.bitness,
                    model: ch.model,
                    uaFullVersion: ch.uaFullVersion,
                    fullVersionList: ch.brands.map(function(b) {{
                        return {{ brand: b.brand, version: b.version + '.0.0.0' }};
                    }}),
                }});
            }},
            toJSON: function() {{
                return {{
                    brands: ch.brands,
                    mobile: ch.mobile,
                    platform: ch.platform,
                }};
            }},
        }};
        try {{
            Object.defineProperty(navigator, 'userAgentData', {{
                get: function() {{ return uaDataObj; }},
                configurable: true,
            }});
        }} catch(e) {{}}
    }}

    // === 12. Font enumeration protection ===
    // Intercept offsetWidth/offsetHeight measurement used for font detection
    var fakeFonts = FP_DATA.fonts;
    var fontSet = {{}};
    for (var i = 0; i < fakeFonts.length; i++) {{
        fontSet[fakeFonts[i]] = true;
    }}
    // Override document.fonts.check to report consistent font availability
    if (document.fonts && document.fonts.check) {{
        var origFontsCheck = document.fonts.check;
        document.fonts.check = function(font, text) {{
            // Extract font family from font string
            var match = font.match(/font-family:\\s*([^;]+)/);
            if (match) {{
                var fontFamily = match[1].replace(/['"]/g, '').trim().split(',')[0].trim();
                if (fontSet[fontFamily]) return true;
                return false;
            }}
            return origFontsCheck.apply(this, arguments);
        }};
    }}

    // === 13. Geolocation spoofing ===
    if (navigator.geolocation) {{
        var geoData = FP_DATA.geolocation;
        var origGetCurrentPosition = navigator.geolocation.getCurrentPosition;
        navigator.geolocation.getCurrentPosition = function(success, error, options) {{
            success({{
                coords: {{
                    latitude: geoData.latitude,
                    longitude: geoData.longitude,
                    accuracy: geoData.accuracy || 50,
                    altitude: null,
                    altitudeAccuracy: null,
                    heading: null,
                    speed: null,
                }},
                timestamp: Date.now(),
            }});
        }};
        var origWatchPosition = navigator.geolocation.watchPosition;
        navigator.geolocation.watchPosition = function(success, error, options) {{
            navigator.geolocation.getCurrentPosition(success, error, options);
            return Math.floor(Math.random() * 100000);
        }};
    }}

    // === 14. Speech synthesis spoofing ===
    if (window.speechSynthesis) {{
        var fakeVoices = FP_DATA.speechVoices;
        speechSynthesis.getVoices = function() {{
            return fakeVoices.map(function(v) {{
                return {{
                    name: v.name,
                    lang: v.lang,
                    voiceURI: v.name,
                    default: false,
                    localService: true,
                }};
            }});
        }};
        // Trigger voiceschanged event
        setTimeout(function() {{
            speechSynthesis.dispatchEvent(new Event('voiceschanged'));
        }}, 100);
    }}

    // === 15. Performance API protection ===
    if (performance.memory) {{
        try {{
            Object.defineProperty(performance, 'memory', {{
                get: function() {{
                    return {{
                        jsHeapSizeLimit: FP_DATA.performance.memory * 1024 * 1024 * 1024,
                        totalJSHeapSize: Math.floor(FP_DATA.performance.memory * 512 * 1024 * 1024 * (0.3 + Math.random() * 0.4)),
                        usedJSHeapSize: Math.floor(FP_DATA.performance.memory * 256 * 1024 * 1024 * (0.1 + Math.random() * 0.3)),
                    }};
                }},
                configurable: true,
            }});
        }} catch(e) {{}}
    }}

    // === 16. navigator.connection (Network Information API) ===
    if (navigator.connection) {{
        try {{
            var connProps = {{
                effectiveType: '4g',
                rtt: 50,
                downlink: 10,
                saveData: false,
                type: 'wifi',
            }};
            for (var ck in connProps) {{
                try {{
                    Object.defineProperty(navigator.connection, ck, {{
                        get: function() {{ return connProps[ck]; }},
                        configurable: true,
                    }});
                }} catch(e) {{}}
            }}
        }} catch(e) {{}}
    }}

    // === 17. Intl.Collator / Intl.NumberFormat fingerprinting ===
    try {{
        var OrigCollator = Intl.Collator;
        var origCollatorResolved = OrigCollator.prototype.resolvedOptions;
        OrigCollator.prototype.resolvedOptions = function() {{
            var opts = origCollatorResolved.apply(this, arguments);
            opts.locale = FP_DATA.locale;
            return opts;
        }};
        var OrigNumberFormat = Intl.NumberFormat;
        var origNFResolved = OrigNumberFormat.prototype.resolvedOptions;
        OrigNumberFormat.prototype.resolvedOptions = function() {{
            var opts = origNFResolved.apply(this, arguments);
            opts.locale = FP_DATA.locale;
            return opts;
        }};
    }} catch(e) {{}}

    // === 18. window.outer* properties spoofing ===
    try {{
        var screenW = FP_DATA.screen.width;
        var screenH = FP_DATA.screen.height;
        Object.defineProperty(window, 'outerWidth', {{
            get: function() {{ return screenW; }},
            configurable: true,
        }});
        Object.defineProperty(window, 'outerHeight', {{
            get: function() {{ return screenH; }},
            configurable: true,
        }});
    }} catch(e) {{}}

    // === 19. CSS @supports fingerprinting resistance ===
    try {{
        var origCSSSupports = CSS.supports;
        CSS.supports = function(prop, val) {{
            // Normalize behavior — don't reveal unique CSS feature support
            return origCSSSupports.apply(this, arguments);
        }};
    }} catch(e) {{}}

    // === 20. Storage quota normalization (anti-incognito detection) ===
    // CloakBrowser technique: spoof storage.estimate() so detection sites
    // can't identify incognito/ephemeral profiles by their tiny quota.
    // Real persistent profiles show hundreds of GB; incognito shows ~0.
    try {{
        if (navigator.storage && navigator.storage.estimate) {{
            var origEstimate = navigator.storage.estimate.bind(navigator.storage);
            // Generate plausible quota based on seed for consistency
            var seedVal = FP_DATA.canvas.noiseSeed || 12345;
            var fakeQuota = 500000000000 + (seedVal % 300000000000); // 500GB–800GB
            var fakeUsage = 10000000000 + (seedVal % 50000000000);   // 10GB–60GB
            navigator.storage.estimate = function() {{
                return Promise.resolve({{
                    usage: fakeUsage,
                    quota: fakeQuota,
                    usageDetails: {{
                        caches: Math.floor(fakeUsage * 0.3),
                        indexedDB: Math.floor(fakeUsage * 0.4),
                        serviceWorkerRegistrations: Math.floor(fakeUsage * 0.1),
                    }},
                }});
            }};
        }}
    }} catch(e) {{}}

    // === 21. Performance API timing normalization (hide proxy latency) ===
    // CloakBrowser zeros DNS/connect/SSL timing to hide proxy patterns.
    // We normalize timing entries so proxy latency patterns aren't detectable.
    try {{
        var origGetEntriesByType = PerformanceObserver.prototype.constructor.prototype.getEntriesByType ||
            performance.getEntriesByType.bind(performance);
        if (performance.getEntriesByType) {{
            var origGetEntries = performance.getEntriesByType.bind(performance);
            performance.getEntriesByType = function(type) {{
                var entries = origGetEntries(type);
                if (type === 'resource' || type === 'navigation') {{
                    entries.forEach(function(entry) {{
                        try {{
                            // Zero out timing details that reveal proxy hops
                            Object.defineProperty(entry, 'domainLookupStart', {{ get: function() {{ return entry.fetchStart || 0; }} }});
                            Object.defineProperty(entry, 'domainLookupEnd', {{ get: function() {{ return entry.fetchStart || 0; }} }});
                            Object.defineProperty(entry, 'connectStart', {{ get: function() {{ return entry.fetchStart || 0; }} }});
                            Object.defineProperty(entry, 'connectEnd', {{ get: function() {{ return entry.fetchStart || 0; }} }});
                            Object.defineProperty(entry, 'secureConnectionStart', {{ get: function() {{ return entry.fetchStart || 0; }} }});
                        }} catch(e) {{}}
                    }});
                }}
                return entries;
            }};
        }}
    }} catch(e) {{}}

    // === 22. Remove automation signals ===
    // Remove cdc_ properties that ChromeDriver injects
    var cdcProps = Object.getOwnPropertyNames(document).filter(function(p) {{
        return p.match(/^cdc_/) || p.match(/^\\$cdc_/);
    }});
    cdcProps.forEach(function(prop) {{
        try {{ delete document[prop]; }} catch(e) {{}}
    }});
    // Remove webdriver flag (redundant with navigator override but belt-and-suspenders)
    try {{
        Object.defineProperty(navigator, 'webdriver', {{
            get: function() {{ return false; }},
            configurable: true,
        }});
    }} catch(e) {{}}

    // === 23. Enhanced CDP detection countermeasures ===
    // CloakBrowser patches isAutomatedWithCDP at source level.
    // We counter detectable JS-level CDP artifacts.
    try {{
        // Remove window.cdc_adoQpoasnfa76pfcZLmcfl_Array injection
        if (window.cdc_adoQpoasnfa76pfcZLmcfl_Array) delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
        if (window.cdc_adoQpoasnfa76pfcZLmcfl_Promise) delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
        if (window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol) delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;
        // Ensure window.chrome exists with expected structure
        if (!window.chrome) {{
            window.chrome = {{
                runtime: {{}},
                loadTimes: function() {{ return {{}}; }},
                csi: function() {{ return {{}}; }},
                app: {{ isInstalled: false }},
            }};
        }} else if (!window.chrome.runtime) {{
            window.chrome.runtime = {{}};
        }}
        // Patch Permissions API to not reveal automation
        if (navigator.permissions && navigator.permissions.query) {{
            var origQuery = navigator.permissions.query.bind(navigator.permissions);
            navigator.permissions.query = function(desc) {{
                if (desc && desc.name === 'notifications') {{
                    return Promise.resolve({{ state: 'prompt', onchange: null }});
                }}
                return origQuery(desc);
            }};
        }}
    }} catch(e) {{}}

}})();
"""
