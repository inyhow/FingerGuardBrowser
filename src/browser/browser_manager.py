import os
import json
import random
import requests
from loguru import logger
from .profile import ProfileManager, BrowserProfile
from ..fingerprint.fingerprint_manager import FingerprintManager
from ..fingerprint.humanize import Humanizer
from ..utils.browser_detector import get_browser_path, detect_all_browsers, get_browser_version_major
from ..utils.app_paths import data_path, resource_path
from typing import Optional, Dict, Any

# Lazy import of undetected_chromedriver to avoid hard dependency at module load time
# (useful for testing and environments where Chrome is not installed)
uc = None

def _ensure_uc():
    """Lazy-load undetected_chromedriver only when actually needed."""
    global uc
    if uc is None:
        import undetected_chromedriver as _uc
        uc = _uc
    return uc

class BrowserManager:
    """Enhanced Browser Manager with CDP injection, proxy validation, and profile isolation."""

    def __init__(self, database=None):
        self.config_dir = data_path("profiles", "config")
        os.makedirs(self.config_dir, exist_ok=True)
        self.profile_manager = ProfileManager(self.config_dir)
        self.fingerprint_manager = FingerprintManager()
        # API server port for serving the fingerprint test page (set externally after server starts)
        self.api_port: Optional[int] = None
        # Use database for profile storage if provided
        if database is not None:
            self.db = database
        else:
            try:
                from ..storage.database import Database
                self.db = Database()
            except Exception:
                self.db = None
        # Cache for proxy validation results: {proxy_string: {result, timestamp}}
        self._proxy_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_ttl = 300  # 5 minutes
        # Track running drivers: {profile_name: driver}
        self._drivers: Dict[str, Any] = {}
        # Track humanizers for profiles with humanize enabled: {profile_name: Humanizer}
        self._humanizers: Dict[str, Humanizer] = {}
        self._drivers: Dict[str, Any] = {}

    def create_profile(self, name: str, **kwargs) -> BrowserProfile:
        if self.db is not None:
            data = self.db.create_profile(name, **kwargs)
            return BrowserProfile(name=name, proxy=data.get("proxy"), timezone=data.get("timezone"))
        return self.profile_manager.create_profile(name, **kwargs)

    def get_profile(self, name: str) -> Optional[BrowserProfile]:
        if self.db is not None:
            data = self.db.get_profile(name)
            if data is None:
                return None
            return BrowserProfile(
                name=data["name"],
                proxy=data.get("proxy"),
                timezone=data.get("timezone"),
                webrtc=data.get("webrtc", "filter"),
                canvas_fp=data.get("canvas_fp", True),
                webgl_fp=data.get("webgl_fp", True),
                audio_fp=data.get("audio_fp", True),
                dns_protection=data.get("dns_protection", "cloudflare"),
            )
        return self.profile_manager.get_profile(name)

    def update_profile(self, name: str, **kwargs) -> BrowserProfile:
        if self.db is not None:
            self.db.update_profile(name, **kwargs)
            return self.get_profile(name)
        return self.profile_manager.update_profile(name, **kwargs)

    def delete_profile(self, name: str):
        """Delete a profile and clean up all associated data."""
        # Close browser if running
        if name in self._drivers:
            try:
                self.close_browser(name)
            except Exception as e:
                logger.warning(f"Error closing browser during deletion of {name}: {e}")

        # Clean up user-data directory
        self._cleanup_profile_data(name)

        # Delete from database
        if self.db is not None:
            self.db.delete_profile(name)
        else:
            self.profile_manager.delete_profile(name)
        logger.info(f"Profile deleted with cleanup: {name}")

    def _cleanup_profile_data(self, profile_name: str):
        """Remove all on-disk data associated with a profile."""
        import shutil
        data_dir = data_path("profiles", "chrome_data", profile_name)
        if os.path.isdir(data_dir):
            try:
                shutil.rmtree(data_dir, ignore_errors=True)
                logger.info(f"Cleaned up profile data directory: {data_dir}")
            except Exception as e:
                logger.warning(f"Failed to clean up profile data directory {data_dir}: {e}")

    def close_all_browsers(self):
        """Close all running browser instances."""
        names = list(self._drivers.keys())
        closed = 0
        for name in names:
            try:
                self.close_browser(name)
                closed += 1
            except Exception as e:
                logger.warning(f"Error closing browser {name}: {e}")
        logger.info(f"Closed {closed}/{len(names)} browsers")
        return {"closed": closed, "total": len(names)}

    def list_profiles(self) -> dict:
        if self.db is not None:
            profiles = self.db.list_profiles()
            return {p["name"]: p for p in profiles}
        return self.profile_manager.list_profiles()

    def get_all_profiles(self) -> dict:
        return self.list_profiles()

    def check_proxy(self, proxy: str, use_cache: bool = True) -> Dict[str, Any]:
        """Validate proxy connectivity and get geographic/ISP information.

        Uses HTTPS endpoints from multiple sources for reliability.
        Results are cached for 5 minutes to avoid redundant API calls.
        """
        if not proxy:
            return {"status": "error", "message": "No proxy provided"}

        # Check cache
        if use_cache and proxy in self._proxy_cache:
            cached = self._proxy_cache[proxy]
            import time
            if time.time() - cached["timestamp"] < self._cache_ttl:
                logger.debug(f"Using cached proxy result for {proxy}")
                return cached["result"]

        proxies = {
            "http": proxy,
            "https": proxy,
        }

        # Try multiple geo-IP sources for reliability (all over HTTPS)
        geo_sources = [
            {
                "url": "https://ipapi.co/json/",
                "parser": lambda data: {
                    "status": "success",
                    "ip": data.get("ip"),
                    "country": data.get("country_name"),
                    "country_code": data.get("country_code"),
                    "city": data.get("city"),
                    "isp": data.get("org"),
                    "timezone": data.get("timezone"),
                    "latitude": data.get("latitude"),
                    "longitude": data.get("longitude"),
                    "asn": data.get("asn"),
                } if data.get("ip") else {"status": "error", "message": "No IP in response"},
            },
            {
                "url": "https://ipwho.is/",
                "parser": lambda data: {
                    "status": "success",
                    "ip": data.get("ip"),
                    "country": data.get("country"),
                    "country_code": data.get("country_code"),
                    "city": data.get("city"),
                    "isp": data.get("connection", {}).get("isp") if isinstance(data.get("connection"), dict) else None,
                    "timezone": data.get("timezone", {}).get("id") if isinstance(data.get("timezone"), dict) else None,
                    "latitude": data.get("latitude"),
                    "longitude": data.get("longitude"),
                    "asn": data.get("connection", {}).get("asn") if isinstance(data.get("connection"), dict) else None,
                } if data.get("success") else {"status": "error", "message": data.get("message", "Unknown error")},
            },
            {
                "url": "https://api.ipify.org?format=json",
                "parser": lambda data: {
                    "status": "success",
                    "ip": data.get("ip"),
                    "country": None,
                    "country_code": None,
                    "city": None,
                    "isp": None,
                    "timezone": None,
                    "latitude": None,
                    "longitude": None,
                    "asn": None,
                } if data.get("ip") else {"status": "error", "message": "No IP in response"},
            },
        ]

        for source in geo_sources:
            try:
                response = requests.get(source["url"], proxies=proxies, timeout=15, verify=True)
                if response.status_code == 200:
                    data = response.json()
                    result = source["parser"](data)
                    if result["status"] == "success":
                        logger.info(f"Proxy verified via {source['url']}: {result.get('ip')} ({result.get('country')})")
                        # Cache the result
                        import time
                        self._proxy_cache[proxy] = {"result": result, "timestamp": time.time()}
                        return result
            except requests.exceptions.ProxyError:
                logger.warning(f"Proxy error with {source['url']}")
                continue
            except requests.exceptions.Timeout:
                logger.warning(f"Timeout with {source['url']}")
                continue
            except Exception as e:
                logger.warning(f"Error with {source['url']}: {str(e)}")
                continue

        result = {"status": "error", "message": "All geo-IP sources failed"}
        return result

    def _get_profile_data_dir(self, profile_name: str) -> str:
        """Get isolated user-data directory for a profile."""
        base_dir = data_path("profiles", "chrome_data", profile_name)
        os.makedirs(base_dir, exist_ok=True)
        return base_dir

    @staticmethod
    def _locale_from_country_code(country_code: str) -> Optional[str]:
        """Map a country code to a locale string (e.g. US -> en-US, DE -> de-DE)."""
        if not country_code:
            return None
        country_locale_map = {
            "US": "en-US", "GB": "en-GB", "AU": "en-AU", "CA": "en-CA",
            "DE": "de-DE", "AT": "de-AT", "CH": "de-CH",
            "FR": "fr-FR", "BE": "fr-BE", "CA": "fr-CA",
            "JP": "ja-JP", "CN": "zh-CN", "TW": "zh-TW", "HK": "zh-HK",
            "KR": "ko-KR", "ES": "es-ES", "MX": "es-MX", "IT": "it-IT",
            "PT": "pt-PT", "BR": "pt-BR", "RU": "ru-RU", "NL": "nl-NL",
            "SE": "sv-SE", "NO": "nb-NO", "DK": "da-DK", "FI": "fi-FI",
            "PL": "pl-PL", "TR": "tr-TR", "IN": "en-IN", "SG": "en-SG",
            "TH": "th-TH", "VN": "vi-VN", "ID": "id-ID", "MY": "ms-MY",
            "PH": "en-PH", "SA": "ar-SA", "AE": "ar-AE", "IL": "he-IL",
        }
        return country_locale_map.get(country_code.upper())

    def _inject_fingerprint_via_cdp(self, driver, profile: BrowserProfile, proxy_ip: str = None, proxy_geo: dict = None):
        """Inject fingerprint protection script via Chrome DevTools Protocol.

        Uses Page.addScriptToEvaluateOnNewDocument for persistent injection
        across all page navigations.
        """
        try:
            # Load or create the fingerprint for this profile
            fp_name = profile.name
            fingerprint = self.fingerprint_manager.load_fingerprint(fp_name)

            # Override timezone from profile if set
            if profile.timezone:
                fingerprint["timezone"] = profile.timezone

            # GeoIP auto-sync: override geolocation from proxy exit IP
            if proxy_geo and proxy_geo.get("latitude") and proxy_geo.get("longitude"):
                fingerprint["geolocation"] = {
                    "latitude": float(proxy_geo["latitude"]),
                    "longitude": float(proxy_geo["longitude"]),
                    "accuracy": 50,
                }
                logger.info(f"Auto-set geolocation from proxy IP: {proxy_geo['latitude']}, {proxy_geo['longitude']}")

            # GeoIP auto-sync: override locale from proxy country
            if proxy_geo and proxy_geo.get("country_code"):
                locale_from_country = self._locale_from_country_code(proxy_geo["country_code"])
                if locale_from_country:
                    fingerprint["locale"] = locale_from_country
                    fingerprint.setdefault("navigator", {})["language"] = locale_from_country
                    fingerprint["navigator"]["languages"] = [locale_from_country, locale_from_country.split("-")[0]]
                    logger.info(f"Auto-set locale from proxy country: {locale_from_country}")

            # Pass proxy exit IP for WebRTC spoofing
            if proxy_ip:
                fingerprint["proxy_ip"] = proxy_ip
                logger.info(f"Passing proxy exit IP to fingerprint for WebRTC spoofing: {proxy_ip}")

            # Generate the injection script
            injection_script = self.fingerprint_manager.get_injection_script(fingerprint)

            # Inject via CDP — runs before any page script
            driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                'source': injection_script
            })

            # Also set extra HTTP headers for consistency
            locale = fingerprint.get("locale", "en-US")
            languages = fingerprint.get("navigator", {}).get("languages", [locale])
            accept_language = ",".join(
                [f"{lang};q={1.0 - i*0.1:.1f}" for i, lang in enumerate(languages)]
            )

            driver.execute_cdp_cmd('Network.setExtraHTTPHeaders', {
                'headers': {
                    'Accept-Language': accept_language,
                }
            })

            logger.info(f"Fingerprint injected for profile: {fp_name}")
            return fingerprint

        except Exception as e:
            logger.error(f"Failed to inject fingerprint: {str(e)}")
            raise

    def launch_browser(self, profile_name: str) -> Any:
        """Launch browser with full fingerprint injection and profile isolation.

        Returns the WebDriver instance with fingerprint protection active.
        """
        try:
            # Read profile from database (primary) or JSON (fallback)
            profile_data = None
            if self.db is not None:
                profile_data = self.db.get_profile(profile_name)
            if profile_data is None:
                # Fallback to JSON ProfileManager
                profile = self.profile_manager.get_profile(profile_name)
                if not profile:
                    raise ValueError(f"Profile '{profile_name}' not found. Create it in the Profiles tab first.")
            else:
                # Create a BrowserProfile from database dict
                profile = BrowserProfile(
                    name=profile_data["name"],
                    proxy=profile_data.get("proxy"),
                    timezone=profile_data.get("timezone"),
                    webrtc=profile_data.get("webrtc", "filter"),
                    canvas_fp=profile_data.get("canvas_fp", True),
                    webgl_fp=profile_data.get("webgl_fp", True),
                    audio_fp=profile_data.get("audio_fp", True),
                    dns_protection=profile_data.get("dns_protection", "cloudflare"),
                )

            # Check if already running
            if profile_name in self._drivers:
                logger.warning(f"Browser {profile_name} is already running")
                return self._drivers[profile_name]

            logger.info(f"Launching browser with profile: {profile_name}")

            # Proxy validation (with caching)
            proxy_info = {"status": "error", "message": "No proxy configured"}
            if profile.proxy:
                proxy_info = self.check_proxy(profile.proxy)
                if proxy_info["status"] == "success":
                    logger.info(f"Proxy verified: {proxy_info.get('ip')} ({proxy_info.get('country')})")
                    # Auto-set timezone from proxy geo if not explicitly set
                    if not profile.timezone and proxy_info.get("timezone"):
                        profile.timezone = proxy_info["timezone"]
                        logger.info(f"Auto-set timezone from proxy: {profile.timezone}")
                else:
                    logger.warning(f"Proxy verification failed: {proxy_info.get('message')}")

            _ensure_uc()

            # Auto-detect browser binary path — use profile's browser_engine if available
            preferred_browser = "chrome"
            if profile_data and profile_data.get("browser_engine"):
                preferred_browser = profile_data["browser_engine"]
            browser_path = get_browser_path(preferred=preferred_browser)
            if not browser_path:
                detected = detect_all_browsers()
                if detected:
                    browser_path = list(detected.values())[0]
                else:
                    raise RuntimeError(
                        "No Chrome/Chromium browser found. Please install Google Chrome, "
                        "Microsoft Edge, or set a custom browser path in Settings. "
                        f"Detected: {detected or 'None'}"
                    )
            logger.info(f"Using browser binary: {browser_path} (engine: {preferred_browser})")

            options = uc.ChromeOptions()
            # Set the browser binary path explicitly
            options.binary_location = browser_path

            # Profile isolation — each profile gets its own user-data-dir
            user_data_dir = self._get_profile_data_dir(profile_name)
            options.add_argument(f'--user-data-dir={user_data_dir}')
            options.add_argument('--no-first-run')
            options.add_argument('--no-default-browser-check')

            # Security and privacy settings
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_argument('--disable-features=IsolateOrigins,site-per-process')
            options.add_argument('--disable-infobars')
            options.add_argument('--disable-notifications')
            options.add_argument('--disable-popup-blocking')

            # TLS/JA3 fingerprint randomization — prevent TLS-based tracking
            options.add_argument('--tls-variants=GREASE')
            options.add_argument('--disable-features=Tls13Grease,Tls13KeyShareGrease')

            # Disable WebRTC mDNS hostname resolution (prevents local IP leak via WebRTC)
            options.add_argument('--force-webrtc-ip-handling-policy=disable_non_proxied_udp')

            # Block third-party cookies by default (CloakBrowser technique — reduces tracking surface)
            options.add_argument('--disable-features=ThirdPartyCookies')

            # Headless mode (for automation/scraping)
            if profile_data and profile_data.get("headless"):
                options.add_argument('--headless=new')
                logger.info(f"Launching {profile_name} in headless mode")

            # Custom User-Agent if specified
            if profile_data and profile_data.get("user_agent"):
                options.add_argument(f'--user-agent={profile_data["user_agent"]}')
                logger.info(f"Using custom UA for {profile_name}")

            # Extension loading
            if profile_data and profile_data.get("extensions_enabled") and self.db:
                exts = self.db.list_extensions(profile_name)
                ext_paths = [e["path"] for e in exts if e["enabled"] and os.path.isdir(e["path"])]
                if ext_paths:
                    options.add_argument(f'--load-extension={",".join(ext_paths)}')
                    options.add_argument('--disable-extensions-except=' + ",".join(ext_paths))
                    logger.info(f"Loaded {len(ext_paths)} extensions for {profile_name}")

            # Proxy configuration
            if profile.proxy:
                options.add_argument(f'--proxy-server={profile.proxy}')
                # Explicitly bypass localhost so the local API server (test page) is reachable
                # Chrome bypasses <local> by default, but we make it explicit for reliability
                options.add_argument('--proxy-bypass-list=<local>')
                logger.info(f"Proxy configured with localhost bypass: {profile.proxy}")

            # Remote debugging port for CDP access (enables external automation)
            debug_port = random.randint(9223, 9999)
            options.add_argument(f'--remote-debugging-port={debug_port}')

            # Language and timezone
            locale = "en-US"
            if profile.timezone:
                # Set locale based on timezone for consistency
                tz_locale_map = {
                    "America/New_York": "en-US", "America/Chicago": "en-US",
                    "America/Denver": "en-US", "America/Los_Angeles": "en-US",
                    "Europe/London": "en-GB", "Europe/Paris": "fr-FR",
                    "Europe/Berlin": "de-DE", "Asia/Tokyo": "ja-JP",
                    "Asia/Shanghai": "zh-CN", "Asia/Seoul": "ko-KR",
                }
                locale = tz_locale_map.get(profile.timezone, "en-US")
            options.add_argument(f'--lang={locale}')

            # Accept-Language header
            options.add_argument(f'--accept-lang={locale},{locale.split("-")[0]}')

            # Launch with explicit browser binary path
            # Detect Chrome major version to avoid ChromeDriver version mismatch
            chrome_version = get_browser_version_major(browser_path, preferred_browser)
            uc_kwargs = dict(options=options, browser_executable_path=browser_path)
            if chrome_version:
                uc_kwargs["version_main"] = chrome_version
                logger.info(f"Detected Chrome major version: {chrome_version}")
            else:
                logger.warning("Could not detect Chrome version, using latest ChromeDriver (may cause version mismatch)")
            driver = uc.Chrome(**uc_kwargs)

            # Inject fingerprint protection via CDP
            # Pass proxy exit IP and geo data for full GeoIP auto-sync + WebRTC spoofing
            proxy_exit_ip = proxy_info.get("ip") if proxy_info.get("status") == "success" else None
            proxy_geo_data = {
                "latitude": proxy_info.get("latitude"),
                "longitude": proxy_info.get("longitude"),
                "country_code": proxy_info.get("country_code"),
            } if proxy_info.get("status") == "success" else None
            fingerprint = self._inject_fingerprint_via_cdp(driver, profile, proxy_ip=proxy_exit_ip, proxy_geo=proxy_geo_data)

            # Inject cookies from database if available
            if self.db:
                cookies = self.db.get_cookies(profile_name)
                if cookies:
                    for c in cookies:
                        try:
                            driver.execute_cdp_cmd('Network.setCookie', {
                                'name': c['name'],
                                'value': c['value'],
                                'domain': c['domain'],
                                'path': c.get('path', '/'),
                                'secure': c.get('secure', False),
                                'httpOnly': c.get('httpOnly', False),
                                'sameSite': c.get('sameSite', 'Lax'),
                            })
                        except Exception as ce:
                            logger.debug(f"Cookie inject error for {c.get('name')}: {ce}")
                    logger.info(f"Injected {len(cookies)} cookies for {profile_name}")

            # Track the driver
            self._drivers[profile_name] = driver

            # Initialize humanizer if enabled for this profile
            if profile_data and profile_data.get("humanize"):
                self._humanizers[profile_name] = Humanizer(driver)
                logger.info(f"Humanizer enabled for profile: {profile_name}")

            # Note: Proxy signal headers (Via, Proxy-Connection, X-Forwarded-For) are
            # added by the proxy server itself, not by the browser. CDP's
            # setExtraHTTPHeaders can only ADD headers, not remove them — setting
            # them to empty strings corrupts ALL outgoing requests (ERR_INVALID_ARGUMENT).
            # To properly strip these, a Fetch.requestPaused interception handler would
            # be needed. Skipped for now to avoid request corruption.

            # Update database state
            if self.db is not None:
                import time as _time
                self.db.update_profile(
                    profile_name,
                    is_running=True,
                    cdp_endpoint=f"http://127.0.0.1:{debug_port}",
                    last_used=_time.time(),
                )
                self.db.log_operation(profile_name, "launch", {"cdp_port": debug_port})

            logger.info(f"Browser launched successfully: {profile_name} (CDP: 127.0.0.1:{debug_port})")

            # Auto-open fingerprint test page so user can verify their fingerprint
            # We inject the test page directly via CDP (Page.setDocumentContent) instead
            # of navigating to the local API server. This avoids proxy routing issues:
            # when a SOCKS/HTTP proxy is active, 127.0.0.1 traffic may be forwarded to
            # the proxy server and time out. Injecting the HTML locally keeps the page
            # fully functional (external IP/DNS checks still run through the proxy).
            if self.api_port:
                try:
                    test_html_path = resource_path("src", "fingerprint", "test_page.html")
                    with open(test_html_path, "r", encoding="utf-8") as f:
                        test_html = f.read()
                    # Navigate to about:blank first, then replace the document content.
                    driver.get("about:blank")
                    driver.execute_cdp_cmd("Page.setDocumentContent", {"html": test_html})
                    logger.info(f"Injected fingerprint test page for {profile_name}")
                except Exception as te:
                    logger.warning(f"Could not inject test page: {te}")
                    # Fallback: try direct URL in case CDP injection fails
                    test_url = f"http://127.0.0.1:{self.api_port}/test"
                    try:
                        driver.get(test_url)
                        logger.info(f"Opened fingerprint test page via URL: {test_url}")
                    except Exception as te2:
                        logger.warning(f"Fallback test page URL also failed: {te2}")

            return driver

        except Exception as e:
            logger.error(f"Error launching browser: {str(e)}")
            raise

    def close_browser(self, profile_name: str):
        """Close a running browser instance, extract cookies, and clean up."""
        try:
            driver = self._drivers.pop(profile_name, None)
            # Clean up humanizer
            self._humanizers.pop(profile_name, None)
            if driver:
                # Extract cookies before closing
                if self.db:
                    try:
                        cookies = driver.execute_cdp_cmd('Network.getCookies', {})
                        cookie_list = cookies.get('cookies', [])
                        if cookie_list:
                            self.db.clear_cookies(profile_name)
                            self.db.add_cookies(profile_name, cookie_list)
                            logger.info(f"Extracted {len(cookie_list)} cookies from {profile_name}")
                    except Exception as ce:
                        logger.debug(f"Cookie extraction error: {ce}")

                try:
                    driver.quit()
                except Exception as e:
                    logger.warning(f"Driver quit error (may be already closed): {str(e)}")

            # Update database state
            if self.db is not None:
                self.db.update_profile(
                    profile_name,
                    is_running=False,
                    cdp_endpoint=None,
                )
                self.db.log_operation(profile_name, "stop")
            else:
                # Fallback: update JSON ProfileManager
                profile = self.profile_manager.get_profile(profile_name)
                if profile:
                    profile.driver = None
                    profile.is_running = False
                    profile.cdp_endpoint = None
                    self.profile_manager.save_profiles()

            logger.info(f"Browser closed: {profile_name}")
        except Exception as e:
            logger.error(f"Error closing browser: {str(e)}")
            raise

    def is_profile_running(self, profile_name: str) -> bool:
        return profile_name in self._drivers

    def get_humanizer(self, profile_name: str) -> Optional[Humanizer]:
        """Get the Humanizer instance for a running profile (if humanize is enabled)."""
        return self._humanizers.get(profile_name)

    def humanized_action(self, profile_name: str, action: str, **kwargs) -> Dict[str, Any]:
        """Execute a humanized action on a running browser.

        Actions: 'click', 'type', 'scroll', 'navigate', 'move', 'idle'
        """
        humanizer = self._humanizers.get(profile_name)
        driver = self._drivers.get(profile_name)
        if not driver:
            return {"status": "error", "message": f"Browser '{profile_name}' is not running"}

        # If humanizer not enabled, create a temporary one
        if not humanizer:
            humanizer = Humanizer(driver)

        try:
            if action == "click":
                x = kwargs.get("x", 0)
                y = kwargs.get("y", 0)
                selector = kwargs.get("selector")
                if selector:
                    element = driver.find_element("css selector", selector)
                    humanizer.click(element=element)
                else:
                    humanizer.click(x, y)
                return {"status": "success", "action": "click"}

            elif action == "type":
                selector = kwargs.get("selector")
                text = kwargs.get("text", "")
                if selector:
                    element = driver.find_element("css selector", selector)
                    humanizer.type_text(element, text)
                return {"status": "success", "action": "type"}

            elif action == "scroll":
                dx = kwargs.get("dx", 0)
                dy = kwargs.get("dy", 0)
                humanizer.scroll_by(dx, dy)
                return {"status": "success", "action": "scroll"}

            elif action == "navigate":
                url = kwargs.get("url", "")
                humanizer.human_navigate(url)
                return {"status": "success", "action": "navigate"}

            elif action == "move":
                x = kwargs.get("x", 0)
                y = kwargs.get("y", 0)
                humanizer.move_to(x, y)
                return {"status": "success", "action": "move"}

            elif action == "idle":
                duration = kwargs.get("duration", 2.0)
                humanizer.random_idle((0.5, duration))
                return {"status": "success", "action": "idle"}

            else:
                return {"status": "error", "message": f"Unknown action: {action}"}

        except Exception as e:
            logger.error(f"Humanized action '{action}' failed: {e}")
            return {"status": "error", "message": str(e)}

    def get_cdp_endpoint(self, profile_name: str) -> Optional[str]:
        """Get the CDP websocket endpoint for external automation (Selenium/Puppeteer)."""
        if self.db is not None:
            profile = self.db.get_profile(profile_name)
            if profile and profile.get("is_running"):
                return profile.get("cdp_endpoint")
        # Fallback to driver tracking
        if profile_name in self._drivers:
            return getattr(self._drivers[profile_name], 'cdp_endpoint', None)
        return None

    def launch_batch(self, profile_names: list, max_workers: int = 5) -> Dict[str, Any]:
        """Launch multiple browser profiles in parallel using ThreadPoolExecutor."""
        from concurrent.futures import ThreadPoolExecutor, as_completed
        results = {"launched": [], "failed": []}
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_name = {
                executor.submit(self.launch_browser, name): name
                for name in profile_names
            }
            for future in as_completed(future_to_name):
                name = future_to_name[future]
                try:
                    future.result()
                    results["launched"].append(name)
                except Exception as e:
                    results["failed"].append({"name": name, "error": str(e)})
        logger.info(f"Batch launch: {len(results['launched'])} succeeded, {len(results['failed'])} failed")
        return results

    def dns_leak_test(self, profile_name: str) -> Dict[str, Any]:
        """Perform a DNS leak test by checking if DNS queries go through the proxy."""
        if profile_name not in self._drivers:
            return {"status": "error", "message": "Browser not running"}
        try:
            driver = self._drivers[profile_name]
            # Use the browser to check DNS leak via a JS-based test
            driver.get("https://dnsleaktest.com/special/tools/dnsleak.php")
            import time as _t
            _t.sleep(5)
            page_source = driver.page_source
            # Check for DNS server IPs in the response
            has_leak = "your IP" in page_source.lower()
            return {
                "status": "warning" if has_leak else "ok",
                "message": "Potential DNS leak detected" if has_leak else "No DNS leak detected",
                "test_url": "https://dnsleaktest.com",
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def take_screenshot(self, profile_name: str) -> Optional[str]:
        """Take a screenshot of a running browser session."""
        if profile_name not in self._drivers:
            return None
        try:
            driver = self._drivers[profile_name]
            screenshot_dir = data_path("data", "screenshots")
            os.makedirs(screenshot_dir, exist_ok=True)
            import time as _t
            filepath = os.path.join(screenshot_dir, f"{profile_name}_{int(_t.time())}.png")
            driver.save_screenshot(filepath)
            logger.info(f"Screenshot saved: {filepath}")
            return filepath
        except Exception as e:
            logger.error(f"Screenshot error: {e}")
            return None
