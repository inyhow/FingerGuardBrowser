import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium_stealth import stealth
import os
import json
from loguru import logger
from src.fingerprint.fingerprint_manager import FingerprintManager

class FingerGuardBrowser:
    def __init__(self, profile_name: str = "default", fingerprint_name: str = "default", proxy: str = None):
        self.profile_name = profile_name
        self.fingerprint_name = fingerprint_name
        self.proxy = proxy
        self.driver = None
        self.tabs = []
        self.current_tab_index = -1
        self.fingerprint_manager = None
        
        # 确保配置目录存在
        self.profile_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "src", "profiles", profile_name
        )
        os.makedirs(self.profile_dir, exist_ok=True)
        
    def _create_options(self) -> uc.ChromeOptions:
        """创建Chrome选项"""
        options = uc.ChromeOptions()
        
        # 基本设置
        options.add_argument(f"--user-data-dir={self.profile_dir}")
        options.add_argument("--no-first-run")
        options.add_argument("--no-default-browser-check")
        options.add_argument("--disable-blink-features=AutomationControlled")
        
        # 增强的保护设置
        options.add_argument("--disable-webrtc")
        options.add_argument("--disable-background-networking")
        options.add_argument("--disable-default-apps")
        options.add_argument("--disable-sync")
        options.add_argument("--disable-translate")
        
        if self.proxy:
            options.add_argument(f"--proxy-server={self.proxy}")
        
        return options
        
    def start(self):
        """启动浏览器"""
        try:
            options = self._create_options()
            
            self.driver = uc.Chrome(options=options)
            self.fingerprint_manager = FingerprintManager(self.driver)
            
            # 基础 stealth
            stealth(
                self.driver,
                languages=["en-US", "en"],
                vendor="Google Inc.",
                platform="Win32",
                webgl_vendor="Intel Inc.",
                renderer="Intel Iris OpenGL Engine",
                fix_hairline=True,
            )
            
            # 加载并注入高级指纹
            fingerprint = self.fingerprint_manager.load_fingerprint(self.fingerprint_name)
            injection_script = self.fingerprint_manager.get_injection_script(fingerprint)
            
            # 在每个页面加载前执行脚本 (undetected_chromedriver 特性)
            self.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                'source': injection_script
            })
            
            self.new_tab()
            return self.driver
            
        except Exception as e:
            logger.error(f"Failed to start browser: {str(e)}")
            raise
            
    def new_tab(self):
        if not self.driver:
            raise Exception("Browser not started")
        self.driver.execute_script("window.open('about:blank');")
        self.tabs.append(self.driver.window_handles[-1])
        self.current_tab_index = len(self.tabs) - 1
        self.driver.switch_to.window(self.tabs[self.current_tab_index])
        
    def navigate(self, url: str):
        if not self.driver or not self.tabs:
            raise Exception("No tabs available")
        self.driver.get(url)
            
    def close(self):
        if self.driver:
            self.driver.quit()
            self.driver = None
            self.tabs = []
            self.current_tab_index = -1
