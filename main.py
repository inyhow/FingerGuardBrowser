#!/usr/bin/env python3
import sys
from PyQt5.QtWidgets import QApplication
from PyQt5.QtWebEngineWidgets import QWebEngineView
from src.ui.main_window import MainWindow
from src.utils.logger import setup_logger

if __name__ == "__main__":
    # 确保只有一个QApplication实例
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    # 设置应用名称和日志
    app.setApplicationName("FingerGuard Browser")
    setup_logger()
    
    # 创建并显示主窗口
    browser = MainWindow()
    browser.show()
    
    # 运行应用主循环
    sys.exit(app.exec_())
