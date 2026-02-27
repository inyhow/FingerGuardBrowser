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
        
        # 加载基础指纹模板
        self.template = {
            "navigator": {
                "userAgent": "",
                "platform": "Win32" if platform.system() == "Windows" else "MacIntel" if platform.system() == "Darwin" else "Linux x86_64",
                "language": "en-US",
                "languages": ["en-US", "en"],
                "hardwareConcurrency": 4,
                "deviceMemory": 8,
                "webdriver": False,
                "vendor": "Google Inc.",
                "vendorSub": "",
                "productSub": "20030107",
                "cookieEnabled": True
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
                "vendor": "Google Inc. (NVIDIA)",
                "renderer": "ANGLE (NVIDIA, NVIDIA GeForce GTX 1660 SUPER Direct3D11 vs_5_0 ps_5_0)",
                "unmaskedVendor": "Google Inc.",
                "unmaskedRenderer": "ANGLE (NVIDIA, NVIDIA GeForce GTX 1660 SUPER Direct3D11 vs_5_0 ps_5_0)"
            },
            "audio": {
                "state": "suspended",
                "sampleRate": 44100,
                "channelCount": 2
            },
            "timezone": "UTC",
            "fonts": [
                "Arial", "Arial Black", "Arial Unicode MS", "Calibri", "Cambria",
                "Cambria Math", "Comic Sans MS", "Courier", "Courier New", "Georgia",
                "Helvetica", "Impact", "Times", "Times New Roman", "Trebuchet MS", "Verdana"
            ]
        }
        
        # 常用的User-Agent列表
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.159 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.82 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.81 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/95.0.4638.69 Safari/537.36"
        ]

    def inject_js_script(self, script: str, *args) -> Any:
        """注入并执行JavaScript脚本"""
        if not self.driver:
            logger.error("No driver provided for injection")
            return
        try:
            return self.driver.execute_script(script, *args)
        except Exception as e:
            logger.error(f"Failed to inject JavaScript: {str(e)}")
            raise

    def create_fingerprint(self, name: str) -> Dict[str, Any]:
        """创建新的指纹配置"""
        fingerprint = self.template.copy()
        
        # 随机化一些值
        fingerprint["navigator"]["userAgent"] = random.choice(self.user_agents)
        fingerprint["navigator"]["hardwareConcurrency"] = random.choice([2, 4, 6, 8])
        fingerprint["navigator"]["deviceMemory"] = random.choice([4, 8, 16])
        
        screen_resolutions = [
            (1920, 1080),
            (1366, 768),
            (1440, 900),
            (1536, 864),
            (1600, 900)
        ]
        width, height = random.choice(screen_resolutions)
        fingerprint["screen"]["width"] = width
        fingerprint["screen"]["height"] = height
        fingerprint["screen"]["availWidth"] = width
        fingerprint["screen"]["availHeight"] = height - 40
        
        # 保存指纹配置
        self.save_fingerprint(name, fingerprint)
        return fingerprint
    
    def load_fingerprint(self, name: str) -> Dict[str, Any]:
        """加载指定的指纹配置"""
        filepath = os.path.join(self.fingerprints_dir, f"{name}.json")
        try:
            with open(filepath, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning(f"Fingerprint {name} not found, creating new one")
            return self.create_fingerprint(name)
    
    def save_fingerprint(self, name: str, fingerprint: Dict[str, Any]):
        """保存指纹配置"""
        filepath = os.path.join(self.fingerprints_dir, f"{name}.json")
        with open(filepath, "w") as f:
            json.dump(fingerprint, f, indent=4)
    
    def apply_fingerprint(self, fingerprint: Dict[str, Any]):
        """将指纹应用到当前浏览器"""
        if not self.driver:
            return

        script = self.get_injection_script(fingerprint)
        self.inject_js_script(script)

    def get_injection_script(self, fingerprint: Dict[str, Any]) -> str:
        """生成注入浏览器的JavaScript代码"""
        nav = fingerprint.get('navigator', {})
        screen = fingerprint.get('screen', {})
        webgl = fingerprint.get('webgl', {})

        return f"""
            // 修改navigator属性
            Object.defineProperties(navigator, {{
                userAgent: {{ value: {json.dumps(nav.get('userAgent', ''))} }},
                platform: {{ value: {json.dumps(nav.get('platform', 'Win32'))} }},
                hardwareConcurrency: {{ value: {nav.get('hardwareConcurrency', 4)} }},
                deviceMemory: {{ value: {nav.get('deviceMemory', 8)} }},
                webdriver: {{ value: {str(nav.get('webdriver', False)).lower()} }},
                language: {{ value: {json.dumps(nav.get('language', 'en-US'))} }},
                languages: {{ value: {json.dumps(nav.get('languages', ['en-US', 'en']))} }}
            }});
            
            // 修改screen属性
            Object.defineProperties(screen, {{
                width: {{ value: {screen.get('width', 1920)} }},
                height: {{ value: {screen.get('height', 1080)} }},
                availWidth: {{ value: {screen.get('availWidth', 1920)} }},
                availHeight: {{ value: {screen.get('availHeight', 1040)} }},
                colorDepth: {{ value: {screen.get('colorDepth', 24)} }},
                pixelDepth: {{ value: {screen.get('pixelDepth', 24)} }}
            }});

            // 修改时区
            if ({json.dumps(fingerprint.get('timezone', 'UTC'))}) {{
                const timezone = {json.dumps(fingerprint.get('timezone', 'UTC'))};
                const originalDateTimeFormat = Intl.DateTimeFormat;
                Intl.DateTimeFormat = function(locale, options) {{
                    if (options && !options.timeZone) {{
                        options.timeZone = timezone;
                    }}
                    return new originalDateTimeFormat(locale, options);
                }};
                Intl.DateTimeFormat.prototype = originalDateTimeFormat.prototype;
                Intl.DateTimeFormat.supportedLocalesOf = originalDateTimeFormat.supportedLocalesOf;
            }}
            
            // WebGL指纹保护
            const getParameterProxyHandler = {{
                apply: function(target, thisArg, argumentsList) {{
                    const param = argumentsList[0];
                    if (param === 37445) {{ // UNMASKED_VENDOR_WEBGL
                        return {json.dumps(webgl.get('unmaskedVendor', webgl.get('vendor', 'Google Inc.')))};
                    }}
                    if (param === 37446) {{ // UNMASKED_RENDERER_WEBGL
                        return {json.dumps(webgl.get('unmaskedRenderer', webgl.get('renderer', 'ANGLE (NVIDIA, NVIDIA GeForce GTX 1660 SUPER Direct3D11 vs_5_0 ps_5_0)')))};
                    }}
                    return target.apply(thisArg, argumentsList);
                }}
            }};
            
            if (window.WebGLRenderingContext) {{
                const originalGetParameter = WebGLRenderingContext.prototype.getParameter;
                WebGLRenderingContext.prototype.getParameter = new Proxy(originalGetParameter, getParameterProxyHandler);
            }}

            // Canvas指纹保护
            const originalToDataURL = HTMLCanvasElement.prototype.toDataURL;
            HTMLCanvasElement.prototype.toDataURL = function(type) {{
                if (type === 'image/png' && this.width === 16 && this.height === 16) {{
                    return 'data:image/png;base64,00';
                }}
                return originalToDataURL.apply(this, arguments);
            }};
            
            // 字体指纹保护
            if (document.fonts) {{
                const fonts = {json.dumps(fingerprint.get('fonts', []))};
                Object.defineProperty(document, 'fonts', {{
                    get: () => {{
                        return {{
                            ready: Promise.resolve(),
                            check: () => true,
                            load: () => Promise.resolve(),
                            entries: () => [],
                            forEach: () => {{}},
                            *[Symbol.iterator]() {{
                                yield* fonts;
                            }}
                        }};
                    }}
                }});
            }}
        """
