from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QListWidget, QListWidgetItem, QLabel, QInputDialog, 
                             QMessageBox, QDialog, QFormLayout, QLineEdit, 
                             QSpinBox, QComboBox, QTabWidget, QDoubleSpinBox, 
                             QCheckBox, QDialogButtonBox, QProgressDialog)
from PyQt5.QtCore import Qt, QSize, QTimer, QThread, pyqtSignal
from PyQt5.QtGui import QIcon, QFont
import json
import os
import pytz
from ..browser.browser_manager import BrowserManager
import random

class ProfileDialog(QDialog):
    def __init__(self, parent=None, profile=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Profile" if profile else "Create New Profile")
        self.setMinimumWidth(500)
        self.profile = profile
        self.init_ui()
        if profile:
            self.load_profile(profile)

    def init_ui(self):
        layout = QVBoxLayout()
        
        # Create tabs
        tabs = QTabWidget()
        
        # Basic Settings Tab
        basic_tab = QWidget()
        basic_layout = QFormLayout()
        
        self.name_edit = QLineEdit()
        self.proxy_edit = QLineEdit()
        self.proxy_edit.setPlaceholderText("e.g., socks5://127.0.0.1:1080")
        
        self.timezone_combo = QComboBox()
        self.timezone_combo.addItems(pytz.all_timezones)
        
        # DNS 保护设置
        self.dns_protection_combo = QComboBox()
        self.dns_protection_combo.addItems(['cloudflare', 'google', 'quad9', 'custom', 'disabled'])
        self.dns_protection_combo.currentTextChanged.connect(self.on_dns_protection_changed)
        
        self.custom_dns_edit = QLineEdit()
        self.custom_dns_edit.setPlaceholderText("e.g., https://your-dns-server/dns-query")
        self.custom_dns_edit.setEnabled(False)
        
        self.dns_leak_protection = QCheckBox("Enable DNS Leak Protection")
        self.dns_leak_protection.setChecked(True)
        
        basic_layout.addRow("Profile Name:", self.name_edit)
        basic_layout.addRow("Proxy (host:port):", self.proxy_edit)
        basic_layout.addRow("Timezone:", self.timezone_combo)
        basic_layout.addRow("DNS Protection:", self.dns_protection_combo)
        basic_layout.addRow("Custom DNS:", self.custom_dns_edit)
        basic_layout.addRow("", self.dns_leak_protection)
        
        basic_tab.setLayout(basic_layout)
        
        # Privacy Settings Tab
        privacy_tab = QWidget()
        privacy_layout = QFormLayout()
        
        self.webrtc_combo = QComboBox()
        self.webrtc_combo.addItems(["Default", "Disable", "Only Public IP", "Force Public & Private IP"])
        
        self.canvas_fp = QCheckBox("Enable Canvas Fingerprint Protection")
        self.webgl_fp = QCheckBox("Enable WebGL Fingerprint Protection")
        self.audio_fp = QCheckBox("Enable AudioContext Fingerprint Protection")
        self.client_rects_fp = QCheckBox("Enable Client Rects Fingerprint Protection")
        
        privacy_layout.addRow("WebRTC Policy:", self.webrtc_combo)
        privacy_layout.addRow(self.canvas_fp)
        privacy_layout.addRow(self.webgl_fp)
        privacy_layout.addRow(self.audio_fp)
        privacy_layout.addRow(self.client_rects_fp)
        
        privacy_tab.setLayout(privacy_layout)
        
        # Hardware Fingerprint Tab
        hardware_tab = QWidget()
        hw_layout = QFormLayout()
        
        self.cpu_cores = QSpinBox()
        self.cpu_cores.setRange(1, 32)
        self.cpu_cores.setValue(4)
        
        self.memory = QSpinBox()
        self.memory.setRange(1, 64)
        self.memory.setValue(8)
        self.memory.setSuffix(" GB")
        
        self.gpu_vendor = QComboBox()
        self.gpu_vendor.addItems(["NVIDIA", "AMD", "Intel"])
        
        self.screen_res = QComboBox()
        self.screen_res.addItems([
            "1920x1080",
            "2560x1440",
            "3840x2160",
            "1366x768",
            "1440x900"
        ])
        
        hw_layout.addRow("CPU Cores:", self.cpu_cores)
        hw_layout.addRow("Memory:", self.memory)
        hw_layout.addRow("GPU Vendor:", self.gpu_vendor)
        hw_layout.addRow("Screen Resolution:", self.screen_res)
        hardware_tab.setLayout(hw_layout)
        
        # Browser Identity Tab
        identity_tab = QWidget()
        identity_layout = QFormLayout()
        
        self.platform_combo = QComboBox()
        self.platform_combo.addItems(["Windows", "MacOS", "Linux"])
        
        self.browser_combo = QComboBox()
        self.browser_combo.addItems([
            "Chrome 119",
            "Chrome 118",
            "Firefox 119",
            "Firefox 118",
            "Safari 17",
            "Edge 119"
        ])
        
        self.language_combo = QComboBox()
        self.language_combo.addItems([
            "en-US",
            "zh-CN",
            "ja-JP",
            "ko-KR",
            "fr-FR",
            "de-DE"
        ])
        
        identity_layout.addRow("Platform:", self.platform_combo)
        identity_layout.addRow("Browser:", self.browser_combo)
        identity_layout.addRow("Language:", self.language_combo)
        identity_tab.setLayout(identity_layout)
        
        # Add all tabs
        tabs.addTab(basic_tab, "Basic")
        tabs.addTab(privacy_tab, "Privacy")
        tabs.addTab(hardware_tab, "Hardware")
        tabs.addTab(identity_tab, "Identity")
        
        layout.addWidget(tabs)
        
        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            Qt.Horizontal, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
        self.setLayout(layout)

    def on_dns_protection_changed(self, value):
        """DNS保护模式改变时的处理"""
        self.custom_dns_edit.setEnabled(value == 'custom')

    def load_profile(self, profile):
        """加载现有配置"""
        self.name_edit.setText(profile.name)
        self.proxy_edit.setText(profile.proxy or "")
        
        if profile.timezone:
            index = self.timezone_combo.findText(profile.timezone)
            if index >= 0:
                self.timezone_combo.setCurrentIndex(index)
        
        # 加载 DNS 设置
        index = self.dns_protection_combo.findText(profile.dns_protection)
        if index >= 0:
            self.dns_protection_combo.setCurrentIndex(index)
        self.custom_dns_edit.setText(profile.custom_dns)
        self.dns_leak_protection.setChecked(profile.dns_leak_protection)
        
        # 隐私设置
        index = self.webrtc_combo.findText(profile.webrtc)
        if index >= 0:
            self.webrtc_combo.setCurrentIndex(index)
            
        self.canvas_fp.setChecked(profile.canvas_fp)
        self.webgl_fp.setChecked(profile.webgl_fp)
        self.audio_fp.setChecked(profile.audio_fp)
        self.client_rects_fp.setChecked(profile.client_rects_fp)
        
        # 硬件指纹
        if profile.fingerprint:
            fp = profile.fingerprint
            if "hardware" in fp:
                hw = fp["hardware"]
                self.cpu_cores.setValue(hw.get("cpu_cores", 4))
                self.memory.setValue(hw.get("memory", 8))
                index = self.gpu_vendor.findText(hw.get("gpu_vendor", "NVIDIA"))
                if index >= 0:
                    self.gpu_vendor.setCurrentIndex(index)
                index = self.screen_res.findText(hw.get("screen_resolution", "1920x1080"))
                if index >= 0:
                    self.screen_res.setCurrentIndex(index)
            
            # 浏览器身份
            if "navigator" in fp:
                nav = fp["navigator"]
                platform = nav.get("platform", "Windows")
                index = self.platform_combo.findText(platform)
                if index >= 0:
                    self.platform_combo.setCurrentIndex(index)
                
                browser = nav.get("browser", "Chrome 119")
                index = self.browser_combo.findText(browser)
                if index >= 0:
                    self.browser_combo.setCurrentIndex(index)
                
                language = nav.get("language", "en-US")
                index = self.language_combo.findText(language)
                if index >= 0:
                    self.language_combo.setCurrentIndex(index)

    def get_profile_data(self) -> dict:
        """获取配置数据"""
        return {
            "proxy": self.proxy_edit.text(),
            "timezone": self.timezone_combo.currentText(),
            "webrtc": self.webrtc_combo.currentText(),
            "canvas_fp": self.canvas_fp.isChecked(),
            "webgl_fp": self.webgl_fp.isChecked(),
            "audio_fp": self.audio_fp.isChecked(),
            "client_rects_fp": self.client_rects_fp.isChecked(),
            "dns_protection": self.dns_protection_combo.currentText(),
            "custom_dns": self.custom_dns_edit.text(),
            "dns_leak_protection": self.dns_leak_protection.isChecked(),
            "fingerprint": {
                "hardware": {
                    "cpu_cores": self.cpu_cores.value(),
                    "memory": self.memory.value(),
                    "gpu_vendor": self.gpu_vendor.currentText(),
                    "screen_resolution": self.screen_res.currentText()
                },
                "navigator": {
                    "platform": self.platform_combo.currentText(),
                    "browser": self.browser_combo.currentText(),
                    "language": self.language_combo.currentText()
                }
            }
        }

class ProfileItemWidget(QWidget):
    def __init__(self, profile_name, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 2, 5, 2)
        
        # 配置名称标签
        self.name_label = QLabel(profile_name)
        self.name_label.setMinimumWidth(200)
        layout.addWidget(self.name_label)
        
        # 添加弹性空间
        layout.addStretch()
        
        # 启动/停止按钮
        self.toggle_button = QPushButton("Start")
        self.toggle_button.setFixedWidth(80)
        self.toggle_button.setStyleSheet('QPushButton { background-color: #51cf66; color: white; }')
        layout.addWidget(self.toggle_button)

    def update_button_state(self, is_running):
        if is_running:
            self.toggle_button.setText('Stop')
            self.toggle_button.setStyleSheet('QPushButton { background-color: #ff6b6b; color: white; }')
        else:
            self.toggle_button.setText('Start')
            self.toggle_button.setStyleSheet('QPushButton { background-color: #51cf66; color: white; }')

class BrowserLaunchThread(QThread):
    """浏览器启动线程"""
    finished = pyqtSignal(bool, str)  # 成功/失败, 错误信息

    def __init__(self, browser_manager, profile_name):
        super().__init__()
        self.browser_manager = browser_manager
        self.profile_name = profile_name

    def run(self):
        try:
            self.browser_manager.launch_browser(self.profile_name)
            self.finished.emit(True, "")
        except Exception as e:
            self.finished.emit(False, str(e))

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.browser_manager = BrowserManager()
        self.profile_widgets = {}  # 存储配置文件对应的小部件
        self.launch_thread = None  # 浏览器启动线程
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle('FingerGuard Browser')
        self.setMinimumWidth(600)
        
        central_widget = QWidget()
        layout = QVBoxLayout()
        
        # 配置文件列表
        list_widget = QWidget()
        list_layout = QVBoxLayout()
        
        # 标题行
        title_widget = QWidget()
        title_layout = QHBoxLayout(title_widget)
        title_layout.setContentsMargins(10, 5, 10, 5)
        
        profile_title = QLabel("Browser Profiles")
        profile_title.setStyleSheet("font-weight: bold;")
        title_layout.addWidget(profile_title)
        title_layout.addStretch()
        
        list_layout.addWidget(title_widget)
        
        # 配置文件列表
        self.profile_list = QListWidget()
        self.profile_list.setMinimumWidth(400)
        list_layout.addWidget(self.profile_list)
        
        # 底部按钮
        button_layout = QHBoxLayout()
        
        create_btn = QPushButton('Create')
        create_btn.clicked.connect(self.create_profile)
        
        edit_btn = QPushButton('Edit')
        edit_btn.clicked.connect(self.edit_profile)
        
        delete_btn = QPushButton('Delete')
        delete_btn.clicked.connect(self.delete_profile)
        
        button_layout.addWidget(create_btn)
        button_layout.addWidget(edit_btn)
        button_layout.addWidget(delete_btn)
        button_layout.addStretch()
        
        list_layout.addLayout(button_layout)
        
        list_widget.setLayout(list_layout)
        layout.addWidget(list_widget)
        
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)
        
        # 加载配置文件
        self.load_profiles()
        
        # 设置定时器更新状态
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_profile_states)
        self.status_timer.start(1000)  # 每秒更新一次状态

    def load_profiles(self):
        """加载所有浏览器配置到列表中"""
        self.profile_list.clear()
        self.profile_widgets.clear()
        
        profiles = self.browser_manager.get_all_profiles()
        for name in profiles:
            # 创建列表项
            item = QListWidgetItem()
            self.profile_list.addItem(item)
            
            # 创建自定义小部件
            widget = ProfileItemWidget(name)
            widget.toggle_button.clicked.connect(lambda checked, n=name: self.toggle_browser(n))
            
            # 设置项目大小
            item.setSizeHint(widget.sizeHint())
            
            # 将小部件设置到列表项
            self.profile_list.setItemWidget(item, widget)
            self.profile_widgets[name] = widget
            
            # 更新按钮状态
            profile = self.browser_manager.get_profile(name)
            widget.update_button_state(profile.is_running)

    def update_profile_states(self):
        """更新所有配置文件的状态"""
        for name, widget in self.profile_widgets.items():
            profile = self.browser_manager.get_profile(name)
            if profile:
                widget.update_button_state(profile.is_running)

    def toggle_browser(self, profile_name):
        """切换浏览器启动/关闭状态"""
        try:
            profile = self.browser_manager.get_profile(profile_name)
            if profile.is_running:
                self.browser_manager.close_browser(profile_name)
                self.update_profile_states()
            else:
                # 显示进度对话框
                self.progress = QProgressDialog("Starting browser...", None, 0, 0, self)
                self.progress.setWindowTitle("Please Wait")
                self.progress.setWindowModality(Qt.WindowModal)
                self.progress.setCancelButton(None)  # 禁用取消按钮
                self.progress.show()

                # 创建并启动线程
                self.launch_thread = BrowserLaunchThread(self.browser_manager, profile_name)
                self.launch_thread.finished.connect(self.on_browser_launch_finished)
                self.launch_thread.start()

        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))

    def on_browser_launch_finished(self, success, error_msg):
        """浏览器启动完成的回调"""
        self.progress.close()
        if not success:
            QMessageBox.warning(self, "Error", error_msg)
        self.update_profile_states()
        self.launch_thread = None

    def edit_profile(self):
        """编辑配置文件"""
        current_item = self.profile_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "提示", "请先选择要编辑的配置")
            return
            
        # 获取当前选中的配置名称
        widget = self.profile_list.itemWidget(current_item)
        if not widget or not isinstance(widget, ProfileItemWidget):
            return
            
        profile_name = widget.name_label.text()
        profile = self.browser_manager.get_profile(profile_name)
        
        if not profile:
            QMessageBox.warning(self, "错误", f"找不到配置: {profile_name}")
            return
            
        dialog = ProfileDialog(self, profile)
        if dialog.exec_() == QDialog.Accepted:
            try:
                data = dialog.get_profile_data()
                self.browser_manager.update_profile(
                    name=profile_name,
                    **data
                )
                self.load_profiles()
            except Exception as e:
                QMessageBox.warning(self, "错误", str(e))

    def create_profile(self):
        """创建新的浏览器配置"""
        dialog = ProfileDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_profile_data()
            try:
                self.browser_manager.create_profile(
                    name=self.name_edit.text(),
                    fingerprint=data["fingerprint"],
                    proxy=data["proxy"],
                    timezone=data["timezone"],
                    webrtc=data["webrtc"],
                    canvas_fp=data["canvas_fp"],
                    webgl_fp=data["webgl_fp"],
                    audio_fp=data["audio_fp"],
                    client_rects_fp=data["client_rects_fp"],
                    dns_protection=data["dns_protection"],
                    custom_dns=data["custom_dns"],
                    dns_leak_protection=data["dns_leak_protection"],
                )
                self.load_profiles()
            except ValueError as e:
                QMessageBox.warning(self, "错误", str(e))
                
    def delete_profile(self):
        """删除选中的浏览器配置"""
        current_item = self.profile_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "提示", "请先选择要删除的配置")
            return
            
        # 获取当前选中的配置名称
        widget = self.profile_list.itemWidget(current_item)
        if not widget or not isinstance(widget, ProfileItemWidget):
            return
            
        profile_name = widget.name_label.text()
        
        reply = QMessageBox.question(
            self, 
            '确认删除', 
            f'确定要删除配置 "{profile_name}" 吗？',
            QMessageBox.Yes | QMessageBox.No, 
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                # 如果浏览器正在运行，先关闭它
                if self.browser_manager.is_profile_running(profile_name):
                    self.browser_manager.close_browser(profile_name)
                
                # 删除配置文件
                self.browser_manager.delete_profile(profile_name)
                
                # 重新加载配置列表
                self.load_profiles()
                
                QMessageBox.information(self, "成功", f"配置 {profile_name} 已删除")
            except Exception as e:
                QMessageBox.warning(self, "错误", f"删除配置失败: {str(e)}")
            
    def launch_profile(self, item):
        """启动选中的浏览器配置"""
        profile_name = item.text()
        if self.browser_manager.is_profile_running(profile_name):
            QMessageBox.information(self, "提示", f"浏览器 {profile_name} 已经在运行")
            return
            
        driver = self.browser_manager.launch_browser(profile_name)
        if driver:
            self.update_running_list()
        else:
            QMessageBox.warning(self, "错误", f"启动浏览器 {profile_name} 失败")
            
    def close_browser(self):
        """关闭选中的浏览器"""
        current_item = self.running_list.currentItem()
        if current_item is None:
            return
            
        profile_name = current_item.text()
        self.browser_manager.close_browser(profile_name)
        self.update_running_list()
        
    def update_running_list(self):
        """更新运行中的浏览器列表"""
        self.running_list.clear()
        profiles = self.browser_manager.get_all_profiles()
        for name, profile in profiles.items():
            if profile.is_running:
                self.running_list.addItem(name)
                
    def closeEvent(self, event):
        """关闭窗口时关闭所有浏览器"""
        profiles = self.browser_manager.get_all_profiles()
        for name in profiles:
            self.browser_manager.close_browser(name)
        event.accept()
