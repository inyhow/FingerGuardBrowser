"""Centralized proxy pool management with health checks and multi-protocol support.

Supports: HTTP, HTTPS, SOCKS4, SOCKS5 (and extensible for vmess/vless/trojan/ss via Xray bridge).
Features:
- Latency testing (TCP connect time)
- IP health checks with multi-source geo verification
- Proxy rotation rules (per-session, time-based)
- Import/export in standard formats
- Failure detection and automatic unhealthy marking

Reference: Ant Browser's unified proxy node management.
"""

import json
import os
import socket
import time
import threading
import random
from typing import Dict, Any, Optional, List
from loguru import logger

try:
    import requests
except ImportError:
    requests = None


class ProxyPool:
    """Centralized proxy pool with health monitoring and rotation."""

    SUPPORTED_PROTOCOLS = ["http", "https", "socks4", "socks5", "socks5h",
                           "vmess", "vless", "trojan", "ss", "ssr", "ssh",
                           "l2tp", "pptp", "wireguard", "openvpn"]

    # Protocols that can be used directly as Chrome --proxy-server
    CHROME_COMPATIBLE = ["http", "https", "socks4", "socks5", "socks5h"]

    # Protocols that require a local proxy bridge (Xray/sing-box/Mihomo/strongSwan)
    BRIDGE_REQUIRED = ["vmess", "vless", "trojan", "ss", "ssr", "ssh",
                       "l2tp", "pptp", "wireguard", "openvpn"]

    def __init__(self, database=None):
        # Avoid circular import — accept database instance
        if database is None:
            from ..storage.database import Database
            database = Database()
        self.db = database
        self._rotation_state: Dict[str, int] = {}  # group_name -> current_index
        self._lock = threading.Lock()

    def add_proxy(self, name: str, protocol: str, host: str, port: int,
                  username: str = None, password: str = None,
                  tags: list = None) -> Dict[str, Any]:
        """Add a proxy to the pool."""
        protocol = protocol.lower()
        if protocol not in self.SUPPORTED_PROTOCOLS:
            raise ValueError(f"Unsupported protocol: {protocol}. Supported: {self.SUPPORTED_PROTOCOLS}")

        proxy = self.db.add_proxy(name, protocol, host, port, username, password, tags)
        logger.info(f"Added proxy: {name} ({protocol}://{host}:{port})")
        return proxy

    def remove_proxy(self, name: str) -> bool:
        """Remove a proxy from the pool."""
        result = self.db.delete_proxy(name)
        if result:
            logger.info(f"Removed proxy: {name}")
        return result

    def list_proxies(self, healthy_only: bool = False) -> List[Dict[str, Any]]:
        """List all proxies in the pool."""
        return self.db.list_proxies(healthy_only)

    def get_proxy_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a specific proxy by name."""
        return self.db.get_proxy(name)

    def get_proxy_url(self, name: str) -> Optional[str]:
        """Get a proxy URL string suitable for Chrome --proxy-server flag.

        For Chrome-compatible protocols (http, https, socks4, socks5), returns the URL directly.
        For bridge-required protocols (vmess, vless, trojan, ss, ssr), returns None —
        these need a local proxy bridge (Xray/sing-box) that exposes a SOCKS5 port.
        """
        proxy = self.db.get_proxy(name)
        if not proxy:
            return None

        protocol = proxy["protocol"]
        host = proxy["host"]
        port = proxy["port"]

        if protocol in ("http", "https"):
            return f"http://{host}:{port}"
        elif protocol == "socks4":
            return f"socks4://{host}:{port}"
        elif protocol in ("socks5", "socks5h"):
            return f"socks5://{host}:{port}"
        elif protocol in self.BRIDGE_REQUIRED:
            logger.warning(
                f"Protocol '{protocol}' requires a local proxy bridge. "
                f"Configure Xray/sing-box to convert to SOCKS5, then use the SOCKS5 port."
            )
            return None
        return f"{protocol}://{host}:{port}"

    def is_chrome_compatible(self, name: str) -> bool:
        """Check if a proxy can be used directly with Chrome."""
        proxy = self.db.get_proxy(name)
        if not proxy:
            return False
        return proxy["protocol"] in self.CHROME_COMPATIBLE

    def build_proxy_url_with_auth(self, protocol: str, host: str, port: int,
                                   username: str = None, password: str = None) -> str:
        """Build a proxy URL string with optional authentication.

        For Chrome --proxy-server flag, auth is NOT included (Chrome doesn't support it in the flag).
        Auth is handled separately via a Chrome extension or CDP.
        """
        if protocol in ("http", "https"):
            return f"http://{host}:{port}"
        elif protocol == "socks4":
            return f"socks4://{host}:{port}"
        elif protocol in ("socks5", "socks5h"):
            return f"socks5://{host}:{port}"
        else:
            # For bridge protocols, return full URL with auth for reference
            if username and password:
                return f"{protocol}://{username}:{password}@{host}:{port}"
            return f"{protocol}://{host}:{port}"

    def test_latency(self, name: str, timeout: float = 5.0) -> Optional[int]:
        """Test TCP connect latency to a proxy in milliseconds."""
        proxy = self.db.get_proxy(name)
        if not proxy:
            return None

        try:
            start = time.time()
            sock = socket.create_connection(
                (proxy["host"], proxy["port"]),
                timeout=timeout
            )
            elapsed = (time.time() - start) * 1000
            sock.close()

            latency = int(elapsed)
            self.db.update_proxy(name, latency_ms=latency, last_checked=time.time(), is_healthy=True)
            return latency
        except (socket.timeout, ConnectionRefusedError, OSError) as e:
            logger.warning(f"Latency test failed for {name}: {e}")
            self.db.update_proxy(name, is_healthy=False, last_checked=time.time())
            return None

    def check_ip(self, name: str) -> Dict[str, Any]:
        """Check the exit IP and geolocation of a proxy using multiple sources."""
        proxy = self.db.get_proxy(name)
        if not proxy:
            return {"status": "error", "message": "Proxy not found"}

        proxy_url = self.get_proxy_url(name)
        if not proxy_url:
            return {"status": "error", "message": "Cannot construct proxy URL"}

        if requests is None:
            return {"status": "error", "message": "requests library not installed"}

        proxies = {"http": proxy_url, "https": proxy_url}

        # Multi-source geo-IP verification (all HTTPS)
        geo_sources = [
            {
                "url": "https://ipapi.co/json/",
                "parser": lambda d: {
                    "status": "success",
                    "ip": d.get("ip"),
                    "country": d.get("country_name"),
                    "country_code": d.get("country_code"),
                    "city": d.get("city"),
                    "isp": d.get("org"),
                    "timezone": d.get("timezone"),
                    "asn": d.get("asn"),
                } if d.get("ip") else {"status": "error", "message": "No IP"}
            },
            {
                "url": "https://ipwho.is/",
                "parser": lambda d: {
                    "status": "success",
                    "ip": d.get("ip"),
                    "country": d.get("country"),
                    "country_code": d.get("country_code"),
                    "city": d.get("city"),
                    "isp": d.get("connection", {}).get("isp") if isinstance(d.get("connection"), dict) else None,
                    "timezone": d.get("timezone", {}).get("id") if isinstance(d.get("timezone"), dict) else None,
                    "asn": d.get("connection", {}).get("asn") if isinstance(d.get("connection"), dict) else None,
                } if d.get("success") else {"status": "error", "message": d.get("message", "Unknown")}
            },
        ]

        for source in geo_sources:
            try:
                response = requests.get(source["url"], proxies=proxies, timeout=15, verify=True)
                if response.status_code == 200:
                    data = response.json()
                    result = source["parser"](data)
                    if result["status"] == "success":
                        # Update proxy record
                        self.db.update_proxy(
                            name,
                            country=result.get("country"),
                            country_code=result.get("country_code"),
                            city=result.get("city"),
                            isp=result.get("isp"),
                            asn=result.get("asn"),
                            is_healthy=True,
                            last_checked=time.time(),
                        )
                        return result
            except requests.exceptions.ProxyError:
                logger.warning(f"Proxy error checking {name} via {source['url']}")
                continue
            except requests.exceptions.Timeout:
                logger.warning(f"Timeout checking {name} via {source['url']}")
                continue
            except Exception as e:
                logger.warning(f"Error checking {name} via {source['url']}: {e}")
                continue

        self.db.update_proxy(name, is_healthy=False, last_checked=time.time())
        return {"status": "error", "message": "All geo-IP sources failed"}

    def check_all_proxies(self) -> List[Dict[str, Any]]:
        """Run health check on all proxies. Returns results per proxy."""
        proxies = self.list_proxies()
        results = []
        for proxy in proxies:
            latency = self.test_latency(proxy["name"])
            if latency is not None:
                ip_info = self.check_ip(proxy["name"])
                results.append({
                    "name": proxy["name"],
                    "latency_ms": latency,
                    "ip_info": ip_info,
                    "healthy": True,
                })
            else:
                results.append({
                    "name": proxy["name"],
                    "latency_ms": None,
                    "ip_info": None,
                    "healthy": False,
                })
        return results

    def get_healthy_proxy(self, tags: list = None) -> Optional[Dict[str, Any]]:
        """Get a random healthy proxy, optionally filtered by tags."""
        proxies = self.list_proxies(healthy_only=True)
        if tags:
            proxies = [p for p in proxies if any(t in p.get("tags", []) for t in tags)]
        if not proxies:
            return None
        return random.choice(proxies)

    def rotate_proxy(self, group_name: str = None) -> Optional[Dict[str, Any]]:
        """Get the next proxy in rotation. If group_name is given, rotate within that group's proxies."""
        with self._lock:
            proxies = self.list_proxies(healthy_only=True)
            if not proxies:
                return None

            key = group_name or "default"
            if key not in self._rotation_state:
                self._rotation_state[key] = 0

            idx = self._rotation_state[key] % len(proxies)
            self._rotation_state[key] = (idx + 1) % len(proxies)
            return proxies[idx]

    def import_proxies(self, file_path: str) -> int:
        """Import proxies from a JSON or CSV file.

        JSON format: [{"name": "...", "protocol": "...", "host": "...", "port": 1234, ...}, ...]
        CSV format: name,protocol,host,port,username,password
        """
        count = 0
        _, ext = os.path.splitext(file_path)

        if ext.lower() == ".json":
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for item in data:
                try:
                    self.add_proxy(
                        name=item["name"],
                        protocol=item.get("protocol", "socks5"),
                        host=item["host"],
                        port=int(item["port"]),
                        username=item.get("username"),
                        password=item.get("password"),
                        tags=item.get("tags", []),
                    )
                    count += 1
                except Exception as e:
                    logger.warning(f"Failed to import proxy {item.get('name')}: {e}")

        elif ext.lower() == ".csv":
            import csv
            with open(file_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        self.add_proxy(
                            name=row["name"],
                            protocol=row.get("protocol", "socks5"),
                            host=row["host"],
                            port=int(row["port"]),
                            username=row.get("username") or None,
                            password=row.get("password") or None,
                        )
                        count += 1
                    except Exception as e:
                        logger.warning(f"Failed to import proxy {row.get('name')}: {e}")
        else:
            raise ValueError(f"Unsupported file format: {ext}")

        logger.info(f"Imported {count} proxies from {file_path}")
        return count

    def export_proxies(self, file_path: str, include_credentials: bool = False) -> int:
        """Export proxies to a JSON file."""
        proxies = self.list_proxies()
        if not include_credentials:
            for p in proxies:
                p.pop("username", None)
                p.pop("password", None)

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(proxies, f, indent=2, ensure_ascii=False)

        logger.info(f"Exported {len(proxies)} proxies to {file_path}")
        return len(proxies)

    def parse_proxy_string(self, proxy_str: str) -> Dict[str, Any]:
        """Parse a proxy URL string into components.

        Examples:
            socks5://user:pass@host:port
            http://host:port
            host:port (defaults to socks5)
        """
        from urllib.parse import urlparse

        if "://" not in proxy_str:
            proxy_str = "socks5://" + proxy_str

        parsed = urlparse(proxy_str)
        return {
            "protocol": parsed.scheme or "socks5",
            "host": parsed.hostname or "",
            "port": parsed.port or 1080,
            "username": parsed.username,
            "password": parsed.password,
        }
