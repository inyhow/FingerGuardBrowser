"""Tests for the AI-powered fingerprint generator."""

import pytest
from src.fingerprint.ai_generator import AIFingerprintGenerator
from src.fingerprint.fingerprint_manager import FingerprintManager


@pytest.fixture
def ai_gen():
    fm = FingerprintManager()
    return AIFingerprintGenerator(fingerprint_manager=fm)


class TestAIFingerprintGenerator:
    def test_parse_description_us_windows(self, ai_gen):
        parsed = ai_gen._parse_description("Create a profile for Amazon US from New York with a Windows laptop")
        assert parsed["market"] == "US"
        assert parsed["os_type"] == "windows"
        assert parsed["timezone"] == "America/New_York"
        assert parsed["use_case"] == "ecommerce"

    def test_parse_description_mac_london(self, ai_gen):
        parsed = ai_gen._parse_description("I need a Mac user in London for browsing social media")
        assert parsed["os_type"] == "macos"
        assert parsed["market"] == "EU"
        assert parsed["timezone"] == "Europe/London"

    def test_parse_description_tokyo_gaming(self, ai_gen):
        parsed = ai_gen._parse_description("Gaming PC in Tokyo for e-commerce")
        assert parsed["market"] == "ASIA"
        assert parsed["timezone"] == "Asia/Tokyo"
        assert parsed["device_class"] == "high"
        assert parsed["use_case"] == "ecommerce"

    def test_generate_with_rules_us(self, ai_gen):
        parsed = {"market": "US", "os_type": "windows", "timezone": "America/New_York", "device_class": "mid"}
        config = ai_gen._generate_with_rules(parsed)
        assert config["os_type"] == "windows"
        assert config["timezone"] == "America/New_York"
        assert config["market"] == "US"
        assert "hardwareConcurrency" in config
        assert "deviceMemory" in config
        assert "consistency_score" in config

    def test_generate_with_rules_macos(self, ai_gen):
        parsed = {"market": "EU", "os_type": "macos", "timezone": "Europe/London"}
        config = ai_gen._generate_with_rules(parsed)
        assert config["os_type"] == "macos"
        # macOS should not have NVIDIA GPU
        assert "NVIDIA" not in config.get("gpu", "")

    def test_generate_from_natural_language(self, ai_gen):
        config = ai_gen.generate_from_natural_language(
            "Create a profile for Amazon US from New York with a mid-range Windows laptop"
        )
        assert config["os_type"] == "windows"
        assert config["market"] == "US"
        assert config["generated_by"] in ("ai_rule_based", "ai_llm")

    def test_validate_consistency_good(self, ai_gen):
        config = {
            "os_type": "windows",
            "hardwareConcurrency": 8,
            "deviceMemory": 16,
            "gpu": "RTX 3060",
            "resolution": "1920x1080",
        }
        score = ai_gen.validate_consistency(config)
        assert score >= 0.8  # Should be high for a coherent combination

    def test_validate_consistency_bad_gpu_memory(self, ai_gen):
        config = {
            "os_type": "windows",
            "hardwareConcurrency": 4,
            "deviceMemory": 4,
            "gpu": "RTX 4090",
            "resolution": "1366x768",
        }
        score = ai_gen.validate_consistency(config)
        # RTX 4090 with 4GB RAM is unrealistic — penalized from 1.0 to 0.8
        assert score <= 0.8

    def test_validate_consistency_macos_nvidia(self, ai_gen):
        config = {
            "os_type": "macos",
            "hardwareConcurrency": 8,
            "deviceMemory": 16,
            "gpu": "RTX 3060",
            "resolution": "1920x1080",
        }
        score = ai_gen.validate_consistency(config)
        # macOS with NVIDIA GPU is invalid
        assert score < 0.8

    def test_validate_consistency_4k_low_cpu(self, ai_gen):
        config = {
            "os_type": "windows",
            "hardwareConcurrency": 2,
            "deviceMemory": 4,
            "gpu": "RTX 3060",
            "resolution": "3840x2160",
        }
        score = ai_gen.validate_consistency(config)
        # 4K with 2 CPU cores is unrealistic
        assert score < 0.8

    def test_recommend_proxy(self, ai_gen):
        fingerprint = {"timezone": "America/New_York", "market": "US"}
        rec = ai_gen.recommend_proxy("https://www.amazon.com", fingerprint)
        assert rec["target_website"] == "https://www.amazon.com"
        assert rec["detected_anti_bot"] is not None
        assert "recommended_proxy_country" in rec

    def test_recommend_proxy_consistency_warning(self, ai_gen):
        fingerprint = {"timezone": "Asia/Tokyo", "market": "ASIA"}
        rec = ai_gen.recommend_proxy("https://example.com", fingerprint)
        # ASIA market with US proxy country should warn
        assert rec["recommended_proxy_country"] in ("US", "JP")

    def test_market_profiles_completeness(self, ai_gen):
        for market, profile in ai_gen.MARKET_PROFILES.items():
            assert "popular_resolutions" in profile
            assert "popular_gpus" in profile
            assert "popular_cpu_cores" in profile
            assert "popular_memory" in profile
            assert "os_distribution" in profile
            assert "timezones" in profile
            assert len(profile["timezones"]) > 0
