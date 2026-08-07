"""Internationalization (i18n) support for FingerGuardBrowser.

Supports: English (en), Chinese (zh), Spanish (es).
Locale files are JSON dictionaries stored in src/utils/locales/.

Usage:
    from src.utils.i18n import _
    label = _("profiles.create")  # Returns translated string
"""

import json
import os
from typing import Dict, Optional
from loguru import logger


class I18n:
    """Internationalization manager with JSON-based locale files."""

    DEFAULT_LOCALE = "en"
    SUPPORTED_LOCALES = ["en", "zh", "es"]

    # Built-in translations (also written to locale files for extensibility)
    TRANSLATIONS = {
        "en": {
            "app.title": "FingerGuard Browser",
            "profiles.title": "Browser Profiles",
            "profiles.create": "Create",
            "profiles.edit": "Edit",
            "profiles.delete": "Delete",
            "profiles.start": "Start",
            "profiles.stop": "Stop",
            "profiles.name": "Profile Name",
            "profiles.proxy": "Proxy (host:port)",
            "profiles.timezone": "Timezone",
            "profiles.dns_protection": "DNS Protection",
            "profiles.custom_dns": "Custom DNS",
            "profiles.dns_leak": "Enable DNS Leak Protection",
            "profiles.webrtc": "WebRTC Policy",
            "profiles.canvas_fp": "Enable Canvas Fingerprint Protection",
            "profiles.webgl_fp": "Enable WebGL Fingerprint Protection",
            "profiles.audio_fp": "Enable AudioContext Fingerprint Protection",
            "profiles.client_rects_fp": "Enable Client Rects Fingerprint Protection",
            "profiles.cpu_cores": "CPU Cores",
            "profiles.memory": "Memory",
            "profiles.gpu_vendor": "GPU Vendor",
            "profiles.screen_res": "Screen Resolution",
            "profiles.platform": "Platform",
            "profiles.browser": "Browser",
            "profiles.language": "Language",
            "profiles.tags": "Tags",
            "profiles.group": "Group",
            "tabs.basic": "Basic",
            "tabs.privacy": "Privacy",
            "tabs.hardware": "Hardware",
            "tabs.identity": "Identity",
            "dialog.create_title": "Create New Profile",
            "dialog.edit_title": "Edit Profile",
            "dialog.confirm_delete": "Are you sure you want to delete this profile?",
            "dialog.starting": "Starting browser...",
            "dialog.please_wait": "Please Wait",
            "groups.title": "Profile Groups",
            "groups.create": "New Group",
            "groups.bulk_launch": "Launch All",
            "groups.bulk_stop": "Stop All",
            "api.title": "API & MCP",
            "api.start": "Start API Server",
            "api.stop": "Stop API Server",
            "api.key": "API Key",
            "api.reset_key": "Reset API Key",
            "api.copy_config": "Copy MCP Config",
            "proxy_pool.title": "Proxy Pool",
            "proxy_pool.add": "Add Proxy",
            "proxy_pool.test_all": "Test All",
            "proxy_pool.import": "Import",
            "proxy_pool.export": "Export",
            "fingerprint.test": "Test Fingerprint",
            "fingerprint.generate_ai": "Generate with AI",
            "error.profile_not_found": "Profile not found",
            "error.profile_exists": "Profile already exists",
            "error.browser_launch_failed": "Failed to launch browser",
            "error.proxy_invalid": "Invalid proxy configuration",
        },
        "zh": {
            "app.title": "指纹卫士浏览器",
            "profiles.title": "浏览器配置",
            "profiles.create": "创建",
            "profiles.edit": "编辑",
            "profiles.delete": "删除",
            "profiles.start": "启动",
            "profiles.stop": "停止",
            "profiles.name": "配置名称",
            "profiles.proxy": "代理 (地址:端口)",
            "profiles.timezone": "时区",
            "profiles.dns_protection": "DNS 保护",
            "profiles.custom_dns": "自定义 DNS",
            "profiles.dns_leak": "启用 DNS 防泄漏",
            "profiles.webrtc": "WebRTC 策略",
            "profiles.canvas_fp": "启用 Canvas 指纹保护",
            "profiles.webgl_fp": "启用 WebGL 指纹保护",
            "profiles.audio_fp": "启用 AudioContext 指纹保护",
            "profiles.client_rects_fp": "启用 Client Rects 指纹保护",
            "profiles.cpu_cores": "CPU 核心数",
            "profiles.memory": "内存",
            "profiles.gpu_vendor": "GPU 厂商",
            "profiles.screen_res": "屏幕分辨率",
            "profiles.platform": "平台",
            "profiles.browser": "浏览器",
            "profiles.language": "语言",
            "profiles.tags": "标签",
            "profiles.group": "分组",
            "tabs.basic": "基本",
            "tabs.privacy": "隐私",
            "tabs.hardware": "硬件",
            "tabs.identity": "身份",
            "dialog.create_title": "创建新配置",
            "dialog.edit_title": "编辑配置",
            "dialog.confirm_delete": "确定要删除此配置吗？",
            "dialog.starting": "正在启动浏览器...",
            "dialog.please_wait": "请稍候",
            "groups.title": "配置分组",
            "groups.create": "新建分组",
            "groups.bulk_launch": "全部启动",
            "groups.bulk_stop": "全部停止",
            "api.title": "API 与 MCP",
            "api.start": "启动 API 服务器",
            "api.stop": "停止 API 服务器",
            "api.key": "API 密钥",
            "api.reset_key": "重置 API 密钥",
            "api.copy_config": "复制 MCP 配置",
            "proxy_pool.title": "代理池",
            "proxy_pool.add": "添加代理",
            "proxy_pool.test_all": "全部测试",
            "proxy_pool.import": "导入",
            "proxy_pool.export": "导出",
            "fingerprint.test": "测试指纹",
            "fingerprint.generate_ai": "AI 生成指纹",
            "error.profile_not_found": "找不到配置",
            "error.profile_exists": "配置已存在",
            "error.browser_launch_failed": "启动浏览器失败",
            "error.proxy_invalid": "无效的代理配置",
        },
        "es": {
            "app.title": "FingerGuard Browser",
            "profiles.title": "Perfiles de Navegador",
            "profiles.create": "Crear",
            "profiles.edit": "Editar",
            "profiles.delete": "Eliminar",
            "profiles.start": "Iniciar",
            "profiles.stop": "Detener",
            "profiles.name": "Nombre del Perfil",
            "profiles.proxy": "Proxy (host:puerto)",
            "profiles.timezone": "Zona Horaria",
            "profiles.dns_protection": "Protección DNS",
            "profiles.custom_dns": "DNS Personalizado",
            "profiles.dns_leak": "Habilitar Protección de Fuga DNS",
            "profiles.webrtc": "Política WebRTC",
            "profiles.canvas_fp": "Habilitar Protección de Huella Canvas",
            "profiles.webgl_fp": "Habilitar Protección de Huella WebGL",
            "profiles.audio_fp": "Habilitar Protección de Huella AudioContext",
            "profiles.client_rects_fp": "Habilitar Protección de Client Rects",
            "profiles.cpu_cores": "Núcleos de CPU",
            "profiles.memory": "Memoria",
            "profiles.gpu_vendor": "Fabricante de GPU",
            "profiles.screen_res": "Resolución de Pantalla",
            "profiles.platform": "Plataforma",
            "profiles.browser": "Navegador",
            "profiles.language": "Idioma",
            "profiles.tags": "Etiquetas",
            "profiles.group": "Grupo",
            "tabs.basic": "Básico",
            "tabs.privacy": "Privacidad",
            "tabs.hardware": "Hardware",
            "tabs.identity": "Identidad",
            "dialog.create_title": "Crear Nuevo Perfil",
            "dialog.edit_title": "Editar Perfil",
            "dialog.confirm_delete": "¿Está seguro de que desea eliminar este perfil?",
            "dialog.starting": "Iniciando navegador...",
            "dialog.please_wait": "Por favor espere",
            "groups.title": "Grupos de Perfiles",
            "groups.create": "Nuevo Grupo",
            "groups.bulk_launch": "Iniciar Todos",
            "groups.bulk_stop": "Detener Todos",
            "api.title": "API y MCP",
            "api.start": "Iniciar Servidor API",
            "api.stop": "Detener Servidor API",
            "api.key": "Clave API",
            "api.reset_key": "Restablecer Clave API",
            "api.copy_config": "Copiar Configuración MCP",
            "proxy_pool.title": "Grupo de Proxies",
            "proxy_pool.add": "Añadir Proxy",
            "proxy_pool.test_all": "Probar Todos",
            "proxy_pool.import": "Importar",
            "proxy_pool.export": "Exportar",
            "fingerprint.test": "Probar Huella",
            "fingerprint.generate_ai": "Generar con IA",
            "error.profile_not_found": "Perfil no encontrado",
            "error.profile_exists": "El perfil ya existe",
            "error.browser_launch_failed": "Error al iniciar el navegador",
            "error.proxy_invalid": "Configuración de proxy no válida",
        },
    }

    def __init__(self, locale: str = None):
        self._locale = self.DEFAULT_LOCALE
        if locale:
            self.locale = locale  # Use setter for validation
        self._load_locale_files()

    def _load_locale_files(self):
        """Load external locale files from src/utils/locales/ if they exist."""
        locales_dir = os.path.join(os.path.dirname(__file__), "locales")
        if not os.path.exists(locales_dir):
            os.makedirs(locales_dir, exist_ok=True)
            # Write built-in translations to files
            for lang, translations in self.TRANSLATIONS.items():
                filepath = os.path.join(locales_dir, f"{lang}.json")
                if not os.path.exists(filepath):
                    with open(filepath, "w", encoding="utf-8") as f:
                        json.dump(translations, f, indent=2, ensure_ascii=False)
            logger.info(f"Created locale files in {locales_dir}")

        # Load from files, merging with built-in
        for lang in self.SUPPORTED_LOCALES:
            filepath = os.path.join(locales_dir, f"{lang}.json")
            if os.path.exists(filepath):
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        external = json.load(f)
                        self.TRANSLATIONS[lang].update(external)
                except (json.JSONDecodeError, IOError) as e:
                    logger.warning(f"Failed to load locale {lang}: {e}")

    @property
    def locale(self) -> str:
        return self._locale

    @locale.setter
    def locale(self, value: str):
        if value in self.SUPPORTED_LOCALES:
            self._locale = value
        else:
            logger.warning(f"Unsupported locale: {value}, using {self.DEFAULT_LOCALE}")
            self._locale = self.DEFAULT_LOCALE

    def translate(self, key: str, locale: str = None) -> str:
        """Translate a key to the current (or specified) locale."""
        lang = locale or self._locale
        translations = self.TRANSLATIONS.get(lang, self.TRANSLATIONS[self.DEFAULT_LOCALE])
        return translations.get(key, key)  # Fallback to key itself

    def get_all_translations(self, locale: str = None) -> dict:
        """Get all translations for a locale."""
        lang = locale or self._locale
        return self.TRANSLATIONS.get(lang, self.TRANSLATIONS[self.DEFAULT_LOCALE])


# Global singleton
_i18n_instance: Optional[I18n] = None


def get_i18n(locale: str = None) -> I18n:
    """Get or create the global I18n instance."""
    global _i18n_instance
    if _i18n_instance is None:
        _i18n_instance = I18n(locale=locale)
    elif locale:
        _i18n_instance.locale = locale
    return _i18n_instance


def _(key: str, locale: str = None) -> str:
    """Shorthand translation function."""
    return get_i18n().translate(key, locale)
