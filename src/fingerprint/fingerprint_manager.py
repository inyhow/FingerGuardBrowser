import json
import os
import random
import platform
from loguru import logger
from typing import Dict, Any

class FingerprintManager:
    def __init__(self):
        self.fingerprints_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "profiles"
        )
        os.makedirs(self.fingerprints_dir, exist_ok=True)
        
        # 加载基础指纹模板
        self.template = {
            "navigator": {
                "userAgent": "",
                "platform": platform.system(),
                "language": ["en-US", "en"],
                "languages": ["en-US", "en"],
                "hardwareConcurrency": 4,
                "deviceMemory": 8,
                "webdriver": False
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
            "mediaDevices": {
                "enabledDevices": ["audioinput", "audiooutput", "videoinput"]
            },
            "fonts": [
                "Arial",
                "Arial Black",
                "Arial Unicode MS",
                "Calibri",
                "Cambria",
                "Cambria Math",
                "Comic Sans MS",
                "Courier",
                "Courier New",
                "Georgia",
                "Helvetica",
                "Impact",
                "Times",
                "Times New Roman",
                "Trebuchet MS",
                "Verdana"
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
        try:
            with open(os.path.join(self.fingerprints_dir, f"{name}.json"), "r") as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning(f"Fingerprint {name} not found, creating new one")
            return self.create_fingerprint(name)
    
    def save_fingerprint(self, name: str, fingerprint: Dict[str, Any]):
        """保存指纹配置"""
        with open(os.path.join(self.fingerprints_dir, f"{name}.json"), "w") as f:
            json.dump(fingerprint, f, indent=4)
    
    def get_injection_script(self, fingerprint: Dict[str, Any]) -> str:
        """生成注入浏览器的JavaScript代码"""
        return f"""
            // 修改navigator属性
            Object.defineProperties(navigator, {{
                userAgent: {{ value: "{fingerprint['navigator']['userAgent']}" }},
                platform: {{ value: "{fingerprint['navigator']['platform']}" }},
                hardwareConcurrency: {{ value: {fingerprint['navigator']['hardwareConcurrency']} }},
                deviceMemory: {{ value: {fingerprint['navigator']['deviceMemory']} }},
                webdriver: {{ value: {str(fingerprint['navigator']['webdriver']).lower()} }}
            }});
            
            // 修改screen属性
            Object.defineProperties(screen, {{
                width: {{ value: {fingerprint['screen']['width']} }},
                height: {{ value: {fingerprint['screen']['height']} }},
                availWidth: {{ value: {fingerprint['screen']['availWidth']} }},
                availHeight: {{ value: {fingerprint['screen']['availHeight']} }},
                colorDepth: {{ value: {fingerprint['screen']['colorDepth']} }},
                pixelDepth: {{ value: {fingerprint['screen']['pixelDepth']} }}
            }});
            
            // WebGL指纹保护
            const getParameterProxyHandler = {{
                apply: function(target, thisArg, argumentsList) {{
                    const param = argumentsList[0];
                    if (param === 37445) {{ // UNMASKED_VENDOR_WEBGL
                        return "{fingerprint['webgl']['unmaskedVendor']}";
                    }}
                    if (param === 37446) {{ // UNMASKED_RENDERER_WEBGL
                        return "{fingerprint['webgl']['unmaskedRenderer']}";
                    }}
                    return target.apply(thisArg, argumentsList);
                }}
            }};
            
            // Canvas指纹保护
            const originalToDataURL = HTMLCanvasElement.prototype.toDataURL;
            HTMLCanvasElement.prototype.toDataURL = function(type) {{
                if (type === 'image/png' && this.width === 16 && this.height === 16) {{
                    return 'data:image/png;base64,00';
                }}
                return originalToDataURL.apply(this, arguments);
            }};
            
            // 字体指纹保护
            Object.defineProperty(document, 'fonts', {{
                get: () => {{
                    const fonts = {fingerprint['fonts']};
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
        """
