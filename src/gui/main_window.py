import flet as ft
import os
from src.browser.core import FingerGuardBrowser
from src.fingerprint.manager import FingerprintManager
from .fingerprint_editor import FingerprintEditor
from .proxy_manager import ProxyManager

class BrowserTab:
    def __init__(self, browser: FingerGuardBrowser, url: str = ""):
        self.browser = browser
        self.url = url
        self.title = "New Tab"

class MainWindow:
    def __init__(self, page: ft.Page):
        self.page = page
        self.page.title = "FingerGuard Browser"
        self.page.theme_mode = ft.ThemeMode.DARK
        self.page.window_width = 1200
        self.page.window_height = 800
        self.page.window_resizable = True
        self.browser = None
        self.current_browser = None
        
        # 初始化UI组件
        self.init_components()
        self.init_layout()
        
    def init_components(self):
        """初始化所有UI组件"""
        def page_resize(e):
            self.content_column.height = self.page.window_height - 100
            self.content_column.update()
            
        self.page.on_resize = page_resize
        
        # 配置部分
        self.profile_input = ft.TextField(
            label="Profile Name",
            width=200,
            height=35
        )
        
        self.fingerprint_input = ft.TextField(
            label="Fingerprint Name",
            width=200,
            height=35
        )
        
        self.edit_fingerprint_button = ft.IconButton(
            icon=ft.icons.EDIT,
            tooltip="Edit Fingerprint",
            on_click=lambda _: self.show_fingerprint_editor()
        )
        
        self.proxy_input = ft.TextField(
            label="Proxy",
            width=200,
            height=35
        )
        
        self.edit_proxy_button = ft.IconButton(
            icon=ft.icons.LIST,
            tooltip="Manage Proxies",
            on_click=lambda _: self.show_proxy_manager()
        )
        
        # 浏览器控制按钮
        self.start_button = ft.ElevatedButton(
            text="Start Browser",
            on_click=lambda _: self.create_browser(),
            style=ft.ButtonStyle(
                color=ft.colors.WHITE,
                bgcolor=ft.colors.GREEN
            )
        )
        
        self.close_button = ft.ElevatedButton(
            text="Close Browser",
            on_click=lambda _: self.close_browser(),
            disabled=True,
            style=ft.ButtonStyle(
                color=ft.colors.WHITE,
                bgcolor=ft.colors.RED_700
            )
        )
        
        # 导航部分
        self.url_input = ft.TextField(
            label="URL",
            width=400,
            height=35
        )
        
        self.navigate_button = ft.ElevatedButton(
            text="Navigate",
            on_click=lambda _: self.navigate()
        )
        
        # 标签页控制
        self.new_tab_button = ft.IconButton(
            icon=ft.icons.ADD,
            tooltip="New Tab",
            on_click=lambda _: self.create_tab()
        )
        
        self.close_tab_button = ft.IconButton(
            icon=ft.icons.CLOSE,
            tooltip="Close Tab",
            on_click=lambda _: self.close_tab()
        )
        
        # 状态显示
        self.status_text = ft.Text(
            value="Ready",
            color=ft.colors.GREEN
        )
    
    def init_layout(self):
        """初始化UI布局"""
        # 配置行
        self.config_row = ft.Row(
            controls=[
                self.profile_input,
                ft.Column([
                    ft.Row([
                        self.fingerprint_input,
                        self.edit_fingerprint_button
                    ]),
                    ft.Row([
                        self.proxy_input,
                        self.edit_proxy_button
                    ])
                ]),
                ft.Column([
                    self.start_button,
                    self.close_button
                ])
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN
        )
        
        # 导航行
        self.navigation_row = ft.Row(
            controls=[
                self.new_tab_button,
                self.close_tab_button,
                self.url_input,
                self.navigate_button
            ]
        )
        
        # 主内容列
        self.content_column = ft.Column(
            controls=[
                self.config_row,
                ft.Divider(),
                self.navigation_row,
                ft.Divider(),
                self.status_text
            ],
            spacing=20,
            scroll=ft.ScrollMode.AUTO
        )
        
        self.page.add(self.content_column)
        self.page.update()
    
    def create_browser(self):
        """创建并启动浏览器"""
        try:
            profile_name = self.profile_input.value or "default"
            fingerprint_name = self.fingerprint_input.value or "default"
            proxy = self.proxy_input.value
            
            browser = FingerGuardBrowser(
                profile_name=profile_name,
                fingerprint_name=fingerprint_name,
                proxy=proxy
            )
            browser.start()  # 启动浏览器
            self.current_browser = browser
            self.status_text.value = "Browser started successfully"
            self.status_text.color = ft.colors.GREEN
            self.start_button.disabled = True
            self.close_button.disabled = False
            self.page.update()
            
        except Exception as e:
            self.status_text.value = f"Error starting browser: {str(e)}"
            self.status_text.color = ft.colors.RED
            self.page.update()
    
    def close_browser(self):
        """关闭浏览器"""
        if self.current_browser:
            try:
                self.current_browser.close()
                self.current_browser = None
                self.status_text.value = "Browser closed"
                self.status_text.color = ft.colors.GREEN
                self.start_button.disabled = False
                self.close_button.disabled = True
                self.page.update()
            except Exception as e:
                self.status_text.value = f"Error closing browser: {str(e)}"
                self.status_text.color = ft.colors.RED
                self.page.update()
    
    def navigate(self):
        """导航到指定URL"""
        if self.current_browser and self.url_input.value:
            try:
                self.current_browser.navigate(self.url_input.value)
                self.status_text.value = f"Navigated to {self.url_input.value}"
                self.status_text.color = ft.colors.GREEN
            except Exception as e:
                self.status_text.value = f"Error navigating: {str(e)}"
                self.status_text.color = ft.colors.RED
            self.page.update()
    
    def show_fingerprint_editor(self):
        """显示指纹编辑器"""
        editor = FingerprintEditor()
        dialog = editor.build_dialog(self.page, self.fingerprint_input.value or "default")
        self.page.dialog = dialog
        dialog.open = True
        self.page.update()
    
    def show_proxy_manager(self):
        """显示代理管理器"""
        manager = ProxyManager()
        dialog = manager.build_dialog(self.page)
        self.page.dialog = dialog
        dialog.open = True
        self.page.update()
    
    def create_tab(self):
        """创建新标签页"""
        if self.current_browser:
            try:
                self.current_browser.new_tab()
                self.status_text.value = "New tab created"
                self.status_text.color = ft.colors.GREEN
            except Exception as e:
                self.status_text.value = f"Error creating tab: {str(e)}"
                self.status_text.color = ft.colors.RED
            self.page.update()
    
    def close_tab(self):
        """关闭当前标签页"""
        if self.current_browser:
            try:
                self.current_browser.close_tab()
                self.status_text.value = "Tab closed"
                self.status_text.color = ft.colors.GREEN
            except Exception as e:
                self.status_text.value = f"Error closing tab: {str(e)}"
                self.status_text.color = ft.colors.RED
            self.page.update()
    
    def init_ui(self):
        pass

ft.app(target=lambda page: MainWindow(page))
