from loguru import logger
import sys
import os

def setup_logger():
    # 确保日志目录存在
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs")
    os.makedirs(log_dir, exist_ok=True)
    
    # 设置日志格式
    log_format = "{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}"
    
    # 移除默认处理程序
    logger.remove()
    
    # 添加控制台处理程序
    logger.add(sys.stderr, format=log_format, level="INFO")
    
    # 添加文件处理程序
    log_file = os.path.join(log_dir, "browser.log")
    logger.add(log_file, format=log_format, level="DEBUG", rotation="10 MB")
