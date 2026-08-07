"""Lightweight web-based UI launcher using pywebview.

Replaces the heavy PyQt5 + PyQtWebEngine stack (~100MB) with pywebview (~5MB),
which uses the system WebView (WebView2 on Windows, WebKit on macOS/Linux).

The launcher:
1. Initializes the database and all backend modules
2. Starts the local API server (serves both API and web UI)
3. Opens a native window pointing to the local URL
"""

import os
import sys
import time
import threading

# Ensure src is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def launch():
    """Start backend and open the web UI in a pywebview window."""
    from src.utils.logger import setup_logger
    setup_logger()

    from loguru import logger
    from src.storage.database import Database
    from src.api.server import APIServer

    # Initialize database (singleton) — required for everything
    db = Database()

    # Initialize browser manager (lazy import — selenium/uc optional)
    browser_manager = None
    try:
        from src.browser.browser_manager import BrowserManager
        browser_manager = BrowserManager(database=db)
        logger.info("BrowserManager initialized (with database)")
    except Exception as e:
        logger.warning(f"BrowserManager not available: {e}")

    # Initialize proxy pool
    proxy_pool = None
    try:
        from src.proxy.proxy_pool import ProxyPool
        proxy_pool = ProxyPool(database=db)
        logger.info("ProxyPool initialized")
    except Exception as e:
        logger.warning(f"ProxyPool not available: {e}")

    # Defer non-critical modules — initialize after window opens
    group_manager = None
    fingerprint_manager = None
    ai_generator = None

    # Start API server immediately with available modules
    api_server = APIServer(
        browser_manager=browser_manager,
        proxy_pool=proxy_pool,
        group_manager=group_manager,
        fingerprint_manager=fingerprint_manager,
        ai_generator=ai_generator,
        database=db,
        port=0,  # auto-assign
    )
    api_server.start()

    # Wait for server to be ready
    time.sleep(0.3)
    port = api_server.actual_port
    api_key = api_server.api_key
    url = f"http://127.0.0.1:{port}/?key={api_key}&port={port}"
    logger.info(f"Web UI URL: {url}")

    # Share API port with browser manager so it can open the test page on launch
    if browser_manager:
        browser_manager.api_port = port

    # Deferred initialization — load remaining modules in background
    def _deferred_init():
        nonlocal group_manager, fingerprint_manager, ai_generator
        try:
            from src.profiles.group_manager import GroupManager
            group_manager = GroupManager()
            api_server.group_manager = group_manager
            logger.info("GroupManager initialized (deferred)")
        except Exception as e:
            logger.warning(f"GroupManager not available: {e}")
        try:
            from src.fingerprint.fingerprint_manager import FingerprintManager
            fingerprint_manager = FingerprintManager()
            api_server.fingerprint_manager = fingerprint_manager
            logger.info("FingerprintManager initialized (deferred)")
        except Exception as e:
            logger.warning(f"FingerprintManager not available: {e}")
        try:
            from src.fingerprint.ai_generator import AIFingerprintGenerator
            ai_generator = AIFingerprintGenerator()
            api_server.ai_generator = ai_generator
            logger.info("AIFingerprintGenerator initialized (deferred)")
        except Exception as e:
            logger.warning(f"AIFingerprintGenerator not available: {e}")

    threading.Thread(target=_deferred_init, daemon=True).start()

    # Open pywebview window
    try:
        import webview

        def on_closed():
            logger.info("Window closed, shutting down API server")
            api_server.stop()

        window = webview.create_window(
            title="FingerGuard Browser",
            url=url,
            width=1100,
            height=720,
            min_size=(800, 500),
            text_select=False,
        )
        window.events.closing += on_closed

        webview.start(debug=False)

        # --- Window closed: full cleanup ---
        logger.info("Cleaning up before exit...")

        # Close all running browser instances
        if browser_manager:
            try:
                browser_manager.close_all_browsers()
            except Exception as e:
                logger.warning(f"Error closing browsers during exit: {e}")

        # Stop API server (in case on_closed didn't fire or didn't finish)
        try:
            api_server.stop()
        except Exception:
            pass

        # Close database connection
        try:
            db.close()
        except Exception:
            pass

        logger.info("Cleanup complete, exiting.")
        # Force exit — bypass lingering non-daemon threads that prevent clean shutdown
        os._exit(0)

    except ImportError:
        logger.error("pywebview not installed. Install with: pip install pywebview")
        logger.info(f"Open manually: {url}")
        # Keep running so user can open in browser
        try:
            import webbrowser
            webbrowser.open(url)
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            api_server.stop()


if __name__ == "__main__":
    launch()
