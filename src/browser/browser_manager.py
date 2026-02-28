import os
import requests
import undetected_chromedriver as uc
from loguru import logger
from .profile import ProfileManager, BrowserProfile
from typing import Optional, Dict, Any

class BrowserManager:
    """Enhanced Browser Manager for commercial use"""
    def __init__(self):
        self.config_dir = os.path.join(os.path.dirname(__file__), "config")
        os.makedirs(self.config_dir, exist_ok=True)
        self.profile_manager = ProfileManager(self.config_dir)

    def create_profile(self, name: str, **kwargs) -> BrowserProfile:
        return self.profile_manager.create_profile(name, **kwargs)

    def get_profile(self, name: str) -> BrowserProfile:
        return self.profile_manager.get_profile(name)

    def update_profile(self, name: str, **kwargs) -> BrowserProfile:
        return self.profile_manager.update_profile(name, **kwargs)

    def delete_profile(self, name: str):
        self.profile_manager.delete_profile(name)

    def list_profiles(self) -> dict:
        return self.profile_manager.list_profiles()

    def get_all_profiles(self) -> dict:
        return self.list_profiles()

    def check_proxy(self, proxy: str) -> Dict[str, Any]:
        """验证代理连通性并获取地理位置信息"""
        if not proxy:
            return {"status": "error", "message": "No proxy provided"}

        proxies = {
            "http": proxy,
            "https": proxy
        }

        try:
            # 使用 ip-api.com 获取地理位置信息
            response = requests.get("http://ip-api.com/json/", proxies=proxies, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success":
                    return {
                        "status": "success",
                        "ip": data.get("query"),
                        "country": data.get("country"),
                        "city": data.get("city"),
                        "isp": data.get("isp"),
                        "timezone": data.get("timezone")
                    }
                else:
                    return {"status": "error", "message": data.get("message", "Unknown error")}
            else:
                return {"status": "error", "message": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def launch_browser(self, profile_name: str):
        """启动指定配置的浏览器 (增强型)"""
        try:
            profile = self.profile_manager.get_profile(profile_name)
            if not profile:
                raise ValueError(f"Profile {profile_name} not found")
            
            if profile.is_running:
                logger.warning(f"Browser {profile_name} is already running")
                return profile.driver
                
            logger.info(f"Launching browser with profile: {profile_name}")
            
            # 代理验证
            if profile.proxy:
                proxy_info = self.check_proxy(profile.proxy)
                if proxy_info["status"] == "success":
                    logger.info(f"Proxy verified: {proxy_info['ip']} ({proxy_info['country']})")
                else:
                    logger.warning(f"Proxy verification failed: {proxy_info['message']}")

            options = uc.ChromeOptions()
            
            # 基础安全与隐私设置
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('--disable-blink-features=AutomationControlled')

            # 设置代理
            if profile.proxy:
                options.add_argument(f'--proxy-server={profile.proxy}')
            
            # 设置时区 (如果代理验证成功，可以使用代理的时区)
            tz = profile.timezone or (proxy_info.get('timezone') if profile.proxy and proxy_info['status'] == 'success' else 'UTC')
            options.add_argument(f'--timezone={tz}')
            
            # 启动
            driver = uc.Chrome(options=options)
            profile.driver = driver
            profile.is_running = True
            self.profile_manager.save_profiles()
            
            logger.info(f"Browser launched successfully: {profile_name}")
            return driver
            
        except Exception as e:
            logger.error(f"Error launching browser: {str(e)}")
            raise

    def close_browser(self, profile_name: str):
        try:
            profile = self.profile_manager.get_profile(profile_name)
            if profile and profile.is_running:
                if profile.driver:
                    profile.driver.quit()
                profile.driver = None
                profile.is_running = False
                self.profile_manager.save_profiles()
                logger.info(f"Browser closed: {profile_name}")
        except Exception as e:
            logger.error(f"Error closing browser: {str(e)}")
            raise

    def is_profile_running(self, profile_name: str) -> bool:
        profile = self.profile_manager.get_profile(profile_name)
        return profile and profile.is_running
