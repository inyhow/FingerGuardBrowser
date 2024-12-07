import json
import os
from dataclasses import dataclass, field
from typing import Dict, Any, Optional

@dataclass
class BrowserProfile:
    """浏览器配置文件类"""
    name: str
    proxy: Optional[str] = None
    timezone: Optional[str] = None
    geolocation: Optional[Dict[str, float]] = None
    webrtc: str = "disable"  # disable, only public ip, force public & private ip
    canvas_fp: bool = True
    webgl_fp: bool = True
    audio_fp: bool = True
    client_rects_fp: bool = True
    dns_protection: str = "cloudflare"  # cloudflare, google, quad9, custom, disabled
    custom_dns: str = ""  # 自定义 DNS over HTTPS 服务器
    dns_leak_protection: bool = True
    fingerprint: Dict[str, Any] = field(default_factory=dict)
    is_running: bool = False
    driver: Any = None

    def __post_init__(self):
        if self.fingerprint is None:
            self.fingerprint = {}

    def to_dict(self) -> dict:
        """转换为字典格式"""
        data = {
            'name': self.name,
            'proxy': self.proxy,
            'timezone': self.timezone,
            'geolocation': self.geolocation,
            'webrtc': self.webrtc,
            'canvas_fp': self.canvas_fp,
            'webgl_fp': self.webgl_fp,
            'audio_fp': self.audio_fp,
            'client_rects_fp': self.client_rects_fp,
            'dns_protection': self.dns_protection,
            'custom_dns': self.custom_dns,
            'dns_leak_protection': self.dns_leak_protection,
            'fingerprint': self.fingerprint
        }
        return data

    @classmethod
    def from_dict(cls, name: str, data: dict) -> 'BrowserProfile':
        """从字典创建配置文件"""
        return cls(
            name=name,
            proxy=data.get('proxy'),
            timezone=data.get('timezone'),
            geolocation=data.get('geolocation'),
            webrtc=data.get('webrtc', "disable"),
            canvas_fp=data.get('canvas_fp', True),
            webgl_fp=data.get('webgl_fp', True),
            audio_fp=data.get('audio_fp', True),
            client_rects_fp=data.get('client_rects_fp', True),
            dns_protection=data.get('dns_protection', "cloudflare"),
            custom_dns=data.get('custom_dns', ""),
            dns_leak_protection=data.get('dns_leak_protection', True),
            fingerprint=data.get('fingerprint', {})
        )

class ProfileManager:
    """配置文件管理器"""
    def __init__(self, config_dir: str):
        self.config_dir = config_dir
        self.profiles_file = os.path.join(config_dir, "profiles.json")
        self.profiles: Dict[str, BrowserProfile] = {}
        self._load_profiles()

    def _load_profiles(self):
        """从文件加载配置文件"""
        if os.path.exists(self.profiles_file):
            with open(self.profiles_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for name, profile_data in data.items():
                    self.profiles[name] = BrowserProfile.from_dict(name, profile_data)

    def save_profiles(self):
        """保存配置文件到磁盘"""
        data = {name: profile.to_dict() for name, profile in self.profiles.items()}
        with open(self.profiles_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

    def create_profile(self, name: str, **kwargs) -> BrowserProfile:
        """创建新的配置文件"""
        if name in self.profiles:
            raise ValueError(f"Profile {name} already exists")
        profile = BrowserProfile(name=name, **kwargs)
        self.profiles[name] = profile
        self.save_profiles()
        return profile

    def get_profile(self, name: str) -> Optional[BrowserProfile]:
        """获取配置文件"""
        return self.profiles.get(name)

    def update_profile(self, name: str, **kwargs) -> BrowserProfile:
        """更新配置文件"""
        if name not in self.profiles:
            raise ValueError(f"Profile {name} not found")
        profile = self.profiles[name]
        for key, value in kwargs.items():
            if hasattr(profile, key):
                setattr(profile, key, value)
        self.save_profiles()
        return profile

    def delete_profile(self, name: str):
        """删除配置文件"""
        if name in self.profiles:
            del self.profiles[name]
            self.save_profiles()

    def list_profiles(self) -> Dict[str, BrowserProfile]:
        """列出所有配置文件"""
        return self.profiles
