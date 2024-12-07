import undetected_chromedriver as uc
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium_stealth import stealth
from webdriver_manager.chrome import ChromeDriverManager
import os
import json
from loguru import logger

class FingerGuardBrowser:
    def __init__(self, profile_name: str = "default", fingerprint_name: str = "default", proxy: str = None):
        self.profile_name = profile_name
        self.fingerprint_name = fingerprint_name
        self.proxy = proxy
        self.driver = None
        self.tabs = []
        self.current_tab_index = -1
        
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
        
        # 增强的WebRTC和网络保护设置
        options.add_argument("--disable-webrtc")  # 完全禁用WebRTC
        options.add_argument("--disable-webrtc-hw-encoding")  # 禁用WebRTC硬件编码
        options.add_argument("--disable-webrtc-hw-decoding")  # 禁用WebRTC硬件解码
        options.add_argument("--disable-webrtc-multiple-routes")  # 禁用WebRTC多路由
        options.add_argument("--enforce-webrtc-ip-permission-check")  # 强制WebRTC IP权限检查
        options.add_argument("--force-webrtc-ip-handling-policy=disable")  # 完全禁用WebRTC IP处理
        options.add_argument("--disable-webrtc-hide-local-ips-with-mdns")  # 禁用mDNS
        
        # 网络隔离设置
        options.add_argument("--disable-site-isolation-trials")  # 禁用站点隔离试验
        options.add_argument("--disable-features=IsolateOrigins,site-per-process")  # 禁用源隔离
        options.add_argument("--disable-dev-shm-usage")  # 禁用/dev/shm使用
        options.add_argument("--disable-background-networking")  # 禁用后台网络
        options.add_argument("--disable-default-apps")  # 禁用默认应用
        options.add_argument("--disable-sync")  # 禁用同步
        options.add_argument("--disable-translate")  # 禁用翻译
        options.add_argument("--disable-domain-reliability")  # 禁用域名可靠性监控
        options.add_argument("--disable-client-side-phishing-detection")  # 禁用客户端网络钓鱼检测
        
        # DNS设置
        if self.proxy:
            options.add_argument(f"--proxy-server={self.proxy}")
            options.add_argument("--dns-over-https-enable")
            options.add_argument("--dns-over-https-templates=https://dns.google/dns-query")
            options.add_argument("--proxy-bypass-list=<-loopback>")
            # 强制所有连接通过代理
            options.add_argument("--proxy-pac-url=data:application/x-javascript,{}")
        else:
            options.add_argument("--dns-over-https-enable")
            options.add_argument("--dns-over-https-templates=https://dns.google/dns-query")
        
        return options
        
    def _inject_privacy_scripts(self):
        """注入隐私保护脚本"""
        privacy_script = """
        (function() {
            // 完全禁用WebRTC
            const disableWebRTC = () => {
                // 覆盖RTCPeerConnection
                const rtcConstructors = [
                    'RTCPeerConnection',
                    'webkitRTCPeerConnection',
                    'mozRTCPeerConnection',
                    'msRTCPeerConnection'
                ];
                
                rtcConstructors.forEach(constructor => {
                    if (window[constructor]) {
                        window[constructor] = function() {
                            throw new Error('WebRTC is disabled');
                        };
                    }
                });
                
                // 禁用getUserMedia
                if (navigator.mediaDevices) {
                    navigator.mediaDevices.getUserMedia = function() {
                        return new Promise((resolve, reject) => {
                            reject(new Error('getUserMedia is disabled'));
                        });
                    };
                }
                
                // 禁用getDisplayMedia
                if (navigator.mediaDevices) {
                    navigator.mediaDevices.getDisplayMedia = function() {
                        return new Promise((resolve, reject) => {
                            reject(new Error('getDisplayMedia is disabled'));
                        });
                    };
                }
            };
            
            // 禁用网络API
            const disableNetworkAPIs = () => {
                // 禁用WebSocket
                window.WebSocket = function() {
                    throw new Error('WebSocket is disabled');
                };
                
                // 禁用SharedWorker
                window.SharedWorker = function() {
                    throw new Error('SharedWorker is disabled');
                };
                
                // 禁用ServiceWorker
                if (navigator.serviceWorker) {
                    navigator.serviceWorker.register = function() {
                        return Promise.reject(new Error('ServiceWorker is disabled'));
                    };
                }
            };
            
            // 执行所有保护措施
            disableWebRTC();
            disableNetworkAPIs();
            
            // 定期检查和重新应用保护
            setInterval(() => {
                disableWebRTC();
                disableNetworkAPIs();
            }, 1000);
        })();
        """
        try:
            self.driver.execute_script(privacy_script)
        except Exception as e:
            logger.error(f"Failed to inject privacy scripts: {str(e)}")
            
    def start(self):
        """启动浏览器"""
        try:
            # 创建Chrome选项
            options = self._create_options()
            
            # 使用undetected_chromedriver直接启动，指定Chrome版本
            self.driver = uc.Chrome(
                options=options,
                driver_executable_path=None,
                browser_executable_path=None,
                version_main=130
            )
            
            # 应用stealth设置
            stealth(
                self.driver,
                languages=["en-US", "en"],
                vendor="Google Inc.",
                platform="Win32",
                webgl_vendor="Intel Inc.",
                renderer="Intel Iris OpenGL Engine",
                fix_hairline=True,
            )
            
            # 注入隐私保护脚本
            self._inject_privacy_scripts()
            
            # 创建第一个标签页
            self.new_tab()
            
            return self.driver
            
        except Exception as e:
            logger.error(f"Failed to start browser: {str(e)}")
            raise
            
    def new_tab(self):
        """创建新标签页"""
        if not self.driver:
            raise Exception("Browser not started")
            
        # 创建新标签页
        self.driver.execute_script("window.open('about:blank');")
        self.tabs.append(self.driver.window_handles[-1])
        self.current_tab_index = len(self.tabs) - 1
        
        # 切换到新标签页
        self.driver.switch_to.window(self.tabs[self.current_tab_index])
        
    def close_tab(self):
        """关闭当前标签页"""
        if not self.driver or not self.tabs:
            raise Exception("No tabs to close")
            
        # 关闭当前标签页
        self.driver.close()
        self.tabs.pop(self.current_tab_index)
        
        # 如果还有标签页，切换到最后一个
        if self.tabs:
            self.current_tab_index = len(self.tabs) - 1
            self.driver.switch_to.window(self.tabs[self.current_tab_index])
        else:
            self.current_tab_index = -1
            
    def switch_tab(self, index: int):
        """切换到指定标签页"""
        if not self.driver or not self.tabs:
            raise Exception("No tabs available")
            
        if 0 <= index < len(self.tabs):
            self.current_tab_index = index
            self.driver.switch_to.window(self.tabs[index])
        else:
            raise Exception("Invalid tab index")
            
    def navigate(self, url: str):
        """访问URL"""
        if not self.driver or not self.tabs:
            raise Exception("No tabs available")
            
        try:
            self.driver.get(url)
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
        except Exception as e:
            logger.error(f"Failed to navigate to {url}: {str(e)}")
            raise
            
    def close(self):
        """关闭浏览器"""
        if self.driver:
            try:
                self.driver.quit()
            finally:
                self.driver = None
                self.tabs = []
                self.current_tab_index = -1
