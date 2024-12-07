import flet as ft
import json
import os
from typing import Optional, Dict, List, Callable

class ProxyManager:
    def __init__(self, on_save: Optional[Callable[[str, Dict[str, str]], None]] = None):
        self.on_save = on_save
        self.proxy_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "src", "proxies"
        )
        os.makedirs(self.proxy_dir, exist_ok=True)
        
    def load_proxies(self) -> List[Dict[str, str]]:
        """加载所有代理配置"""
        proxies = []
        try:
            with open(os.path.join(self.proxy_dir, "proxies.json"), 'r') as f:
                proxies = json.load(f)
        except:
            pass
        return proxies
    
    def save_proxies(self, proxies: List[Dict[str, str]]):
        """保存代理配置"""
        with open(os.path.join(self.proxy_dir, "proxies.json"), 'w') as f:
            json.dump(proxies, f, indent=4)
    
    def build_dialog(self, page: ft.Page):
        """构建代理管理器对话框"""
        dialog = ft.AlertDialog(
            title=ft.Text("Proxy Manager"),
            content=None
        )
        
        # 加载现有代理
        proxies = self.load_proxies()
        
        # 创建布局容器
        content = ft.Column(
            scroll=ft.ScrollMode.AUTO,
            height=500,
            width=400
        )
        
        # 代理列表
        proxy_list = ft.ListView(
            expand=1,
            spacing=10,
            padding=20,
            auto_scroll=True
        )
        
        def update_proxy_list():
            proxy_list.controls.clear()
            for proxy in proxies:
                proxy_list.controls.append(
                    ft.ListTile(
                        leading=ft.Icon(ft.icons.COMPUTER),
                        title=ft.Text(f"{proxy['name']} - {proxy['type']}"),
                        subtitle=ft.Text(proxy['address']),
                        trailing=ft.IconButton(
                            icon=ft.icons.DELETE,
                            on_click=lambda e, p=proxy: delete_proxy(p)
                        )
                    )
                )
            page.update()
        
        def add_proxy(e):
            if not name_field.value or not address_field.value:
                page.show_snack_bar(
                    ft.SnackBar(content=ft.Text("Please fill in all fields"))
                )
                return
                
            proxy = {
                "name": name_field.value,
                "type": proxy_type.value,
                "address": address_field.value,
                "username": username_field.value,
                "password": password_field.value
            }
            
            proxies.append(proxy)
            self.save_proxies(proxies)
            
            # 清空输入框
            name_field.value = ""
            address_field.value = ""
            username_field.value = ""
            password_field.value = ""
            
            update_proxy_list()
        
        def delete_proxy(proxy):
            proxies.remove(proxy)
            self.save_proxies(proxies)
            update_proxy_list()
        
        # 输入控件
        name_field = ft.TextField(
            label="Proxy Name",
            width=200
        )
        
        proxy_type = ft.Dropdown(
            label="Proxy Type",
            width=200,
            options=[
                ft.dropdown.Option("http"),
                ft.dropdown.Option("socks4"),
                ft.dropdown.Option("socks5")
            ],
            value="http"
        )
        
        address_field = ft.TextField(
            label="Address (host:port)",
            width=200
        )
        
        username_field = ft.TextField(
            label="Username (optional)",
            width=200
        )
        
        password_field = ft.TextField(
            label="Password (optional)",
            width=200,
            password=True
        )
        
        add_button = ft.ElevatedButton(
            text="Add Proxy",
            on_click=add_proxy
        )
        
        # 创建布局
        input_column = ft.Column(
            controls=[
                name_field,
                proxy_type,
                address_field,
                username_field,
                password_field,
                add_button
            ],
            spacing=10
        )
        
        # 添加所有控件到内容容器
        content.controls.extend([
            ft.Text("Add New Proxy", size=16, weight=ft.FontWeight.BOLD),
            input_column,
            ft.Divider(),
            ft.Text("Proxy List", size=16, weight=ft.FontWeight.BOLD),
            proxy_list
        ])
        
        # 设置对话框内容
        dialog.content = content
        
        dialog.actions = [
            ft.TextButton("Close", on_click=lambda e: self.close_dialog(e, dialog))
        ]
        
        # 更新代理列表
        update_proxy_list()
        
        return dialog
    
    def close_dialog(self, e, dialog: ft.AlertDialog):
        """关闭对话框"""
        dialog.open = False
        dialog.page.update()
