# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for FingerGuard Browser.

Build a standalone Windows directory distribution that can be zipped or
wrapped into an installer. User data (database, logs, Chrome profiles) is
written to %LOCALAPPDATA%\FingerGuardBrowser at runtime, not into the
installation folder.
"""

import os
from PyInstaller.building.build_main import Analysis, PYZ, EXE, COLLECT

block_cipher = None

PROJECT_ROOT = os.path.abspath(SPECPATH)


def collect_datas():
    """Return datas entries for non-Python resources."""
    entries = []

    # Web UI
    entries.append((os.path.join(PROJECT_ROOT, "src", "web", "index.html"), "src/web"))

    # Fingerprint test page injected into launched browsers
    entries.append((os.path.join(PROJECT_ROOT, "src", "fingerprint", "test_page.html"), "src/fingerprint"))

    # Fingerprint presets (only the default template; test artifacts excluded)
    entries.append((os.path.join(PROJECT_ROOT, "src", "fingerprint", "fingerprints", "default.json"), "src/fingerprint/fingerprints"))

    # Legacy empty profile JSON used by migration fallback
    entries.append((os.path.join(PROJECT_ROOT, "src", "browser", "config", "profiles.json"), "src/browser/config"))

    return entries


a = Analysis(
    [os.path.join(PROJECT_ROOT, "main.py")],
    pathex=[PROJECT_ROOT],
    binaries=[],
    datas=collect_datas(),
    hiddenimports=[
        "pywebview",
        "pywebview.platforms.winforms",
        "clr",
        "selenium",
        "selenium.webdriver.chrome",
        "selenium.webdriver.common.service",
        "undetected_chromedriver",
        "undetected_chromedriver.dprocess",
        "selenium_stealth",
        "loguru",
        "cryptography",
        "cryptography.fernet",
        "requests",
        "pytz",
        "websockets",
        "keyring",
        "keyring.backends.Windows",
        "python_dotenv",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "matplotlib",
        "numpy",
        "pandas",
        "PIL",
        "PyQt5",
        "PyQt6",
        "PySide2",
        "PySide6",
        "flet",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="FingerGuardBrowser",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="FingerGuardBrowser",
)
