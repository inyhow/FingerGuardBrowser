from PyQt5.QtWidgets import (QMainWindow, QTabWidget, QToolBar, 
                               QLineEdit, QPushButton, QVBoxLayout, QWidget,
                               QComboBox, QLabel, QHBoxLayout)
from PyQt5.QtCore import QUrl, Qt
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage, QWebEngineProfile
from loguru import logger
import os
from src.fingerprint.fingerprint_manager import FingerprintManager

class BrowserTab(QWebEngineView):
    def __init__(self, profile=None, fingerprint_manager=None, fingerprint_name="default"):
        super().__init__()
        self.fingerprint_manager = fingerprint_manager
        self.fingerprint_name = fingerprint_name
        
        if profile:
            page = QWebEnginePage(profile, self)
            self.setPage(page)
        
        # 设置页面加载完成回调
        self.loadFinished.connect(self._on_load_finished)
        
    def _on_load_finished(self, ok):
        if ok and self.fingerprint_manager:
            # 加载指纹配置
            fingerprint = self.fingerprint_manager.load_fingerprint(self.fingerprint_name)
            # 注入指纹保护脚本
            self.page().runJavaScript(self.fingerprint_manager.get_injection_script(fingerprint))

class BrowserWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Virtual Browser")
        self.setGeometry(100, 100, 1024, 768)
        
        # 初始化指纹管理器
        self.fingerprint_manager = FingerprintManager()
        
        # 创建自定义配置文件
        self.profile = QWebEngineProfile("browser_profile")
        self.setup_profile()
        
        # 创建中心部件
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)
        
        # 创建工具栏
        self.create_toolbar()
        
        # 创建指纹选择器
        self.create_fingerprint_selector()
        
        # 创建标签页
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.layout.addWidget(self.tabs)
        
        # 添加新标签页
        self.add_new_tab()
    
    def setup_profile(self):
        # 禁用持久化Cookie
        self.profile.setPersistentCookiesPolicy(QWebEngineProfile.NoPersistentCookies)
        
        # 设置缓存路径
        cache_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "cache")
        os.makedirs(cache_path, exist_ok=True)
        self.profile.setCachePath(cache_path)
    
    def create_fingerprint_selector(self):
        """创建指纹选择器"""
        fingerprint_layout = QHBoxLayout()
        
        # 指纹选择下拉框
        fingerprint_label = QLabel("Fingerprint:")
        self.fingerprint_combo = QComboBox()
        self.update_fingerprint_list()
        
        # 新建指纹按钮
        new_fingerprint_btn = QPushButton("New")
        new_fingerprint_btn.clicked.connect(self.create_new_fingerprint)
        
        fingerprint_layout.addWidget(fingerprint_label)
        fingerprint_layout.addWidget(self.fingerprint_combo)
        fingerprint_layout.addWidget(new_fingerprint_btn)
        fingerprint_layout.addStretch()
        
        self.layout.addLayout(fingerprint_layout)
    
    def update_fingerprint_list(self):
        """更新指纹列表"""
        self.fingerprint_combo.clear()
        for file in os.listdir(self.fingerprint_manager.fingerprints_dir):
            if file.endswith('.json'):
                name = file[:-5]  # 移除.json后缀
                self.fingerprint_combo.addItem(name)
    
    def create_new_fingerprint(self):
        """创建新的指纹配置"""
        # 生成新的指纹名称
        index = 1
        while True:
            name = f"fingerprint_{index}"
            if not os.path.exists(os.path.join(self.fingerprint_manager.fingerprints_dir, f"{name}.json")):
                break
            index += 1
        
        # 创建新指纹
        self.fingerprint_manager.create_fingerprint(name)
        self.update_fingerprint_list()
        self.fingerprint_combo.setCurrentText(name)
    
    def create_toolbar(self):
        navigation_bar = QToolBar()
        self.addToolBar(navigation_bar)
        
        # 后退按钮
        back_btn = QPushButton("←")
        back_btn.clicked.connect(lambda: self.tabs.currentWidget().back())
        navigation_bar.addWidget(back_btn)
        
        # 前进按钮
        forward_btn = QPushButton("→")
        forward_btn.clicked.connect(lambda: self.tabs.currentWidget().forward())
        navigation_bar.addWidget(forward_btn)
        
        # 刷新按钮
        reload_btn = QPushButton("↻")
        reload_btn.clicked.connect(lambda: self.tabs.currentWidget().reload())
        navigation_bar.addWidget(reload_btn)
        
        # 地址栏
        self.url_bar = QLineEdit()
        self.url_bar.returnPressed.connect(self.navigate_to_url)
        navigation_bar.addWidget(self.url_bar)
        
        # 新标签页按钮
        new_tab_btn = QPushButton("+")
        new_tab_btn.clicked.connect(self.add_new_tab)
        navigation_bar.addWidget(new_tab_btn)
    
    def add_new_tab(self, url=None):
        """添加新标签页"""
        current_fingerprint = self.fingerprint_combo.currentText() or "default"
        browser = BrowserTab(
            self.profile,
            fingerprint_manager=self.fingerprint_manager,
            fingerprint_name=current_fingerprint
        )
        
        if url:
            browser.setUrl(QUrl(url))
        else:
            browser.setUrl(QUrl("https://www.google.com"))
        
        i = self.tabs.addTab(browser, "New Tab")
        self.tabs.setCurrentIndex(i)
        
        # 连接信号
        browser.titleChanged.connect(lambda title: self.update_tab_title(browser, title))
        browser.urlChanged.connect(lambda url: self.url_bar.setText(url.toString()))
    
    def update_tab_title(self, browser, title):
        """更新标签页标题"""
        index = self.tabs.indexOf(browser)
        if index >= 0:
            self.tabs.setTabText(index, title)
    
    def close_tab(self, index):
        """关闭标签页"""
        if self.tabs.count() > 1:
            self.tabs.removeTab(index)
        else:
            self.close()
    
    def navigate_to_url(self):
        """导航到URL"""
        url = self.url_bar.text()
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        self.tabs.currentWidget().setUrl(QUrl(url))
    
    def closeEvent(self, event):
        """关闭窗口事件"""
        # 清理缓存
        self.profile.clearAllVisitedLinks()
        self.profile.clearHttpCache()
        event.accept()
