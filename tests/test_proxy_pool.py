"""Tests for the proxy pool management."""

import os
import pytest
from src.storage.database import Database
from src.proxy.proxy_pool import ProxyPool


@pytest.fixture
def pool(tmp_path):
    Database._instance = None
    db = Database(db_path=str(tmp_path / "test.db"))
    return ProxyPool(database=db)


class TestProxyPool:
    def test_add_proxy(self, pool):
        proxy = pool.add_proxy("test1", "socks5", "127.0.0.1", 1080)
        assert proxy["name"] == "test1"
        assert proxy["protocol"] == "socks5"

    def test_add_unsupported_protocol(self, pool):
        with pytest.raises(ValueError, match="Unsupported protocol"):
            pool.add_proxy("bad", "ftp", "1.1.1.1", 443)

    def test_get_proxy_url_http(self, pool):
        pool.add_proxy("http1", "http", "1.1.1.1", 8080)
        url = pool.get_proxy_url("http1")
        assert url == "http://1.1.1.1:8080"

    def test_get_proxy_url_socks5(self, pool):
        pool.add_proxy("socks1", "socks5", "2.2.2.2", 1080)
        url = pool.get_proxy_url("socks1")
        assert url == "socks5://2.2.2.2:1080"

    def test_get_proxy_url_socks4(self, pool):
        pool.add_proxy("socks4", "socks4", "3.3.3.3", 1080)
        url = pool.get_proxy_url("socks4")
        assert url == "socks4://3.3.3.3:1080"

    def test_remove_proxy(self, pool):
        pool.add_proxy("toremove", "http", "1.1.1.1", 8080)
        assert pool.remove_proxy("toremove") is True
        assert pool.get_proxy_by_name("toremove") is None

    def test_list_proxies(self, pool):
        pool.add_proxy("p1", "http", "1.1.1.1", 8080)
        pool.add_proxy("p2", "socks5", "2.2.2.2", 1080)
        proxies = pool.list_proxies()
        assert len(proxies) == 2

    def test_parse_proxy_string_full(self, pool):
        result = pool.parse_proxy_string("socks5://user:pass@host:1080")
        assert result["protocol"] == "socks5"
        assert result["host"] == "host"
        assert result["port"] == 1080
        assert result["username"] == "user"
        assert result["password"] == "pass"

    def test_parse_proxy_string_no_protocol(self, pool):
        result = pool.parse_proxy_string("host:8080")
        assert result["protocol"] == "socks5"
        assert result["host"] == "host"
        assert result["port"] == 8080

    def test_parse_proxy_string_http(self, pool):
        result = pool.parse_proxy_string("http://proxy:3128")
        assert result["protocol"] == "http"
        assert result["host"] == "proxy"
        assert result["port"] == 3128

    def test_get_healthy_proxy_none(self, pool):
        assert pool.get_healthy_proxy() is None

    def test_get_healthy_proxy_with_data(self, pool):
        pool.add_proxy("p1", "http", "1.1.1.1", 8080)
        # By default new proxies are healthy
        proxy = pool.get_healthy_proxy()
        assert proxy is not None
        assert proxy["name"] == "p1"

    def test_rotate_proxy(self, pool):
        pool.add_proxy("p1", "http", "1.1.1.1", 8080)
        pool.add_proxy("p2", "http", "2.2.2.2", 8080)
        pool.add_proxy("p3", "http", "3.3.3.3", 8080)

        first = pool.rotate_proxy()
        second = pool.rotate_proxy()
        third = pool.rotate_proxy()
        fourth = pool.rotate_proxy()  # Should wrap around

        assert first["name"] != second["name"]
        assert second["name"] != third["name"]
        assert fourth["name"] == first["name"]  # Rotation wraps

    def test_export_proxies(self, pool, tmp_path):
        pool.add_proxy("p1", "http", "1.1.1.1", 8080, username="user", password="pass")
        export_path = str(tmp_path / "export.json")
        count = pool.export_proxies(export_path, include_credentials=False)
        assert count == 1

        import json
        with open(export_path) as f:
            data = json.load(f)
        assert "password" not in data[0]

    def test_import_proxies_json(self, pool, tmp_path):
        import json
        import_path = str(tmp_path / "import.json")
        with open(import_path, "w") as f:
            json.dump([
                {"name": "imported1", "protocol": "socks5", "host": "5.5.5.5", "port": 1080},
                {"name": "imported2", "protocol": "http", "host": "6.6.6.6", "port": 8080},
            ], f)
        count = pool.import_proxies(import_path)
        assert count == 2
        assert pool.get_proxy_by_name("imported1") is not None
