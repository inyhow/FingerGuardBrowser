"""Browser binary auto-detection and path management.

Detects installed Chrome, Edge, and other Chromium-based browsers on Windows,
macOS, and Linux. Falls back to common installation paths and allows user
override via settings.
"""

import os
import sys
import re
import json
import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Any
from loguru import logger


# Common browser binary names and registry/paths by platform
BROWSER_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    "chrome": {
        "win_names": ["chrome.exe"],
        "win_paths": [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            r"C:\Users\{user}\AppData\Local\Google\Chrome\Application\chrome.exe",
            r"C:\Users\{user}\AppData\Local\Google\Chrome\Bin\chrome.exe",
        ],
        "win_reg": [
            (r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe", None),
            (r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\Google Chrome", "InstallLocation"),
        ],
        "mac_paths": [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        ],
        "linux_names": ["google-chrome", "google-chrome-stable", "chrome", "chromium", "chromium-browser"],
    },
    "edge": {
        "win_names": ["msedge.exe"],
        "win_paths": [
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            r"C:\Users\{user}\AppData\Local\Microsoft\Edge\Application\msedge.exe",
        ],
        "win_reg": [
            (r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\msedge.exe", None),
            (r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\Microsoft Edge", "InstallLocation"),
        ],
        "mac_paths": [
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
            "~/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        ],
        "linux_names": ["microsoft-edge", "microsoft-edge-stable", "msedge"],
    },
    "brave": {
        "win_names": ["brave.exe"],
        "win_paths": [
            r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
            r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe",
            r"C:\Users\{user}\AppData\Local\BraveSoftware\Brave-Browser\Application\brave.exe",
        ],
        "win_reg": [
            (r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\brave.exe", None),
        ],
        "mac_paths": [
            "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
        ],
        "linux_names": ["brave", "brave-browser"],
    },
    "opera": {
        "win_names": ["opera.exe"],
        "win_paths": [
            r"C:\Users\{user}\AppData\Local\Programs\Opera\opera.exe",
            r"C:\Program Files\Opera\opera.exe",
        ],
        "mac_paths": [
            "/Applications/Opera.app/Contents/MacOS/Opera",
        ],
        "linux_names": ["opera"],
    },
    "vivaldi": {
        "win_names": ["vivaldi.exe"],
        "win_paths": [
            r"C:\Users\{user}\AppData\Local\Vivaldi\Application\vivaldi.exe",
            r"C:\Program Files\Vivaldi\Application\vivaldi.exe",
        ],
        "mac_paths": [
            "/Applications/Vivaldi.app/Contents/MacOS/Vivaldi",
        ],
        "linux_names": ["vivaldi", "vivaldi-stable"],
    },
}


def _win_read_reg(key_path: str, value_name: Optional[str]) -> Optional[str]:
    """Read a value from Windows registry."""
    try:
        import winreg
        hives = [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]
        for hive in hives:
            try:
                with winreg.OpenKey(hive, key_path) as key:
                    if value_name is None:
                        # Default value
                        val, _ = winreg.QueryValueEx(key, None)
                    else:
                        val, _ = winreg.QueryValueEx(key, value_name)
                    if val:
                        return val
            except FileNotFoundError:
                continue
            except Exception as e:
                logger.debug(f"Registry read error: {e}")
    except ImportError:
        pass
    return None


def _win_find_browser_exe(browser: str) -> Optional[str]:
    """Find a browser executable on Windows."""
    info = BROWSER_DEFINITIONS.get(browser, {})
    user = os.environ.get("USERNAME") or os.environ.get("USER") or ""

    # 1. Registry-based lookup
    for reg_path, value_name in info.get("win_reg", []):
        val = _win_read_reg(reg_path, value_name)
        if val:
            if value_name == "InstallLocation":
                # Need to append executable name
                exe_name = info["win_names"][0]
                candidate = os.path.join(val, exe_name)
                if not os.path.isfile(candidate):
                    candidate = os.path.join(val, "Application", exe_name)
                if os.path.isfile(candidate):
                    return candidate
            else:
                if os.path.isfile(val):
                    return val

    # 2. Known paths
    for tmpl in info.get("win_paths", []):
        path = tmpl.format(user=user)
        path = os.path.expandvars(path)
        if os.path.isfile(path):
            return path

    # 3. Search PATH
    for name in info.get("win_names", []):
        for path_dir in os.environ.get("PATH", "").split(os.pathsep):
            candidate = os.path.join(path_dir, name)
            if os.path.isfile(candidate):
                return candidate

    # 4. Where command
    for name in info.get("win_names", []):
        try:
            result = subprocess.run(
                ["where", name],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                first = result.stdout.strip().splitlines()[0]
                if os.path.isfile(first):
                    return first
        except Exception:
            pass

    return None


def _mac_find_browser_exe(browser: str) -> Optional[str]:
    """Find a browser executable on macOS."""
    info = BROWSER_DEFINITIONS.get(browser, {})
    for path in info.get("mac_paths", []):
        expanded = os.path.expanduser(path)
        if os.path.isfile(expanded):
            return expanded

    # Search PATH
    for name in info.get("linux_names", []):
        try:
            result = subprocess.run(
                ["which", name],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                path = result.stdout.strip()
                if os.path.isfile(path):
                    return path
        except Exception:
            pass
    return None


def _linux_find_browser_exe(browser: str) -> Optional[str]:
    """Find a browser executable on Linux."""
    info = BROWSER_DEFINITIONS.get(browser, {})
    for name in info.get("linux_names", []):
        try:
            result = subprocess.run(
                ["which", name],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                path = result.stdout.strip()
                if os.path.isfile(path):
                    return path
        except Exception:
            pass

    # Flatpak / snap common paths
    flatpak_map = {
        "chrome": "/var/lib/flatpak/app/com.google.Chrome/current/active/files/extra/chrome",
        "edge": "/var/lib/flatpak/app/com.microsoft.Edge/current/active/files/extra/msedge",
        "brave": "/var/lib/flatpak/app/com.brave.Browser/current/active/files/extra/brave",
    }
    candidate = flatpak_map.get(browser)
    if candidate and os.path.isfile(candidate):
        return candidate

    return None


def find_browser_binary(browser: str = "chrome") -> Optional[str]:
    """Find the binary path for the requested browser.

    Args:
        browser: One of chrome, edge, brave, opera, vivaldi.

    Returns:
        Absolute path to the executable, or None if not found.
    """
    browser = browser.lower()
    if browser not in BROWSER_DEFINITIONS:
        logger.warning(f"Unknown browser '{browser}', defaulting to chrome")
        browser = "chrome"

    system = sys.platform
    if system.startswith("win"):
        path = _win_find_browser_exe(browser)
    elif system == "darwin":
        path = _mac_find_browser_exe(browser)
    else:
        path = _linux_find_browser_exe(browser)

    if path:
        logger.info(f"Detected {browser} binary: {path}")
    else:
        logger.warning(f"Could not detect {browser} binary")
    return path


def detect_all_browsers() -> Dict[str, str]:
    """Detect all supported browser binaries."""
    return {name: path for name, path in {
        name: find_browser_binary(name) for name in BROWSER_DEFINITIONS
    }.items() if path}


def get_browser_path(settings_db=None, preferred: str = None) -> Optional[str]:
    """Get the browser binary path to use, considering user override.

    Args:
        settings_db: Optional Database instance to read stored setting.
        preferred: Optional preferred browser type (chrome, edge, etc.).

    Returns:
        Absolute path, or None if not found.
    """
    # 1. Custom user override
    if settings_db is not None:
        custom_path = settings_db.get_setting("browser_binary_path")
        if custom_path and os.path.isfile(custom_path):
            return custom_path

    # 2. Preferred browser type
    if preferred:
        path = find_browser_binary(preferred)
        if path:
            return path

    # 3. Default order: chrome, edge, brave, opera, vivaldi
    for browser in ["chrome", "edge", "brave", "opera", "vivaldi"]:
        path = find_browser_binary(browser)
        if path:
            return path

    return None


def _get_chrome_version_registry(browser: str) -> Optional[int]:
    """Get browser major version from Windows Registry.

    Chrome stores its version at HKCU\\Software\\Google\\Chrome\\BLBeacon\\version
    Edge stores at HKCU\\Software\\Microsoft\\Edge\\BLBeacon\\version
    """
    reg_paths = {
        "chrome": r"Software\Google\Chrome\BLBeacon",
        "edge": r"Software\Microsoft\Edge\BLBeacon",
        "brave": r"Software\BraveSoftware\Brave-Browser\BLBeacon",
    }
    key_path = reg_paths.get(browser)
    if not key_path:
        return None
    try:
        import winreg
        for hive in [winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE]:
            try:
                with winreg.OpenKey(hive, key_path) as key:
                    val, _ = winreg.QueryValueEx(key, "version")
                    # val is like "150.0.7871.189"
                    match = re.search(r'(\d+)\.', str(val))
                    if match:
                        return int(match.group(1))
            except (FileNotFoundError, OSError):
                continue
    except ImportError:
        pass
    return None


def _get_chrome_version_from_dir(browser_path: str) -> Optional[int]:
    """Parse Chrome version from installation directory structure.

    Chrome installs version-specific folders like:
    C:\\Program Files\\Google\\Chrome\\Application\\150.0.7871.189\\
    """
    try:
        app_dir = os.path.dirname(browser_path)
        if not os.path.isdir(app_dir):
            return None
        # Look for directories that match version pattern (e.g., 150.0.7871.189)
        import re as _re
        for entry in os.listdir(app_dir):
            match = _re.match(r'^(\d+)\.\d+\.\d+\.\d+$', entry)
            if match:
                return int(match.group(1))
    except Exception:
        pass
    return None


def get_browser_version_major(browser_path: str, browser_type: str = "chrome") -> Optional[int]:
    """Get the major version number of a browser binary.

    Tries multiple methods on Windows because ``chrome.exe --version`` returns
    "Opening in existing browser session." when Chrome is already running.

    Methods (in order):
    1. Windows Registry (BLBeacon\\version) — most reliable
    2. Installation directory structure (version-numbered folders)
    3. ``--version`` command line (fails when browser is already running)

    Returns ``150`` for ``Google Chrome 150.0.7871.189``.
    """
    if not browser_path or not os.path.isfile(browser_path):
        return None

    # Method 1: Windows Registry
    if sys.platform.startswith("win"):
        reg_version = _get_chrome_version_registry(browser_type)
        if reg_version:
            return reg_version

    # Method 2: Parse version from installation directory
    dir_version = _get_chrome_version_from_dir(browser_path)
    if dir_version:
        return dir_version

    # Method 3: --version command (unreliable on Windows when browser is running)
    try:
        proc = subprocess.run(
            [browser_path, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        # Check both stdout and stderr (some browsers output to stderr)
        output = (proc.stdout + proc.stderr).strip()
        match = re.search(r'(\d+)\.', output)
        if match:
            return int(match.group(1))
        return None
    except Exception:
        return None


def validate_browser_path(path: str) -> Dict[str, Any]:
    """Validate a browser binary path and return version info if possible."""
    result = {"valid": False, "path": path, "version": None, "error": None}
    if not path or not os.path.isfile(path):
        result["error"] = "File not found"
        return result

    try:
        proc = subprocess.run(
            [path, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if proc.returncode == 0:
            result["valid"] = True
            result["version"] = proc.stdout.strip()
        else:
            result["error"] = proc.stderr.strip() or "Failed to get version"
    except Exception as e:
        result["error"] = str(e)
    return result
