"""SQLite-based storage layer replacing JSON file storage.

Provides ACID transactions, concurrent access safety, indexed queries,
and encrypted storage for sensitive data (proxy credentials, cookies).

Migration from existing JSON profiles is automatic on first init.
"""

import json
import os
import sqlite3
import time
import threading
from typing import Dict, Any, Optional, List
from loguru import logger
from ..utils.app_paths import data_path, resource_path


class Database:
    """Thread-safe SQLite database for profile, proxy, group, and settings storage."""

    _instance: Optional["Database"] = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        """Singleton — all modules share the same database connection pool."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
            return cls._instance

    def __init__(self, db_path: str = None):
        if hasattr(self, "_initialized") and self._initialized:
            return

        if db_path is None:
            db_path = data_path("data", "fingerguard.db")

        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self._local = threading.local()
        self._initialized = True
        self._init_schema()
        self._migrate_json_profiles()
        self._migrate_add_columns()
        logger.info(f"Database initialized at {db_path}")

    def _get_conn(self) -> sqlite3.Connection:
        """Get a thread-local connection."""
        if not hasattr(self._local, "conn"):
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            self._local.conn = conn
        return self._local.conn

    def _init_schema(self):
        """Create tables if they don't exist."""
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                group_id INTEGER,
                proxy TEXT,
                timezone TEXT,
                webrtc TEXT DEFAULT 'filter',
                canvas_fp INTEGER DEFAULT 1,
                webgl_fp INTEGER DEFAULT 1,
                audio_fp INTEGER DEFAULT 1,
                client_rects_fp INTEGER DEFAULT 1,
                dns_protection TEXT DEFAULT 'cloudflare',
                custom_dns TEXT DEFAULT '',
                dns_leak_protection INTEGER DEFAULT 1,
                tags TEXT DEFAULT '[]',
                fingerprint TEXT DEFAULT '{}',
                browser_engine TEXT DEFAULT 'chrome',
                os_type TEXT DEFAULT 'windows',
                notes TEXT DEFAULT '',
                created_at REAL DEFAULT (strftime('%s','now')),
                updated_at REAL DEFAULT (strftime('%s','now')),
                last_used REAL,
                is_running INTEGER DEFAULT 0,
                cdp_endpoint TEXT,
                FOREIGN KEY (group_id) REFERENCES profile_groups(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS profile_groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                description TEXT DEFAULT '',
                color TEXT DEFAULT '#4263eb',
                created_at REAL DEFAULT (strftime('%s','now')),
                settings TEXT DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS proxies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                protocol TEXT NOT NULL,
                host TEXT NOT NULL,
                port INTEGER NOT NULL,
                username TEXT,
                password TEXT,
                country TEXT,
                country_code TEXT,
                city TEXT,
                isp TEXT,
                asn TEXT,
                latency_ms INTEGER,
                last_checked REAL,
                is_healthy INTEGER DEFAULT 1,
                tags TEXT DEFAULT '[]',
                created_at REAL DEFAULT (strftime('%s','now'))
            );

            CREATE TABLE IF NOT EXISTS fingerprints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                os_type TEXT,
                config TEXT NOT NULL,
                is_template INTEGER DEFAULT 0,
                template_category TEXT,
                created_at REAL DEFAULT (strftime('%s','now'))
            );

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            );

            CREATE TABLE IF NOT EXISTS api_keys (
                key TEXT PRIMARY KEY,
                created_at REAL DEFAULT (strftime('%s','now')),
                last_used REAL,
                request_count INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS cookies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_id INTEGER NOT NULL,
                domain TEXT NOT NULL,
                name TEXT NOT NULL,
                value TEXT,
                path TEXT DEFAULT '/',
                secure INTEGER DEFAULT 0,
                http_only INTEGER DEFAULT 0,
                same_site TEXT DEFAULT 'Lax',
                expiry REAL,
                created_at REAL DEFAULT (strftime('%s','now')),
                FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS credentials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_id INTEGER,
                url TEXT,
                username TEXT,
                encrypted_password TEXT,
                notes TEXT,
                created_at REAL DEFAULT (strftime('%s','now')),
                FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS extensions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_id INTEGER,
                name TEXT NOT NULL,
                path TEXT NOT NULL,
                enabled INTEGER DEFAULT 1,
                created_at REAL DEFAULT (strftime('%s','now')),
                FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS operation_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_name TEXT,
                action TEXT NOT NULL,
                details TEXT DEFAULT '{}',
                timestamp REAL DEFAULT (strftime('%s','now'))
            );

            CREATE INDEX IF NOT EXISTS idx_profiles_group ON profiles(group_id);
            CREATE INDEX IF NOT EXISTS idx_profiles_name ON profiles(name);
            CREATE INDEX IF NOT EXISTS idx_proxies_healthy ON proxies(is_healthy);
            CREATE INDEX IF NOT EXISTS idx_proxies_country ON proxies(country_code);
            CREATE INDEX IF NOT EXISTS idx_cookies_profile ON cookies(profile_id);
            CREATE INDEX IF NOT EXISTS idx_credentials_profile ON credentials(profile_id);
            CREATE INDEX IF NOT EXISTS idx_extensions_profile ON extensions(profile_id);
            CREATE INDEX IF NOT EXISTS idx_logs_profile ON operation_logs(profile_name);
        """)
        conn.commit()

    def _migrate_json_profiles(self):
        """Migrate existing JSON profiles to SQLite if present."""
        json_path = resource_path("src", "browser", "config", "profiles.json")
        if not os.path.exists(json_path):
            return

        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if not data:
                return

            conn = self._get_conn()
            migrated = 0
            for name, profile_data in data.items():
                try:
                    conn.execute(
                        """INSERT OR IGNORE INTO profiles
                           (name, proxy, timezone, webrtc, canvas_fp, webgl_fp, audio_fp,
                            client_rects_fp, dns_protection, custom_dns, dns_leak_protection,
                            fingerprint)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            name,
                            profile_data.get("proxy"),
                            profile_data.get("timezone"),
                            profile_data.get("webrtc", "filter"),
                            int(profile_data.get("canvas_fp", True)),
                            int(profile_data.get("webgl_fp", True)),
                            int(profile_data.get("audio_fp", True)),
                            int(profile_data.get("client_rects_fp", True)),
                            profile_data.get("dns_protection", "cloudflare"),
                            profile_data.get("custom_dns", ""),
                            int(profile_data.get("dns_leak_protection", True)),
                            json.dumps(profile_data.get("fingerprint", {})),
                        )
                    )
                    migrated += 1
                except Exception as e:
                    logger.warning(f"Failed to migrate profile {name}: {e}")

            conn.commit()
            # Rename old file as backup
            backup_path = json_path + ".bak"
            os.rename(json_path, backup_path)
            logger.info(f"Migrated {migrated} profiles from JSON to SQLite (backup: {backup_path})")
        except Exception as e:
            logger.error(f"JSON migration failed: {e}")

    def _migrate_add_columns(self):
        """Add new columns to existing tables for schema evolution."""
        conn = self._get_conn()
        # Check and add columns to profiles table
        try:
            cols = [row[1] for row in conn.execute("PRAGMA table_info(profiles)").fetchall()]
            new_cols = {
                "browser_engine": "TEXT DEFAULT 'chrome'",
                "os_type": "TEXT DEFAULT 'windows'",
                "notes": "TEXT DEFAULT ''",
                "headless": "INTEGER DEFAULT 0",
                "user_agent": "TEXT DEFAULT ''",
                "extensions_enabled": "INTEGER DEFAULT 0",
                "humanize": "INTEGER DEFAULT 0",
            }
            for col_name, col_def in new_cols.items():
                if col_name not in cols:
                    conn.execute(f"ALTER TABLE profiles ADD COLUMN {col_name} {col_def}")
                    logger.info(f"Added column {col_name} to profiles table")
            conn.commit()
        except Exception as e:
            logger.debug(f"Column migration (may be already done): {e}")

    # ==================== Profile CRUD ====================

    def create_profile(self, name: str, **kwargs) -> Dict[str, Any]:
        conn = self._get_conn()
        fingerprint = kwargs.get("fingerprint", {})
        if isinstance(fingerprint, dict):
            fingerprint = json.dumps(fingerprint)
        tags = kwargs.get("tags", [])
        if isinstance(tags, list):
            tags = json.dumps(tags)

        conn.execute(
            """INSERT INTO profiles
               (name, proxy, timezone, webrtc, canvas_fp, webgl_fp, audio_fp,
                client_rects_fp, dns_protection, custom_dns, dns_leak_protection,
                tags, fingerprint, group_id, browser_engine, os_type, notes,
                headless, user_agent, extensions_enabled, humanize)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                name,
                kwargs.get("proxy"),
                kwargs.get("timezone"),
                kwargs.get("webrtc", "filter"),
                int(kwargs.get("canvas_fp", True)),
                int(kwargs.get("webgl_fp", True)),
                int(kwargs.get("audio_fp", True)),
                int(kwargs.get("client_rects_fp", True)),
                kwargs.get("dns_protection", "cloudflare"),
                kwargs.get("custom_dns", ""),
                int(kwargs.get("dns_leak_protection", True)),
                tags,
                fingerprint,
                kwargs.get("group_id"),
                kwargs.get("browser_engine", "chrome"),
                kwargs.get("os_type", "windows"),
                kwargs.get("notes", ""),
                int(kwargs.get("headless", False)),
                kwargs.get("user_agent", ""),
                int(kwargs.get("extensions_enabled", False)),
                int(kwargs.get("humanize", False)),
            )
        )
        conn.commit()
        return self.get_profile(name)

    def get_profile(self, name: str) -> Optional[Dict[str, Any]]:
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM profiles WHERE name = ?", (name,)).fetchone()
        return self._row_to_profile(row) if row else None

    def update_profile(self, name: str, **kwargs) -> Optional[Dict[str, Any]]:
        conn = self._get_conn()
        allowed_fields = {
            "proxy", "timezone", "webrtc", "canvas_fp", "webgl_fp", "audio_fp",
            "client_rects_fp", "dns_protection", "custom_dns", "dns_leak_protection",
            "tags", "fingerprint", "group_id", "is_running", "cdp_endpoint", "last_used",
            "browser_engine", "os_type", "notes", "headless", "user_agent", "extensions_enabled",
            "humanize"
        }
        updates = []
        values = []
        for key, val in kwargs.items():
            if key in allowed_fields:
                if key in ("canvas_fp", "webgl_fp", "audio_fp", "client_rects_fp",
                            "dns_leak_protection", "is_running", "headless", "extensions_enabled",
                            "humanize"):
                    val = int(val)
                elif key in ("tags", "fingerprint") and isinstance(val, (dict, list)):
                    val = json.dumps(val)
                updates.append(f"{key} = ?")
                values.append(val)

        if not updates:
            return self.get_profile(name)

        updates.append("updated_at = ?")
        values.append(time.time())
        values.append(name)

        conn.execute(f"UPDATE profiles SET {', '.join(updates)} WHERE name = ?", values)
        conn.commit()
        return self.get_profile(name)

    def delete_profile(self, name: str) -> bool:
        conn = self._get_conn()
        cursor = conn.execute("DELETE FROM profiles WHERE name = ?", (name,))
        conn.commit()
        return cursor.rowcount > 0

    def list_profiles(self, group_id: int = None) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        if group_id is not None:
            rows = conn.execute("SELECT * FROM profiles WHERE group_id = ? ORDER BY name", (group_id,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM profiles ORDER BY name").fetchall()
        return [self._row_to_profile(r) for r in rows]

    def _row_to_profile(self, row: sqlite3.Row) -> Dict[str, Any]:
        return {
            "id": row["id"],
            "name": row["name"],
            "group_id": row["group_id"],
            "proxy": row["proxy"],
            "timezone": row["timezone"],
            "webrtc": row["webrtc"],
            "canvas_fp": bool(row["canvas_fp"]),
            "webgl_fp": bool(row["webgl_fp"]),
            "audio_fp": bool(row["audio_fp"]),
            "client_rects_fp": bool(row["client_rects_fp"]),
            "dns_protection": row["dns_protection"],
            "custom_dns": row["custom_dns"],
            "dns_leak_protection": bool(row["dns_leak_protection"]),
            "tags": json.loads(row["tags"]) if row["tags"] else [],
            "fingerprint": json.loads(row["fingerprint"]) if row["fingerprint"] else {},
            "browser_engine": row["browser_engine"] if "browser_engine" in row.keys() else "chrome",
            "os_type": row["os_type"] if "os_type" in row.keys() else "windows",
            "notes": row["notes"] if "notes" in row.keys() else "",
            "headless": bool(row["headless"]) if "headless" in row.keys() else False,
            "user_agent": row["user_agent"] if "user_agent" in row.keys() else "",
            "extensions_enabled": bool(row["extensions_enabled"]) if "extensions_enabled" in row.keys() else False,
            "humanize": bool(row["humanize"]) if "humanize" in row.keys() else False,
            "is_running": bool(row["is_running"]),
            "cdp_endpoint": row["cdp_endpoint"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "last_used": row["last_used"],
        }

    # ==================== Profile Group CRUD ====================

    def create_group(self, name: str, description: str = "", color: str = "#4263eb",
                     settings: dict = None) -> Dict[str, Any]:
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO profile_groups (name, description, color, settings) VALUES (?, ?, ?, ?)",
            (name, description, color, json.dumps(settings or {}))
        )
        conn.commit()
        return self.get_group(name)

    def get_group(self, name: str) -> Optional[Dict[str, Any]]:
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM profile_groups WHERE name = ?", (name,)).fetchone()
        return self._row_to_group(row) if row else None

    def list_groups(self) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        rows = conn.execute("SELECT * FROM profile_groups ORDER BY name").fetchall()
        return [self._row_to_group(r) for r in rows]

    def delete_group(self, name: str) -> bool:
        conn = self._get_conn()
        cursor = conn.execute("DELETE FROM profile_groups WHERE name = ?", (name,))
        conn.commit()
        return cursor.rowcount > 0

    def _row_to_group(self, row: sqlite3.Row) -> Dict[str, Any]:
        return {
            "id": row["id"],
            "name": row["name"],
            "description": row["description"],
            "color": row["color"],
            "settings": json.loads(row["settings"]) if row["settings"] else {},
            "created_at": row["created_at"],
        }

    # ==================== Proxy CRUD ====================

    def add_proxy(self, name: str, protocol: str, host: str, port: int,
                  username: str = None, password: str = None,
                  tags: list = None) -> Dict[str, Any]:
        conn = self._get_conn()
        conn.execute(
            """INSERT INTO proxies (name, protocol, host, port, username, password, tags)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (name, protocol, host, port, username, password, json.dumps(tags or []))
        )
        conn.commit()
        return self.get_proxy(name)

    def get_proxy(self, name: str) -> Optional[Dict[str, Any]]:
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM proxies WHERE name = ?", (name,)).fetchone()
        return self._row_to_proxy(row) if row else None

    def list_proxies(self, healthy_only: bool = False) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        if healthy_only:
            rows = conn.execute("SELECT * FROM proxies WHERE is_healthy = 1 ORDER BY name").fetchall()
        else:
            rows = conn.execute("SELECT * FROM proxies ORDER BY name").fetchall()
        return [self._row_to_proxy(r) for r in rows]

    def update_proxy(self, name: str, **kwargs) -> Optional[Dict[str, Any]]:
        conn = self._get_conn()
        allowed = {"protocol", "host", "port", "username", "password", "country",
                    "country_code", "city", "isp", "asn", "latency_ms", "last_checked",
                    "is_healthy", "tags"}
        updates = []
        values = []
        for key, val in kwargs.items():
            if key in allowed:
                if key in ("is_healthy",):
                    val = int(val)
                if key == "tags" and isinstance(val, list):
                    val = json.dumps(val)
                updates.append(f"{key} = ?")
                values.append(val)
        if not updates:
            return self.get_proxy(name)
        values.append(name)
        conn.execute(f"UPDATE proxies SET {', '.join(updates)} WHERE name = ?", values)
        conn.commit()
        return self.get_proxy(name)

    def delete_proxy(self, name: str) -> bool:
        conn = self._get_conn()
        cursor = conn.execute("DELETE FROM proxies WHERE name = ?", (name,))
        conn.commit()
        return cursor.rowcount > 0

    def _row_to_proxy(self, row: sqlite3.Row) -> Dict[str, Any]:
        return {
            "id": row["id"],
            "name": row["name"],
            "protocol": row["protocol"],
            "host": row["host"],
            "port": row["port"],
            "username": row["username"],
            "password": row["password"],
            "country": row["country"],
            "country_code": row["country_code"],
            "city": row["city"],
            "isp": row["isp"],
            "asn": row["asn"],
            "latency_ms": row["latency_ms"],
            "last_checked": row["last_checked"],
            "is_healthy": bool(row["is_healthy"]),
            "tags": json.loads(row["tags"]) if row["tags"] else [],
            "created_at": row["created_at"],
        }

    # ==================== Settings CRUD ====================

    def get_setting(self, key: str, default: Any = None) -> Any:
        conn = self._get_conn()
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        if row:
            try:
                return json.loads(row["value"])
            except (json.JSONDecodeError, TypeError):
                return row["value"]
        return default

    def set_setting(self, key: str, value: Any):
        conn = self._get_conn()
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (key, json.dumps(value))
        )
        conn.commit()

    # ==================== API Key Management ====================

    def create_api_key(self, key: str):
        conn = self._get_conn()
        conn.execute("INSERT OR IGNORE INTO api_keys (key) VALUES (?)", (key,))
        conn.commit()

    def validate_api_key(self, key: str) -> bool:
        conn = self._get_conn()
        row = conn.execute("SELECT key FROM api_keys WHERE key = ?", (key,)).fetchone()
        if row:
            conn.execute(
                "UPDATE api_keys SET last_used = ?, request_count = request_count + 1 WHERE key = ?",
                (time.time(), key)
            )
            conn.commit()
            return True
        return False

    def list_api_keys(self) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        rows = conn.execute("SELECT * FROM api_keys ORDER BY created_at DESC").fetchall()
        return [{"key": r["key"], "created_at": r["created_at"],
                 "last_used": r["last_used"], "request_count": r["request_count"]}
                for r in rows]

    def delete_api_key(self, key: str) -> bool:
        conn = self._get_conn()
        cursor = conn.execute("DELETE FROM api_keys WHERE key = ?", (key,))
        conn.commit()
        return cursor.rowcount > 0

    # ==================== Fingerprint Templates ====================

    def save_fingerprint_template(self, name: str, os_type: str, config: dict,
                                  category: str = None) -> Dict[str, Any]:
        conn = self._get_conn()
        conn.execute(
            """INSERT OR REPLACE INTO fingerprints (name, os_type, config, is_template, template_category)
               VALUES (?, ?, ?, 1, ?)""",
            (name, os_type, json.dumps(config), category)
        )
        conn.commit()
        return {"name": name, "os_type": os_type, "config": config, "category": category}

    def list_fingerprint_templates(self, category: str = None) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        if category:
            rows = conn.execute(
                "SELECT * FROM fingerprints WHERE is_template = 1 AND template_category = ? ORDER BY name",
                (category,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM fingerprints WHERE is_template = 1 ORDER BY name"
            ).fetchall()
        return [{"name": r["name"], "os_type": r["os_type"],
                 "config": json.loads(r["config"]), "category": r["template_category"]}
                for r in rows]

    def close(self):
        if hasattr(self._local, "conn"):
            self._local.conn.close()
            del self._local.conn

    # ==================== Cookie CRUD ====================

    def add_cookies(self, profile_name: str, cookies: list) -> int:
        """Add cookies for a profile. Returns count inserted."""
        conn = self._get_conn()
        profile = self.get_profile(profile_name)
        if not profile:
            return 0
        pid = profile["id"]
        count = 0
        for c in cookies:
            conn.execute(
                """INSERT INTO cookies (profile_id, domain, name, value, path, secure, http_only, same_site, expiry)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (pid, c.get("domain", ""), c.get("name", ""), c.get("value", ""),
                 c.get("path", "/"), int(c.get("secure", False)), int(c.get("httpOnly", False)),
                 c.get("sameSite", "Lax"), c.get("expiry"))
            )
            count += 1
        conn.commit()
        return count

    def get_cookies(self, profile_name: str) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        profile = self.get_profile(profile_name)
        if not profile:
            return []
        rows = conn.execute("SELECT * FROM cookies WHERE profile_id = ?", (profile["id"],)).fetchall()
        return [{"id": r["id"], "domain": r["domain"], "name": r["name"], "value": r["value"],
                 "path": r["path"], "secure": bool(r["secure"]), "httpOnly": bool(r["http_only"]),
                 "sameSite": r["same_site"], "expiry": r["expiry"]}
                for r in rows]

    def clear_cookies(self, profile_name: str) -> int:
        conn = self._get_conn()
        profile = self.get_profile(profile_name)
        if not profile:
            return 0
        cursor = conn.execute("DELETE FROM cookies WHERE profile_id = ?", (profile["id"],))
        conn.commit()
        return cursor.rowcount

    # ==================== Credential CRUD ====================

    def add_credential(self, profile_name: str, url: str, username: str,
                       encrypted_password: str, notes: str = "") -> Dict[str, Any]:
        conn = self._get_conn()
        profile = self.get_profile(profile_name)
        if not profile:
            raise ValueError(f"Profile '{profile_name}' not found")
        conn.execute(
            "INSERT INTO credentials (profile_id, url, username, encrypted_password, notes) VALUES (?, ?, ?, ?, ?)",
            (profile["id"], url, username, encrypted_password, notes)
        )
        conn.commit()
        return {"url": url, "username": username, "notes": notes}

    def list_credentials(self, profile_name: str) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        profile = self.get_profile(profile_name)
        if not profile:
            return []
        rows = conn.execute("SELECT * FROM credentials WHERE profile_id = ?", (profile["id"],)).fetchall()
        return [{"id": r["id"], "url": r["url"], "username": r["username"],
                 "notes": r["notes"], "created_at": r["created_at"]}
                for r in rows]

    def delete_credential(self, cred_id: int) -> bool:
        conn = self._get_conn()
        cursor = conn.execute("DELETE FROM credentials WHERE id = ?", (cred_id,))
        conn.commit()
        return cursor.rowcount > 0

    # ==================== Extension CRUD ====================

    def add_extension(self, profile_name: str, name: str, path: str) -> Dict[str, Any]:
        conn = self._get_conn()
        profile = self.get_profile(profile_name)
        if not profile:
            raise ValueError(f"Profile '{profile_name}' not found")
        conn.execute(
            "INSERT INTO extensions (profile_id, name, path, enabled) VALUES (?, ?, ?, 1)",
            (profile["id"], name, path)
        )
        conn.commit()
        return {"name": name, "path": path, "enabled": True}

    def list_extensions(self, profile_name: str) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        profile = self.get_profile(profile_name)
        if not profile:
            return []
        rows = conn.execute("SELECT * FROM extensions WHERE profile_id = ?", (profile["id"],)).fetchall()
        return [{"id": r["id"], "name": r["name"], "path": r["path"], "enabled": bool(r["enabled"])}
                for r in rows]

    def delete_extension(self, ext_id: int) -> bool:
        conn = self._get_conn()
        cursor = conn.execute("DELETE FROM extensions WHERE id = ?", (ext_id,))
        conn.commit()
        return cursor.rowcount > 0

    # ==================== Operation Logs ====================

    def log_operation(self, profile_name: str, action: str, details: dict = None):
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO operation_logs (profile_name, action, details) VALUES (?, ?, ?)",
            (profile_name, action, json.dumps(details or {}))
        )
        conn.commit()

    def list_operation_logs(self, profile_name: str = None, limit: int = 50) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        if profile_name:
            rows = conn.execute(
                "SELECT * FROM operation_logs WHERE profile_name = ? ORDER BY timestamp DESC LIMIT ?",
                (profile_name, limit)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM operation_logs ORDER BY timestamp DESC LIMIT ?", (limit,)
            ).fetchall()
        return [{"id": r["id"], "profile_name": r["profile_name"], "action": r["action"],
                 "details": json.loads(r["details"]) if r["details"] else {},
                 "timestamp": r["timestamp"]}
                for r in rows]

    # ==================== Profile Cloning ====================

    def clone_profile(self, source_name: str, new_name: str) -> Optional[Dict[str, Any]]:
        """Clone a profile's configuration to a new profile with a randomized fingerprint seed."""
        source = self.get_profile(source_name)
        if not source:
            return None
        # Remove identity fields, randomize fingerprint
        clone_data = {k: v for k, v in source.items()
                      if k not in ("id", "name", "created_at", "updated_at", "last_used",
                                   "is_running", "cdp_endpoint")}
        clone_data["name"] = new_name
        clone_data["is_running"] = False
        clone_data["cdp_endpoint"] = None
        # Randomize fingerprint seed for the clone
        fp = clone_data.get("fingerprint", {})
        if isinstance(fp, dict):
            import random as _rng
            fp["seed"] = _rng.randint(100000, 999999)
            clone_data["fingerprint"] = fp
        return self.create_profile(**clone_data)
