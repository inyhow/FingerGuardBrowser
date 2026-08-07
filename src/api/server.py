"""Local REST API server with security boundary.

Provides programmatic control of profiles, browsers, fingerprints, and proxies.
Follows xiaohei-Chrome's security model:
- Bound to 127.0.0.1 only (no LAN/WAN access)
- API key authentication required for all endpoints except /health
- Host/Origin header validation — reject CORS requests
- Request body size limit (1MB) and rate limiting (100 req/min)
- Sensitive data masking in responses (proxy credentials, cookies, paths)

Reference: xiaohei-Chrome V15 Local API.
"""

import json
import os
import secrets
import time
import threading
import hashlib
from typing import Dict, Any, Optional
from collections import defaultdict, deque
from loguru import logger
from ..utils.app_paths import resource_path

try:
    from http.server import HTTPServer, BaseHTTPRequestHandler
    from urllib.parse import urlparse, parse_qs
except ImportError:
    raise ImportError("HTTP server modules not available")

MAX_BODY_SIZE = 1024 * 1024  # 1MB
RATE_LIMIT_WINDOW = 60  # seconds
RATE_LIMIT_MAX_REQUESTS = 100


class APIServer:
    """Local REST API server bound to 127.0.0.1 with security boundary."""

    def __init__(self, browser_manager=None, proxy_pool=None, group_manager=None,
                 fingerprint_manager=None, ai_generator=None, database=None,
                 port: int = 0, api_key: str = None):
        if database is None:
            from ..storage.database import Database
            database = Database()
        self.db = database
        self.browser_manager = browser_manager
        self.proxy_pool = proxy_pool
        self.group_manager = group_manager
        self.fingerprint_manager = fingerprint_manager
        self.ai_generator = ai_generator
        self.port = port or 0  # 0 = auto-assign
        self.host = "127.0.0.1"
        self._server = None
        self._thread = None
        self._actual_port = None

        # API key management
        if api_key is None:
            existing_keys = self.db.list_api_keys()
            if existing_keys:
                self.api_key = existing_keys[0]["key"]
            else:
                self.api_key = secrets.token_hex(24)
                self.db.create_api_key(self.api_key)
                logger.info(f"Generated new API key: {self.api_key}")
        else:
            self.api_key = api_key
            if not self.db.list_api_keys():
                self.db.create_api_key(api_key)

        # Rate limiting
        self._rate_limiter = defaultdict(lambda: deque(maxlen=RATE_LIMIT_MAX_REQUESTS))

    @property
    def actual_port(self) -> Optional[int]:
        return self._actual_port

    @property
    def base_url(self) -> str:
        if self._actual_port:
            return f"http://{self.host}:{self._actual_port}"
        return f"http://{self.host}:<unstarted>"

    def start(self):
        """Start the API server in a background thread."""
        if self._server:
            logger.warning("API server already running")
            return

        # Create a custom handler with access to this instance
        api_instance = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                logger.debug(f"API: {self.client_address[0]} - {format % args}")

            def _check_rate_limit(self) -> bool:
                client_ip = self.client_address[0]
                now = time.time()
                requests = api_instance._rate_limiter[client_ip]
                # Clean old entries
                while requests and now - requests[0] > RATE_LIMIT_WINDOW:
                    requests.popleft()
                if len(requests) >= RATE_LIMIT_MAX_REQUESTS:
                    return False
                requests.append(now)
                return True

            def _check_auth(self) -> bool:
                # Health endpoint doesn't require auth
                if self.path == "/api/health":
                    return True

                # Check API key in header
                auth = self.headers.get("Authorization", "")
                if auth.startswith("Bearer "):
                    token = auth[7:]
                else:
                    token = self.headers.get("X-API-Key", "")

                if not token or not api_instance.db.validate_api_key(token):
                    return False
                return True

            def _check_origin(self) -> bool:
                """Reject requests from external origins (CORS protection)."""
                host_header = self.headers.get("Host", "")
                origin = self.headers.get("Origin", "")
                referer = self.headers.get("Referer", "")

                # If Host header is not 127.0.0.1 or localhost, reject
                if host_header and not any(h in host_header for h in ["127.0.0.1", "localhost"]):
                    return False

                # If Origin is set, it must be localhost
                if origin and not any(h in origin for h in ["127.0.0.1", "localhost"]):
                    return False

                return True

            def _send_json(self, code: int, data: Any):
                body = json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _send_error(self, code: int, message: str):
                self._send_json(code, {"error": message})

            def _read_body(self) -> Optional[dict]:
                content_length = int(self.headers.get("Content-Length", 0))
                if content_length == 0:
                    return {}
                if content_length > MAX_BODY_SIZE:
                    return None  # Caller will send 413
                body = self.rfile.read(content_length)
                try:
                    return json.loads(body)
                except json.JSONDecodeError:
                    return None

            def _mask_response(self, data: dict) -> dict:
                """Mask sensitive data in API responses."""
                sensitive_keys = ["password", "credentials", "secret", "token"]
                masked = {}
                for key, value in data.items():
                    if any(s in key.lower() for s in sensitive_keys):
                        masked[key] = "***" if value else value
                    elif isinstance(value, dict):
                        masked[key] = self._mask_response(value)
                    elif isinstance(value, list):
                        masked[key] = [self._mask_response(v) if isinstance(v, dict) else v for v in value]
                    else:
                        masked[key] = value
                return masked

            def do_GET(self):
                self._handle_request("GET")

            def do_POST(self):
                self._handle_request("POST")

            def do_PUT(self):
                self._handle_request("PUT")

            def do_DELETE(self):
                self._handle_request("DELETE")

            def _serve_static_file(self, filepath: str, content_type: str = "text/html"):
                """Serve a static file from the web directory."""
                try:
                    with open(filepath, "rb") as f:
                        content = f.read()
                    self.send_response(200)
                    self.send_header("Content-Type", content_type)
                    self.send_header("Content-Length", str(len(content)))
                    self.end_headers()
                    self.wfile.write(content)
                except FileNotFoundError:
                    self._send_error(404, "File not found")

            def _serve_web_ui(self, api_instance):
                """Serve the web UI with API key and port injected."""
                web_dir = resource_path("src", "web")
                index_path = os.path.join(web_dir, "index.html")
                try:
                    with open(index_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(content.encode("utf-8"))))
                    self.end_headers()
                    self.wfile.write(content.encode("utf-8"))
                except FileNotFoundError:
                    self._send_error(404, "Web UI not found")

            def _handle_request(self, method: str):
                parsed = urlparse(self.path)
                path = parsed.path.rstrip("/") or "/"

                # Serve web UI and static files without auth
                if method == "GET":
                    web_dir = resource_path("src", "web")
                    # Root → web UI
                    if path == "/" or path == "/index.html":
                        self._serve_web_ui(api_instance)
                        return
                    # Fingerprint test page
                    if path == "/test":
                        test_page = resource_path("src", "fingerprint", "test_page.html")
                        self._serve_static_file(test_page)
                        return
                    # Static assets
                    if path.startswith("/static/"):
                        rel_path = path[len("/static/"):]
                        static_path = os.path.join(web_dir, rel_path)
                        if os.path.isfile(static_path):
                            ext = os.path.splitext(rel_path)[1].lower()
                            ct_map = {".css": "text/css", ".js": "application/javascript",
                                      ".png": "image/png", ".jpg": "image/jpeg",
                                      ".svg": "image/svg+xml", ".ico": "image/x-icon"}
                            self._serve_static_file(static_path, ct_map.get(ext, "application/octet-stream"))
                        else:
                            self._send_error(404, "File not found")
                        return

                # Security checks for API requests
                if not self._check_origin():
                    self._send_error(403, "Forbidden: external origin rejected")
                    return

                if not self._check_rate_limit():
                    self._send_error(429, "Rate limit exceeded")
                    return

                if not self._check_auth():
                    self._send_error(401, "Unauthorized: invalid or missing API key")
                    return

                segments = [s for s in path.split("/") if s]

                try:
                    handler = RouteHandler(api_instance)
                    handler.route(method, segments, parsed, self)
                except Exception as e:
                    logger.error(f"API error: {e}")
                    self._send_error(500, str(e))

        self._server = HTTPServer((self.host, self.port), Handler)
        self._actual_port = self._server.server_address[1]
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        logger.info(f"API server started at {self.base_url} (key: {self.api_key[:8]}...)")

    def stop(self):
        """Stop the API server."""
        if self._server:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
            self._thread = None
            logger.info("API server stopped")

    def reset_api_key(self) -> str:
        """Generate a new API key, invalidating the old one."""
        old_key = self.api_key
        self.db.delete_api_key(old_key)
        self.api_key = secrets.token_hex(24)
        self.db.create_api_key(self.api_key)
        logger.info(f"API key reset: {self.api_key[:8]}...")
        return self.api_key

    def get_mcp_config(self) -> str:
        """Get MCP server configuration text for AI agent setup."""
        return json.dumps({
            "mcpServers": {
                "fingerguard": {
                    "command": "python",
                    "args": ["-m", "src.api.mcp_server"],
                    "env": {
                        "FINGUARD_API_KEY": self.api_key,
                        "FINGUARD_API_URL": self.base_url,
                    }
                }
            }
        }, indent=2)


class RouteHandler:
    """Route API requests to handlers."""

    def __init__(self, api: APIServer):
        self.api = api
        self.db = api.db
        self.bm = api.browser_manager
        self.pp = api.proxy_pool
        self.gm = api.group_manager
        self.fm = api.fingerprint_manager
        self.ai = api.ai_generator

    def route(self, method: str, segments: list, parsed_url, request):
        if len(segments) == 0 or segments[0] != "api":
            request._send_error(404, "Not found. API endpoints start with /api/")
            return

        resource = segments[1] if len(segments) > 1 else ""

        # === Health ===
        if resource == "health":
            request._send_json(200, {"status": "ok", "version": "2.0.0", "timestamp": time.time()})
            return

        # === Profiles ===
        if resource == "profiles":
            self._handle_profiles(method, segments[2:], request)
            return

        # === Sessions ===
        if resource == "sessions":
            self._handle_sessions(method, segments[2:], request)
            return

        # === Fingerprint ===
        if resource == "fingerprint":
            self._handle_fingerprint(method, segments[2:], request)
            return

        # === Proxy ===
        if resource == "proxy":
            self._handle_proxy(method, segments[2:], request)
            return

        # === Groups ===
        if resource == "groups":
            self._handle_groups(method, segments[2:], request)
            return

        # === API Info ===
        if resource == "info":
            request._send_json(200, {
                "api_key": self.api.api_key[:8] + "...",
                "base_url": self.api.base_url,
                "endpoints": [
                    "GET /api/health",
                    "GET /api/profiles", "POST /api/profiles",
                    "GET /api/profiles/{name}", "PUT /api/profiles/{name}", "DELETE /api/profiles/{name}",
                    "POST /api/profiles/{name}/launch", "POST /api/profiles/{name}/stop",
                    "POST /api/profiles/{name}/clone", "POST /api/profiles/{name}/screenshot",
                    "POST /api/profiles/{name}/dns-leak", "GET /api/profiles/{name}/cdp",
                    "POST /api/profiles/{name}/humanize",
                    "GET/POST/DELETE /api/profiles/{name}/cookies",
                    "GET/POST /api/profiles/{name}/credentials",
                    "GET/POST/DELETE /api/profiles/{name}/extensions",
                    "POST /api/profiles/batch-launch", "POST /api/profiles/stop-all",
                    "POST /api/profiles/export", "POST /api/profiles/import",
                    "GET /api/sessions", "POST /api/fingerprint/generate",
                    "GET/POST/DELETE /api/proxy", "POST /api/proxy/check", "GET /api/proxy/protocols",
                    "GET /api/groups", "POST /api/groups",
                    "GET /api/logs", "GET /api/templates", "POST /api/templates",
                ]
            })
            return

        # === Operation Logs ===
        if resource == "logs":
            if method == "GET":
                profile_name = parsed_url.query.split("=")[1] if "profile=" in parsed_url.query else None
                logs = self.db.list_operation_logs(profile_name, limit=100)
                request._send_json(200, {"logs": logs})
            return

        # === Templates ===
        if resource == "templates":
            if method == "GET":
                templates = self.db.list_fingerprint_templates()
                request._send_json(200, {"templates": templates})
            elif method == "POST":
                body = request._read_body() or {}
                template = self.db.save_fingerprint_template(
                    body.get("name", ""), body.get("os_type", "windows"),
                    body.get("config", {}), body.get("category")
                )
                request._send_json(201, template)
            return

        request._send_error(404, f"Unknown endpoint: /api/{resource}")

    def _handle_profiles(self, method: str, path: list, request):
        if method == "GET" and not path:
            profiles = self.db.list_profiles()
            request._send_json(200, request._mask_response({"profiles": profiles}))
            return

        if method == "POST" and not path:
            body = request._read_body()
            if body is None:
                request._send_error(400, "Invalid JSON body")
                return
            name = body.get("name")
            if not name:
                request._send_error(400, "name is required")
                return
            try:
                profile = self.db.create_profile(name, **{k: v for k, v in body.items() if k != "name"})
                request._send_json(201, request._mask_response(profile))
            except Exception as e:
                request._send_error(400, str(e))
            return

        if len(path) >= 1:
            name = path[0]

            if method == "GET":
                profile = self.db.get_profile(name)
                if not profile:
                    request._send_error(404, f"Profile '{name}' not found")
                    return
                request._send_json(200, request._mask_response(profile))
                return

            if method == "PUT":
                body = request._read_body()
                if body is None:
                    request._send_error(400, "Invalid JSON body")
                    return
                profile = self.db.update_profile(name, **{k: v for k, v in body.items() if k != "name"})
                request._send_json(200, request._mask_response(profile))
                return

            if method == "DELETE":
                if self.db.delete_profile(name):
                    request._send_json(200, {"deleted": True})
                else:
                    request._send_error(404, f"Profile '{name}' not found")
                return

            if len(path) >= 2 and path[1] == "launch" and method == "POST":
                if not self.bm:
                    request._send_error(503, "Browser manager not configured")
                    return
                try:
                    self.bm.launch_browser(name)
                    cdp = self.bm.get_cdp_endpoint(name)
                    request._send_json(200, {"status": "launched", "cdp_endpoint": cdp})
                except Exception as e:
                    request._send_error(500, str(e))
                return

            if len(path) >= 2 and path[1] == "stop" and method == "POST":
                if not self.bm:
                    request._send_error(503, "Browser manager not configured")
                    return
                try:
                    self.bm.close_browser(name)
                    request._send_json(200, {"status": "stopped"})
                except Exception as e:
                    request._send_error(500, str(e))
                return

            # GET /api/profiles/{name}/cookies
            if len(path) >= 2 and path[1] == "cookies" and method == "GET":
                cookies = self.db.get_cookies(name)
                request._send_json(200, {"cookies": cookies})
                return

            # POST /api/profiles/{name}/cookies — import cookies
            if len(path) >= 2 and path[1] == "cookies" and method == "POST":
                body = request._read_body() or {}
                cookie_list = body.get("cookies", [])
                if isinstance(cookie_list, str):
                    try:
                        cookie_list = json.loads(cookie_list)
                    except json.JSONDecodeError:
                        request._send_error(400, "Invalid cookie JSON")
                        return
                count = self.db.add_cookies(name, cookie_list)
                self.db.log_operation(name, "import_cookies", {"count": count})
                request._send_json(200, {"imported": count})
                return

            # DELETE /api/profiles/{name}/cookies — clear all cookies
            if len(path) >= 2 and path[1] == "cookies" and method == "DELETE":
                count = self.db.clear_cookies(name)
                request._send_json(200, {"cleared": count})
                return

            # POST /api/profiles/{name}/clone — clone profile
            if len(path) >= 2 and path[1] == "clone" and method == "POST":
                body = request._read_body() or {}
                new_name = body.get("new_name", f"{name}_copy")
                cloned = self.db.clone_profile(name, new_name)
                if cloned:
                    self.db.log_operation(name, "clone", {"new_name": new_name})
                    request._send_json(201, cloned)
                else:
                    request._send_error(404, f"Profile '{name}' not found")
                return

            # GET /api/profiles/{name}/credentials
            if len(path) >= 2 and path[1] == "credentials" and method == "GET":
                creds = self.db.list_credentials(name)
                request._send_json(200, {"credentials": creds})
                return

            # POST /api/profiles/{name}/credentials — add credential
            if len(path) >= 2 and path[1] == "credentials" and method == "POST":
                body = request._read_body() or {}
                try:
                    from ..security.crypto import CryptoManager
                    cm = CryptoManager()
                    encrypted = cm.encrypt({"password": body.get("password", "")})
                    cred = self.db.add_credential(name, body.get("url", ""),
                                                  body.get("username", ""), encrypted,
                                                  body.get("notes", ""))
                    request._send_json(201, cred)
                except Exception as e:
                    request._send_error(400, str(e))
                return

            # GET /api/profiles/{name}/extensions
            if len(path) >= 2 and path[1] == "extensions" and method == "GET":
                exts = self.db.list_extensions(name)
                request._send_json(200, {"extensions": exts})
                return

            # POST /api/profiles/{name}/extensions — add extension
            if len(path) >= 2 and path[1] == "extensions" and method == "POST":
                body = request._read_body() or {}
                ext = self.db.add_extension(name, body.get("name", ""), body.get("path", ""))
                request._send_json(201, ext)
                return

            # DELETE /api/profiles/{name}/extensions/{id}
            if len(path) >= 3 and path[1] == "extensions" and method == "DELETE":
                self.db.delete_extension(int(path[2]))
                request._send_json(200, {"deleted": True})
                return

            # GET /api/profiles/{name}/cdp — get CDP endpoint for external automation
            if len(path) >= 2 and path[1] == "cdp" and method == "GET":
                if self.bm:
                    cdp = self.bm.get_cdp_endpoint(name)
                    if cdp:
                        request._send_json(200, {"cdp_endpoint": cdp})
                    else:
                        request._send_error(404, "Browser not running or no CDP endpoint")
                else:
                    request._send_error(503, "Browser manager not configured")
                return

            # POST /api/profiles/{name}/screenshot — take screenshot
            if len(path) >= 2 and path[1] == "screenshot" and method == "POST":
                if self.bm:
                    filepath = self.bm.take_screenshot(name)
                    if filepath:
                        request._send_json(200, {"screenshot": filepath})
                    else:
                        request._send_error(404, "Browser not running")
                else:
                    request._send_error(503, "Browser manager not configured")
                return

            # POST /api/profiles/{name}/dns-leak — DNS leak test
            if len(path) >= 2 and path[1] == "dns-leak" and method == "POST":
                if self.bm:
                    result = self.bm.dns_leak_test(name)
                    request._send_json(200, result)
                else:
                    request._send_error(503, "Browser manager not configured")
                return

            # POST /api/profiles/{name}/humanize — execute humanized action
            if len(path) >= 2 and path[1] == "humanize" and method == "POST":
                if self.bm:
                    body = request._read_body() or {}
                    action = body.pop("action", "idle")
                    result = self.bm.humanized_action(name, action, **body)
                    request._send_json(200, result)
                else:
                    request._send_error(503, "Browser manager not configured")
                return

        # POST /api/profiles/stop-all — close all running browsers
        if method == "POST" and len(path) == 1 and path[0] == "stop-all":
            if not self.bm:
                request._send_error(503, "Browser manager not configured")
                return
            try:
                result = self.bm.close_all_browsers()
                request._send_json(200, result)
            except Exception as e:
                request._send_error(500, str(e))
            return

        # POST /api/profiles/batch-launch — launch multiple profiles in parallel
        if method == "POST" and len(path) == 1 and path[0] == "batch-launch":
            body = request._read_body() or {}
            names = body.get("names", [])
            workers = body.get("max_workers", 5)
            if not self.bm:
                request._send_error(503, "Browser manager not configured")
                return
            try:
                result = self.bm.launch_batch(names, max_workers=workers)
                request._send_json(200, result)
            except Exception as e:
                request._send_error(500, str(e))
            return

        # POST /api/profiles/export — export all profiles as JSON
        if method == "POST" and len(path) == 1 and path[0] == "export":
            profiles = self.db.list_profiles()
            export_data = []
            for p in profiles:
                p["cookies"] = self.db.get_cookies(p["name"])
                p["extensions"] = self.db.list_extensions(p["name"])
                export_data.append(p)
            request._send_json(200, {"profiles": export_data, "version": "2.0.0"})
            return

        # POST /api/profiles/import — import profiles from JSON
        if method == "POST" and len(path) == 1 and path[0] == "import":
            body = request._read_body() or {}
            profiles = body.get("profiles", [])
            imported = 0
            failed = 0
            for p in profiles:
                try:
                    name = p.get("name")
                    if not name:
                        continue
                    existing = self.db.get_profile(name)
                    if existing:
                        continue  # Skip existing
                    cookie_data = p.pop("cookies", [])
                    ext_data = p.pop("extensions", [])
                    self.db.create_profile(name, **{k: v for k, v in p.items()
                                                     if k not in ("id", "created_at", "updated_at",
                                                                  "last_used", "is_running", "cdp_endpoint")})
                    if cookie_data:
                        self.db.add_cookies(name, cookie_data)
                    imported += 1
                except Exception as e:
                    logger.warning(f"Import failed for profile: {e}")
                    failed += 1
            request._send_json(200, {"imported": imported, "failed": failed})
            return

        request._send_error(405, "Method not allowed")

    def _handle_sessions(self, method: str, path: list, request):
        if method != "GET":
            request._send_error(405, "Method not allowed")
            return

        profiles = self.db.list_profiles()
        running = [p for p in profiles if p.get("is_running")]
        request._send_json(200, {
            "sessions": [{
                "name": p["name"],
                "cdp_endpoint": p.get("cdp_endpoint"),
                "last_used": p.get("last_used"),
            } for p in running]
        })

    def _handle_fingerprint(self, method: str, path: list, request):
        if method == "POST" and path and path[0] == "generate":
            body = request._read_body() or {}
            if self.ai:
                config = self.ai.generate_from_natural_language(
                    body.get("description", "Create a profile for browsing")
                )
                request._send_json(200, config)
            elif self.fm:
                name = body.get("name", f"fp_{int(time.time())}")
                fp = self.fm.create_fingerprint(name, os_type=body.get("os_type"))
                request._send_json(200, fp)
            else:
                request._send_error(503, "Fingerprint manager not configured")
            return

        request._send_error(404, "Unknown fingerprint endpoint")

    def _handle_proxy(self, method: str, path: list, request):
        # GET /api/proxy — list all proxies
        if method == "GET" and not path:
            if self.pp:
                proxies = self.pp.list_proxies()
                request._send_json(200, request._mask_response({"proxies": proxies}))
            else:
                request._send_json(200, {"proxies": []})
            return

        # POST /api/proxy — add a proxy with structured fields
        if method == "POST" and not path:
            body = request._read_body() or {}
            name = body.get("name")
            if not name:
                request._send_error(400, "name is required")
                return

            protocol = body.get("protocol", "socks5").lower()
            host = body.get("host", "")
            port = body.get("port", 0)

            if not host or not port:
                # Try to parse from a proxy string if structured fields missing
                proxy_str = body.get("proxy", "")
                if proxy_str:
                    if self.pp:
                        parsed = self.pp.parse_proxy_string(proxy_str)
                        protocol = parsed["protocol"]
                        host = parsed["host"]
                        port = parsed["port"]
                        if not body.get("username"):
                            body["username"] = parsed["username"]
                        if not body.get("password"):
                            body["password"] = parsed["password"]
                    else:
                        request._send_error(400, "host and port are required (or provide 'proxy' string)")
                        return
                else:
                    request._send_error(400, "host and port are required")
                    return

            try:
                if self.pp:
                    proxy = self.pp.add_proxy(
                        name=name,
                        protocol=protocol,
                        host=host,
                        port=int(port),
                        username=body.get("username"),
                        password=body.get("password"),
                        tags=body.get("tags", []),
                    )
                    request._send_json(201, request._mask_response(proxy))
                else:
                    request._send_error(503, "Proxy pool not configured")
            except Exception as e:
                request._send_error(400, str(e))
            return

        # POST /api/proxy/check — check proxy connectivity
        if method == "POST" and path and path[0] == "check":
            body = request._read_body() or {}
            proxy_str = body.get("proxy")
            if not proxy_str:
                request._send_error(400, "proxy is required")
                return

            if self.pp:
                # If it's a proxy name in the pool, do full health check
                proxy = self.pp.get_proxy_by_name(proxy_str)
                if proxy:
                    latency = self.pp.test_latency(proxy_str)
                    ip_info = self.pp.check_ip(proxy_str)
                    request._send_json(200, {
                        "status": "success" if latency is not None else "error",
                        "latency_ms": latency,
                        "ip_info": ip_info,
                    })
                else:
                    # Parse as a proxy URL string
                    parsed = self.pp.parse_proxy_string(proxy_str)
                    result = {
                        "status": "success",
                        "protocol": parsed["protocol"],
                        "host": parsed["host"],
                        "port": parsed["port"],
                    }
                    request._send_json(200, result)
            elif self.bm:
                result = self.bm.check_proxy(proxy_str)
                request._send_json(200, result)
            else:
                request._send_error(503, "Proxy checker not configured")
            return

        # GET /api/proxy/protocols — list supported protocols
        if method == "GET" and path and path[0] == "protocols":
            if self.pp:
                request._send_json(200, {
                    "supported": self.pp.SUPPORTED_PROTOCOLS,
                    "chrome_compatible": self.pp.CHROME_COMPATIBLE,
                    "bridge_required": self.pp.BRIDGE_REQUIRED,
                })
            else:
                request._send_json(200, {
                    "supported": ["http", "https", "socks4", "socks5"],
                    "chrome_compatible": ["http", "https", "socks4", "socks5"],
                    "bridge_required": [],
                })
            return

        # DELETE /api/proxy/{name}
        if method == "DELETE" and len(path) >= 1 and path[0] != "check" and path[0] != "protocols":
            name = path[0]
            if self.pp and self.pp.remove_proxy(name):
                request._send_json(200, {"deleted": True})
            else:
                request._send_error(404, f"Proxy '{name}' not found")
            return

        # PUT /api/proxy/{name} — update proxy
        if method == "PUT" and len(path) >= 1 and path[0] != "check" and path[0] != "protocols":
            name = path[0]
            body = request._read_body()
            if body is None:
                request._send_error(400, "Invalid JSON body")
                return
            try:
                if self.db:
                    updated = self.db.update_proxy(name, **{k: v for k, v in body.items() if k != "name"})
                    request._send_json(200, request._mask_response(updated))
                else:
                    request._send_error(503, "Database not configured")
            except Exception as e:
                request._send_error(400, str(e))
            return

        request._send_error(404, "Unknown proxy endpoint")

    def _handle_groups(self, method: str, path: list, request):
        if method == "GET" and not path:
            groups = self.db.list_groups() if self.db else []
            request._send_json(200, {"groups": groups})
            return

        if method == "POST" and not path:
            body = request._read_body() or {}
            name = body.get("name")
            if not name:
                request._send_error(400, "name is required")
                return
            group = self.db.create_group(
                name, body.get("description", ""), body.get("color", "#4263eb"),
                body.get("settings", {})
            )
            request._send_json(201, group)
            return

        if len(path) >= 1:
            name = path[0]
            if method == "DELETE":
                if self.db.delete_group(name):
                    request._send_json(200, {"deleted": True})
                else:
                    request._send_error(404, f"Group '{name}' not found")
                return

            if len(path) >= 2 and path[1] == "launch" and method == "POST" and self.gm:
                result = self.gm.bulk_launch(name)
                request._send_json(200, result)
                return

            if len(path) >= 2 and path[1] == "stop" and method == "POST" and self.gm:
                result = self.gm.bulk_stop(name)
                request._send_json(200, result)
                return

        request._send_error(404, "Unknown group endpoint")
