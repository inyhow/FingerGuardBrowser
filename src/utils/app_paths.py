"""Application path resolution for both development and PyInstaller builds.

Rules:
- Bundled resources (HTML, JSON templates) live next to the source in dev
  and inside the PyInstaller extraction directory in production.
- User data (database, logs, Chrome profile cache) is always written to a
  persistent directory so it survives updates and does not pollute the
  install location.
"""

import os
import sys


def is_frozen() -> bool:
    """Return True when running inside a PyInstaller bundle."""
    return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")


def bundle_dir() -> str:
    """Directory containing the bundled application resources."""
    if is_frozen():
        return sys._MEIPASS
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def user_data_dir() -> str:
    """Persistent directory for user data (DB, logs, browser caches).

    In production this is %LOCALAPPDATA%\FingerGuardBrowser on Windows.
    In development it falls back to the project root so existing workflows
    keep working.
    """
    if is_frozen():
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        return os.path.join(base, "FingerGuardBrowser")
    return bundle_dir()


def resource_path(*parts: str) -> str:
    """Path to a bundled resource file (e.g. HTML/JSON templates)."""
    return os.path.join(bundle_dir(), *parts)


def data_path(*parts: str) -> str:
    """Path inside the persistent user data directory."""
    path = os.path.join(user_data_dir(), *parts)
    os.makedirs(os.path.dirname(path) if parts else path, exist_ok=True)
    return path
