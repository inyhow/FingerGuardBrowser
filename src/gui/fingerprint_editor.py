import flet as ft
import json
import os
from typing import Optional, Dict, Any, Callable

class FingerprintEditor:
    def __init__(self, on_save: Optional[Callable[[str, Dict[str, Any]], None]] = None):
        self.on_save = on_save
        self.fingerprint_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "src", "fingerprint", "fingerprints"
        )
        os.makedirs(self.fingerprint_dir, exist_ok=True)
        
    def load_fingerprint(self, name: str) -> Dict[str, Any]:
        """加载指纹配置"""
        try:
            with open(os.path.join(self.fingerprint_dir, f"{name}.json"), 'r') as f:
                return json.load(f)
        except:
            return {
                "userAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "navigator": {
                    "platform": "Win32",
                    "language": "en-US",
                    "languages": ["en-US", "en"],
                    "hardwareConcurrency": 8,
                    "deviceMemory": 8,
                    "vendor": "",
                    "vendorSub": "",
                    "productSub": "20030107",
                    "cookieEnabled": True
                },
                "screen": {
                    "width": 1920,
                    "height": 1080,
                    "colorDepth": 24,
                    "pixelDepth": 24
                },
                "timezone": "America/New_York",
                "webgl": {
                    "vendor": "Google Inc. (NVIDIA)",
                    "renderer": "ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0, D3D11)"
                }
            }
    
    def save_fingerprint(self, name: str, config: Dict[str, Any]):
        """保存指纹配置"""
        os.makedirs(self.fingerprint_dir, exist_ok=True)
        with open(os.path.join(self.fingerprint_dir, f"{name}.json"), 'w') as f:
            json.dump(config, f, indent=4)
        if self.on_save:
            self.on_save(name, config)
    
    def build_dialog(self, page: ft.Page, initial_name: str = "default"):
        """构建指纹编辑器对话框"""
        dialog = ft.AlertDialog(
            title=ft.Text("Fingerprint Editor"),
            content=None,  # 将在后面设置
            actions=[
                ft.TextButton("Save", on_click=lambda e: self.save_and_close(e, dialog, name_input.value, editor_tabs)),
                ft.TextButton("Cancel", on_click=lambda e: self.close_dialog(e, dialog))
            ],
        )
        
        # 加载初始配置
        config = self.load_fingerprint(initial_name)
        
        # 创建输入控件
        name_input = ft.TextField(
            label="Fingerprint Name",
            value=initial_name,
            width=300
        )
        
        # Navigator设置
        nav_fields = {
            "platform": ft.TextField(label="Platform", value=config["navigator"]["platform"]),
            "language": ft.TextField(label="Language", value=config["navigator"]["language"]),
            "hardwareConcurrency": ft.TextField(label="Hardware Concurrency", value=str(config["navigator"]["hardwareConcurrency"])),
            "deviceMemory": ft.TextField(label="Device Memory (GB)", value=str(config["navigator"]["deviceMemory"]))
        }
        
        nav_tab = ft.Column(
            controls=[
                ft.Text("Navigator Properties", size=16, weight=ft.FontWeight.BOLD),
                *nav_fields.values()
            ],
            scroll=ft.ScrollMode.AUTO
        )
        
        # Screen设置
        screen_fields = {
            "width": ft.TextField(label="Width", value=str(config["screen"]["width"])),
            "height": ft.TextField(label="Height", value=str(config["screen"]["height"])),
            "colorDepth": ft.TextField(label="Color Depth", value=str(config["screen"]["colorDepth"])),
            "pixelDepth": ft.TextField(label="Pixel Depth", value=str(config["screen"]["pixelDepth"]))
        }
        
        screen_tab = ft.Column(
            controls=[
                ft.Text("Screen Properties", size=16, weight=ft.FontWeight.BOLD),
                *screen_fields.values()
            ],
            scroll=ft.ScrollMode.AUTO
        )
        
        # WebGL设置
        webgl_fields = {
            "vendor": ft.TextField(label="Vendor", value=config["webgl"]["vendor"], width=400),
            "renderer": ft.TextField(label="Renderer", value=config["webgl"]["renderer"], width=400)
        }
        
        webgl_tab = ft.Column(
            controls=[
                ft.Text("WebGL Properties", size=16, weight=ft.FontWeight.BOLD),
                *webgl_fields.values()
            ],
            scroll=ft.ScrollMode.AUTO
        )
        
        # User-Agent设置
        ua_field = ft.TextField(
            label="User Agent",
            value=config["userAgent"],
            width=400,
            multiline=True
        )
        
        ua_tab = ft.Column(
            controls=[
                ft.Text("User Agent", size=16, weight=ft.FontWeight.BOLD),
                ua_field
            ],
            scroll=ft.ScrollMode.AUTO
        )
        
        # 时区设置
        timezone_field = ft.TextField(
            label="Timezone",
            value=config["timezone"],
            width=200
        )
        
        timezone_tab = ft.Column(
            controls=[
                ft.Text("Timezone", size=16, weight=ft.FontWeight.BOLD),
                timezone_field
            ],
            scroll=ft.ScrollMode.AUTO
        )
        
        # 创建标签页
        editor_tabs = ft.Tabs(
            selected_index=0,
            animation_duration=300,
            tabs=[
                ft.Tab(
                    text="Navigator",
                    content=nav_tab
                ),
                ft.Tab(
                    text="Screen",
                    content=screen_tab
                ),
                ft.Tab(
                    text="WebGL",
                    content=webgl_tab
                ),
                ft.Tab(
                    text="User Agent",
                    content=ua_tab
                ),
                ft.Tab(
                    text="Timezone",
                    content=timezone_tab
                )
            ]
        )
        
        # 创建内容容器
        content = ft.Column(
            controls=[
                name_input,
                ft.Divider(),
                editor_tabs
            ],
            scroll=ft.ScrollMode.AUTO,
            height=400,
            width=500
        )
        
        # 设置对话框内容
        dialog.content = content
        
        return dialog
    
    def save_and_close(self, e, dialog: ft.AlertDialog, name: str, tabs: ft.Tabs):
        """保存配置并关闭对话框"""
        try:
            # 收集所有输入的值
            config = {
                "navigator": {
                    "platform": tabs.tabs[0].content.controls[1].value,
                    "language": tabs.tabs[0].content.controls[2].value,
                    "languages": [tabs.tabs[0].content.controls[2].value, "en"],
                    "hardwareConcurrency": int(tabs.tabs[0].content.controls[3].value),
                    "deviceMemory": int(tabs.tabs[0].content.controls[4].value),
                    "vendor": "",
                    "vendorSub": "",
                    "productSub": "20030107",
                    "cookieEnabled": True
                },
                "screen": {
                    "width": int(tabs.tabs[1].content.controls[1].value),
                    "height": int(tabs.tabs[1].content.controls[2].value),
                    "colorDepth": int(tabs.tabs[1].content.controls[3].value),
                    "pixelDepth": int(tabs.tabs[1].content.controls[4].value)
                },
                "webgl": {
                    "vendor": tabs.tabs[2].content.controls[1].value,
                    "renderer": tabs.tabs[2].content.controls[2].value
                },
                "userAgent": tabs.tabs[3].content.controls[1].value,
                "timezone": tabs.tabs[4].content.controls[1].value
            }
            
            # 保存配置
            self.save_fingerprint(name, config)
            dialog.open = False
            dialog.page.update()
            
        except Exception as e:
            dialog.page.show_snack_bar(
                ft.SnackBar(content=ft.Text(f"Error saving fingerprint: {str(e)}"))
            )
    
    def close_dialog(self, e, dialog: ft.AlertDialog):
        """关闭对话框"""
        dialog.open = False
        dialog.page.update()
