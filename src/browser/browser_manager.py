import os
from pathlib import Path
import json
import undetected_chromedriver as uc
from loguru import logger
from .profile import ProfileManager, BrowserProfile

class BrowserManager:
    """浏览器管理器"""
    def __init__(self):
        self.config_dir = os.path.join(os.path.dirname(__file__), "config")
        os.makedirs(self.config_dir, exist_ok=True)
        self.profile_manager = ProfileManager(self.config_dir)

    def create_profile(self, name: str, **kwargs) -> BrowserProfile:
        """创建新的浏览器配置文件"""
        return self.profile_manager.create_profile(name, **kwargs)

    def get_profile(self, name: str) -> BrowserProfile:
        """获取浏览器配置文件"""
        return self.profile_manager.get_profile(name)

    def update_profile(self, name: str, **kwargs) -> BrowserProfile:
        """更新浏览器配置文件"""
        return self.profile_manager.update_profile(name, **kwargs)

    def delete_profile(self, name: str):
        """删除浏览器配置文件"""
        self.profile_manager.delete_profile(name)

    def list_profiles(self) -> dict:
        """列出所有配置文件"""
        return self.profile_manager.list_profiles()

    def get_all_profiles(self) -> dict:
        """获取所有配置文件（list_profiles的别名）"""
        return self.list_profiles()

    def launch_browser(self, profile_name: str):
        """启动指定配置的浏览器"""
        try:
            profile = self.profile_manager.get_profile(profile_name)
            if not profile:
                raise ValueError(f"Profile {profile_name} not found")
            
            if profile.is_running:
                logger.warning(f"Browser {profile_name} is already running")
                return profile.driver
                
            logger.info(f"Launching browser with profile: {profile_name}")
            
            options = uc.ChromeOptions()
            
            # 设置代理
            if profile.proxy:
                logger.info(f"Setting proxy: {profile.proxy}")
                try:
                    options.add_argument(f'--proxy-server={profile.proxy}')
                except Exception as e:
                    logger.error(f"Failed to set proxy: {str(e)}")
                    raise
            
            # 设置时区
            if profile.timezone:
                options.add_argument(f'--timezone={profile.timezone}')
            
            # 设置地理位置
            if profile.geolocation:
                lat = profile.geolocation.get('latitude')
                lng = profile.geolocation.get('longitude')
                if lat is not None and lng is not None:
                    options.add_argument(f'--geolocation-override={lat},{lng}')
            
            # WebRTC 设置
            if profile.webrtc == "disable":
                options.add_argument('--disable-webrtc')
            elif profile.webrtc == "only public ip":
                options.add_argument('--force-webrtc-ip-handling-policy=default_public_interface_only')
            
            # 指纹保护设置
            if profile.canvas_fp:
                options.add_argument('--disable-reading-from-canvas')
            
            if profile.webgl_fp:
                options.add_argument('--disable-webgl')
                options.add_argument('--disable-webgl2')
                
            if profile.audio_fp:
                options.add_argument('--disable-audio-input')
                options.add_argument('--disable-audio-output')
                
            if profile.client_rects_fp:
                options.add_argument('--disable-client-rects')
            
            # 启动浏览器
            try:
                # 添加必要的启动参数
                options.add_argument('--no-sandbox')
                options.add_argument('--disable-dev-shm-usage')
                
                driver = uc.Chrome(options=options)
                profile.driver = driver
                profile.is_running = True
                self.profile_manager.save_profiles()  # 使用正确的方法名
                logger.info(f"Browser launched successfully: {profile_name}")
                return driver
            except Exception as e:
                logger.error(f"Failed to launch browser: {str(e)}")
                profile.is_running = False
                profile.driver = None
                self.profile_manager.save_profiles()  # 使用正确的方法名
                raise
                
        except Exception as e:
            logger.error(f"Error launching browser: {str(e)}")
            raise

    def close_browser(self, profile_name: str):
        """关闭指定的浏览器"""
        try:
            profile = self.profile_manager.get_profile(profile_name)
            if not profile:
                raise ValueError(f"Profile {profile_name} not found")
            
            if not profile.is_running:
                logger.warning(f"Browser {profile_name} is not running")
                return
                
            logger.info(f"Closing browser: {profile_name}")
            
            try:
                if profile.driver:
                    profile.driver.quit()
            except Exception as e:
                logger.error(f"Error while closing browser: {str(e)}")
            finally:
                profile.driver = None
                profile.is_running = False
                self.profile_manager.save_profiles()  # 修复方法名
                logger.info(f"Browser closed: {profile_name}")
                
        except Exception as e:
            logger.error(f"Error closing browser: {str(e)}")
            raise

    def _generate_user_agent(self, platform: str, browser: str) -> str:
        """生成指定平台和浏览器的User Agent"""
        chrome_version = "119.0.0.0"
        firefox_version = "119.0"
        
        platform_info = {
            "Windows": ("Windows NT 10.0; Win64; x64", "Windows"),
            "MacOS": ("Macintosh; Intel Mac OS X 10_15_7", "Mac"),
            "Linux": ("X11; Linux x86_64", "Linux")
        }
        
        if browser.startswith("Chrome"):
            os_info, _ = platform_info[platform]
            return f"Mozilla/5.0 ({os_info}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{chrome_version} Safari/537.36"
        elif browser.startswith("Firefox"):
            os_info, os_name = platform_info[platform]
            return f"Mozilla/5.0 ({os_info}; rv:{firefox_version}) Gecko/20100101 Firefox/{firefox_version}"
        elif browser == "Safari 17":
            return "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
        elif browser == "Edge 119":
            os_info, _ = platform_info[platform]
            return f"Mozilla/5.0 ({os_info}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{chrome_version} Safari/537.36 Edg/119.0.0.0"
        
        # 默认返回Chrome UA
        os_info, _ = platform_info[platform]
        return f"Mozilla/5.0 ({os_info}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{chrome_version} Safari/537.36"

    def is_profile_running(self, profile_name: str) -> bool:
        """检查指定配置的浏览器是否正在运行"""
        profile = self.profile_manager.get_profile(profile_name)
        return profile and profile.is_running
