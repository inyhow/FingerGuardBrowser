import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.browser.core import FingerGuardBrowser
from src.fingerprint.manager import FingerprintManager
from loguru import logger
import time

def main():
    # Chrome浏览器路径
    chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    
    # 创建浏览器实例
    browser = FingerGuardBrowser(
        profile_name="profile1",  # 可选：使用指定的配置文件
        proxy=None,  # 可选：使用代理
        headless=False,  # 是否使用无头模式
        chrome_path=chrome_path  # 指定Chrome路径
    )
    
    try:
        # 启动浏览器
        driver = browser.start()
        
        # 创建指纹管理器
        fingerprint_manager = FingerprintManager(driver)
        
        # 加载指纹配置
        fingerprint_file = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "src", "fingerprint", "fingerprints", "default.json"
        )
        fingerprint_manager.load_fingerprint(fingerprint_file)
        
        # 访问测试网站
        browser.get_page("https://bot.sannysoft.com")  # 一个用于测试浏览器指纹的网站
        
        # 等待一段时间以查看结果
        time.sleep(30)
        
    except Exception as e:
        logger.error(f"Error occurred: {str(e)}")
    finally:
        # 关闭浏览器
        browser.quit()

if __name__ == "__main__":
    main()
