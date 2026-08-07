"""Tests for the SQLite storage layer."""

import os
import json
import tempfile
import pytest
from src.storage.database import Database


@pytest.fixture
def db(tmp_path):
    """Create a temporary database for each test."""
    db_path = str(tmp_path / "test.db")
    # Reset singleton
    Database._instance = None
    return Database(db_path=db_path)


class TestProfileCRUD:
    def test_create_profile(self, db):
        profile = db.create_profile("test1", proxy="socks5://127.0.0.1:1080")
        assert profile["name"] == "test1"
        assert profile["proxy"] == "socks5://127.0.0.1:1080"
        assert profile["is_running"] is False

    def test_get_profile(self, db):
        db.create_profile("test2", timezone="America/New_York")
        profile = db.get_profile("test2")
        assert profile is not None
        assert profile["timezone"] == "America/New_York"

    def test_get_nonexistent_profile(self, db):
        assert db.get_profile("nonexistent") is None

    def test_update_profile(self, db):
        db.create_profile("test3", proxy="http://proxy:8080")
        updated = db.update_profile("test3", proxy="socks5://new:1080", timezone="Asia/Tokyo")
        assert updated["proxy"] == "socks5://new:1080"
        assert updated["timezone"] == "Asia/Tokyo"

    def test_delete_profile(self, db):
        db.create_profile("test4")
        assert db.delete_profile("test4") is True
        assert db.get_profile("test4") is None

    def test_list_profiles(self, db):
        db.create_profile("a")
        db.create_profile("b")
        db.create_profile("c")
        profiles = db.list_profiles()
        assert len(profiles) == 3

    def test_profile_with_tags(self, db):
        db.create_profile("tagged", tags=["amazon", "us"])
        profile = db.get_profile("tagged")
        assert "amazon" in profile["tags"]
        assert "us" in profile["tags"]


class TestGroupCRUD:
    def test_create_group(self, db):
        group = db.create_group("Social", description="Social media accounts")
        assert group["name"] == "Social"
        assert group["description"] == "Social media accounts"

    def test_list_groups(self, db):
        db.create_group("Group1")
        db.create_group("Group2")
        groups = db.list_groups()
        assert len(groups) == 2

    def test_delete_group(self, db):
        db.create_group("ToDelete")
        assert db.delete_group("ToDelete") is True
        assert db.get_group("ToDelete") is None

    def test_assign_profile_to_group(self, db):
        group = db.create_group("Amazon")
        db.create_profile("amz1")
        db.update_profile("amz1", group_id=group["id"])
        profiles = db.list_profiles(group_id=group["id"])
        assert len(profiles) == 1
        assert profiles[0]["name"] == "amz1"


class TestProxyCRUD:
    def test_add_proxy(self, db):
        proxy = db.add_proxy("proxy1", "socks5", "127.0.0.1", 1080)
        assert proxy["name"] == "proxy1"
        assert proxy["protocol"] == "socks5"
        assert proxy["port"] == 1080

    def test_list_proxies(self, db):
        db.add_proxy("p1", "http", "1.1.1.1", 8080)
        db.add_proxy("p2", "socks5", "2.2.2.2", 1080)
        proxies = db.list_proxies()
        assert len(proxies) == 2

    def test_update_proxy_health(self, db):
        db.add_proxy("p1", "http", "1.1.1.1", 8080)
        db.update_proxy("p1", is_healthy=False, latency_ms=500)
        proxy = db.get_proxy("p1")
        assert proxy["is_healthy"] is False
        assert proxy["latency_ms"] == 500

    def test_list_healthy_proxies_only(self, db):
        db.add_proxy("healthy", "http", "1.1.1.1", 8080)
        db.add_proxy("unhealthy", "http", "2.2.2.2", 8080)
        db.update_proxy("unhealthy", is_healthy=False)
        healthy = db.list_proxies(healthy_only=True)
        assert len(healthy) == 1
        assert healthy[0]["name"] == "healthy"


class TestSettings:
    def test_set_and_get_setting(self, db):
        db.set_setting("theme", "dark")
        assert db.get_setting("theme") == "dark"

    def test_get_nonexistent_setting(self, db):
        assert db.get_setting("nonexistent", "default") == "default"

    def test_setting_with_dict(self, db):
        db.set_setting("config", {"key": "value", "nested": {"a": 1}})
        result = db.get_setting("config")
        assert result["key"] == "value"
        assert result["nested"]["a"] == 1


class TestAPIKeys:
    def test_create_and_validate_api_key(self, db):
        db.create_api_key("test_key_123")
        assert db.validate_api_key("test_key_123") is True
        assert db.validate_api_key("wrong_key") is False

    def test_api_key_request_count(self, db):
        db.create_api_key("counted_key")
        db.validate_api_key("counted_key")
        db.validate_api_key("counted_key")
        keys = db.list_api_keys()
        assert keys[0]["request_count"] == 2

    def test_delete_api_key(self, db):
        db.create_api_key("to_delete")
        assert db.delete_api_key("to_delete") is True
        assert db.validate_api_key("to_delete") is False


class TestFingerprintTemplates:
    def test_save_and_list_templates(self, db):
        db.save_fingerprint_template("WinHigh", "windows", {"cpu": 16}, "high_end")
        db.save_fingerprint_template("MacMid", "macos", {"cpu": 8}, "mid_range")
        templates = db.list_fingerprint_templates()
        assert len(templates) == 2

    def test_list_templates_by_category(self, db):
        db.save_fingerprint_template("WinHigh", "windows", {"cpu": 16}, "high_end")
        db.save_fingerprint_template("MacMid", "macos", {"cpu": 8}, "mid_range")
        high_end = db.list_fingerprint_templates(category="high_end")
        assert len(high_end) == 1
        assert high_end[0]["name"] == "WinHigh"
