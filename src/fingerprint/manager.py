from selenium.webdriver.chrome.webdriver import WebDriver
from typing import Dict, Any, Optional
import json
import os
from loguru import logger

class FingerprintManager:
    def __init__(self, driver: WebDriver):
        self.driver = driver
        
    def inject_js_script(self, script: str, *args) -> Any:
        """注入并执行JavaScript脚本"""
        try:
            return self.driver.execute_script(script, *args)
        except Exception as e:
            logger.error(f"Failed to inject JavaScript: {str(e)}")
            raise

    def modify_navigator(self, properties: Dict[str, Any]):
        """修改navigator属性"""
        script = """
        const properties = arguments[0];
        for (let [key, value] of Object.entries(properties)) {
            Object.defineProperty(navigator, key, {
                get: () => value
            });
        }
        """
        self.inject_js_script(script, properties)
        
    def modify_screen_resolution(self, width: int, height: int):
        """修改屏幕分辨率"""
        script = f"""
        Object.defineProperty(window.screen, 'width', {{
            get: () => {width}
        }});
        Object.defineProperty(window.screen, 'height', {{
            get: () => {height}
        }});
        """
        self.inject_js_script(script)
        
    def modify_timezone(self, timezone: str):
        """修改时区"""
        script = f"""
        Object.defineProperty(Intl, 'DateTimeFormat', {{
            get: () => function() {{
                return {{ resolvedOptions: () => {{ return {{ timeZone: '{timezone}' }} }} }}
            }}
        }});
        """
        self.inject_js_script(script)
        
    def modify_webgl_vendor(self, vendor: str, renderer: str):
        """修改WebGL信息"""
        script = f"""
        const getParameter = WebGLRenderingContext.prototype.getParameter;
        WebGLRenderingContext.prototype.getParameter = function(parameter) {{
            if (parameter === 37445) {{
                return '{vendor}';
            }}
            if (parameter === 37446) {{
                return '{renderer}';
            }}
            return getParameter.apply(this, arguments);
        }};
        """
        self.inject_js_script(script)
        
    def modify_user_agent(self, user_agent: str):
        """修改User-Agent"""
        script = f"""
        Object.defineProperty(navigator, 'userAgent', {{
            get: () => '{user_agent}'
        }});
        """
        self.inject_js_script(script)
        
    def load_fingerprint(self, fingerprint_file: str):
        """从文件加载指纹配置"""
        try:
            with open(fingerprint_file, 'r') as f:
                config = json.load(f)
                
            if 'navigator' in config:
                self.modify_navigator(config['navigator'])
            if 'screen' in config:
                self.modify_screen_resolution(
                    config['screen'].get('width', 1920),
                    config['screen'].get('height', 1080)
                )
            if 'timezone' in config:
                self.modify_timezone(config['timezone'])
            if 'webgl' in config:
                self.modify_webgl_vendor(
                    config['webgl'].get('vendor', ''),
                    config['webgl'].get('renderer', '')
                )
            if 'userAgent' in config:
                self.modify_user_agent(config['userAgent'])
                
            logger.info(f"Successfully loaded fingerprint from {fingerprint_file}")
        except Exception as e:
            logger.error(f"Failed to load fingerprint: {str(e)}")
            raise
