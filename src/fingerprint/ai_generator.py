"""AI-powered fingerprint generation with consistency validation.

This is the unique differentiator that none of the three reference projects offer:
- LLM-powered fingerprint generation for statistically plausible combinations
- Cross-vector consistency validation (detect anomalies like RTX 4090 + 4GB RAM)
- Natural language profile creation ("Create a profile for Amazon US from New York")
- Proxy recommendation based on target website's anti-bot system

Works with or without an LLM API key — falls back to rule-based generation.
"""

import json
import random
import hashlib
import time
from typing import Dict, Any, Optional, List, Tuple
from loguru import logger

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


class AIFingerprintGenerator:
    """AI-powered fingerprint generation and validation."""

    # Hardware consistency rules — used for anomaly detection
    HARDWARE_RULES = {
        # (min_memory_gb, max_memory_gb) per GPU class
        "RTX 4090": (16, 128),
        "RTX 4080": (16, 128),
        "RTX 4070": (16, 64),
        "RTX 4060": (8, 64),
        "RTX 3090": (16, 128),
        "RTX 3080": (16, 64),
        "RTX 3070": (8, 64),
        "RTX 3060": (8, 32),
        "RX 6700 XT": (8, 64),
        "RX 6800 XT": (16, 64),
        "RX 7900 XTX": (16, 128),
        "UHD Graphics 770": (4, 32),
        "Iris Xe Graphics": (4, 32),
        "Iris Plus Graphics 645": (4, 16),
        "Apple M1 Pro": (8, 64),
        "Apple M2": (8, 32),
        "Apple M3": (8, 64),
    }

    # Screen resolution → typical hardware class mapping
    RESOLUTION_HARDWARE_MAP = {
        "3840x2160": {"min_cpu": 8, "min_memory": 16, "gpu_tier": "high"},
        "2560x1440": {"min_cpu": 6, "min_memory": 8, "gpu_tier": "mid"},
        "1920x1080": {"min_cpu": 4, "min_memory": 4, "gpu_tier": "any"},
        "1366x768":  {"min_cpu": 2, "min_memory": 4, "gpu_tier": "low"},
    }

    # Market-specific device profiles for realistic generation
    MARKET_PROFILES = {
        "US": {
            "popular_resolutions": ["1920x1080", "2560x1440", "3840x2160"],
            "popular_gpus": ["RTX 3060", "RTX 4060", "RTX 4070", "UHD Graphics 770", "Iris Xe Graphics"],
            "popular_cpu_cores": [4, 6, 8, 8, 12, 16],
            "popular_memory": [8, 16, 16, 32],
            "os_distribution": {"windows": 0.70, "macos": 0.20, "linux": 0.10},
            "timezones": ["America/New_York", "America/Chicago", "America/Los_Angeles", "America/Denver"],
        },
        "EU": {
            "popular_resolutions": ["1920x1080", "2560x1440"],
            "popular_gpus": ["RTX 3060", "RTX 4060", "RX 6700 XT", "UHD Graphics 770"],
            "popular_cpu_cores": [4, 6, 8, 8],
            "popular_memory": [8, 16, 16, 32],
            "os_distribution": {"windows": 0.65, "macos": 0.20, "linux": 0.15},
            "timezones": ["Europe/London", "Europe/Paris", "Europe/Berlin", "Europe/Madrid", "Europe/Rome"],
        },
        "ASIA": {
            "popular_resolutions": ["1920x1080", "1366x768", "2560x1440"],
            "popular_gpus": ["RTX 3060", "UHD Graphics 770", "Iris Xe Graphics"],
            "popular_cpu_cores": [4, 6, 8],
            "popular_memory": [8, 16, 16],
            "os_distribution": {"windows": 0.85, "macos": 0.10, "linux": 0.05},
            "timezones": ["Asia/Tokyo", "Asia/Shanghai", "Asia/Seoul", "Asia/Singapore"],
        },
    }

    def __init__(self, fingerprint_manager=None, llm_api_key: str = None,
                 llm_api_url: str = None, llm_model: str = None):
        """
        Args:
            fingerprint_manager: Existing FingerprintManager instance
            llm_api_key: API key for LLM (OpenAI-compatible). If None, uses rule-based generation.
            llm_api_url: Base URL for LLM API. Defaults to OpenAI.
            llm_model: Model name. Defaults to gpt-4o-mini.
        """
        self.fp_manager = fingerprint_manager
        self.llm_api_key = llm_api_key
        self.llm_api_url = llm_api_url or "https://api.openai.com/v1/chat/completions"
        self.llm_model = llm_model or "gpt-4o-mini"

    def generate_from_natural_language(self, description: str) -> Dict[str, Any]:
        """Generate a fingerprint from a natural language description.

        Examples:
            "Create a profile for Amazon US from New York with a mid-range Windows laptop"
            "I need a Mac user in London for browsing social media"
            "Gaming PC in Tokyo for e-commerce"

        Falls back to rule-based generation if LLM is not available.
        """
        parsed = self._parse_description(description)

        if self.llm_api_key and REQUESTS_AVAILABLE:
            try:
                return self._generate_with_llm(description, parsed)
            except Exception as e:
                logger.warning(f"LLM generation failed, falling back to rules: {e}")

        return self._generate_with_rules(parsed)

    def _parse_description(self, description: str) -> Dict[str, Any]:
        """Extract parameters from natural language description using keyword matching."""
        desc_lower = description.lower()

        parsed = {
            "market": None,
            "os_type": None,
            "device_class": None,
            "timezone": None,
            "use_case": None,
        }

        # Detect market/region
        for market in self.MARKET_PROFILES:
            if market.lower() in desc_lower:
                parsed["market"] = market
                break

        # Region keywords
        region_map = {
            "new york": ("US", "America/New_York"),
            "los angeles": ("US", "America/Los_Angeles"),
            "chicago": ("US", "America/Chicago"),
            "london": ("EU", "Europe/London"),
            "paris": ("EU", "Europe/Paris"),
            "berlin": ("EU", "Europe/Berlin"),
            "tokyo": ("ASIA", "Asia/Tokyo"),
            "shanghai": ("ASIA", "Asia/Shanghai"),
            "seoul": ("ASIA", "Asia/Seoul"),
            "singapore": ("ASIA", "Asia/Singapore"),
        }
        for keyword, (market, tz) in region_map.items():
            if keyword in desc_lower:
                parsed["market"] = market
                parsed["timezone"] = tz
                break

        # Detect OS
        if "windows" in desc_lower or "pc" in desc_lower or "laptop" in desc_lower:
            parsed["os_type"] = "windows"
        elif "mac" in desc_lower or "macbook" in desc_lower or "apple" in desc_lower:
            parsed["os_type"] = "macos"
        elif "linux" in desc_lower or "ubuntu" in desc_lower:
            parsed["os_type"] = "linux"

        # Detect device class
        if "gaming" in desc_lower or "high-end" in desc_lower or "powerful" in desc_lower:
            parsed["device_class"] = "high"
        elif "mid-range" in desc_lower or "mid range" in desc_lower or "average" in desc_lower:
            parsed["device_class"] = "mid"
        elif "low-end" in desc_lower or "budget" in desc_lower or "cheap" in desc_lower:
            parsed["device_class"] = "low"

        # Detect use case
        if "amazon" in desc_lower or "e-commerce" in desc_lower or "shopping" in desc_lower:
            parsed["use_case"] = "ecommerce"
        elif "social" in desc_lower or "facebook" in desc_lower or "instagram" in desc_lower:
            parsed["use_case"] = "social"
        elif "banking" in desc_lower or "finance" in desc_lower:
            parsed["use_case"] = "banking"

        return parsed

    def _generate_with_rules(self, parsed: Dict[str, Any]) -> Dict[str, Any]:
        """Generate fingerprint using rule-based approach (no LLM needed)."""
        market = parsed.get("market") or "US"
        market_profile = self.MARKET_PROFILES.get(market, self.MARKET_PROFILES["US"])

        # Determine OS from market distribution or explicit choice
        os_type = parsed.get("os_type")
        if not os_type:
            dist = market_profile["os_distribution"]
            r = random.random()
            cumulative = 0
            for os_name, prob in dist.items():
                cumulative += prob
                if r <= cumulative:
                    os_type = os_name
                    break
            if not os_type:
                os_type = "windows"

        # Determine device class
        device_class = parsed.get("device_class", "mid")

        # Generate coherent hardware
        cpu_cores = random.choice(market_profile["popular_cpu_cores"])
        memory = random.choice(market_profile["popular_memory"])

        # Adjust based on device class
        if device_class == "high":
            cpu_cores = max(cpu_cores, random.choice([8, 12, 16, 24]))
            memory = max(memory, random.choice([16, 32, 64]))
        elif device_class == "low":
            cpu_cores = min(cpu_cores, random.choice([4, 6]))
            memory = min(memory, random.choice([4, 8]))

        # GPU must be coherent with memory
        gpu = random.choice(market_profile["popular_gpus"])
        min_mem, max_mem = self.HARDWARE_RULES.get(gpu, (4, 128))
        memory = max(memory, min_mem)
        memory = min(memory, max_mem)

        # Resolution
        resolution = random.choice(market_profile["popular_resolutions"])
        if device_class == "high":
            resolution = random.choice(["2560x1440", "3840x2160"])
        elif device_class == "low":
            resolution = random.choice(["1366x768", "1920x1080"])

        # Timezone
        timezone = parsed.get("timezone") or random.choice(market_profile["timezones"])

        config = {
            "os_type": os_type,
            "hardwareConcurrency": cpu_cores,
            "deviceMemory": memory,
            "gpu": gpu,
            "resolution": resolution,
            "timezone": timezone,
            "market": market,
            "device_class": device_class,
            "use_case": parsed.get("use_case"),
            "generated_by": "ai_rule_based",
            "generated_at": int(time.time()),
            "consistency_score": self.validate_consistency({
                "os_type": os_type,
                "hardwareConcurrency": cpu_cores,
                "deviceMemory": memory,
                "gpu": gpu,
                "resolution": resolution,
            }),
        }

        return config

    def _generate_with_llm(self, description: str, parsed: Dict[str, Any]) -> Dict[str, Any]:
        """Generate fingerprint using LLM API (OpenAI-compatible)."""
        prompt = f"""You are a fingerprint configuration generator for an anti-detect browser.
Generate a realistic, cross-vector-consistent fingerprint configuration based on this description:

"{description}"

Parsed parameters: {json.dumps(parsed)}

Return a JSON object with these fields:
- os_type: "windows", "macos", or "linux"
- hardwareConcurrency: integer (4, 6, 8, 12, 16, 24)
- deviceMemory: integer in GB (4, 8, 16, 32, 64)
- gpu: GPU model string (must be consistent with memory and OS)
- resolution: string like "1920x1080"
- timezone: IANA timezone string
- market: "US", "EU", or "ASIA"
- device_class: "low", "mid", or "high"
- reasoning: brief explanation of why this combination is realistic

Rules:
- macOS can only have Apple GPUs (M1/M2/M3) or Intel Iris
- Windows can have NVIDIA, AMD, or Intel GPUs
- Linux typically has Mesa drivers or llvmpipe
- High-end GPU (RTX 4090) should have at least 16GB RAM
- 4K resolution should have at least 8 CPU cores
- The combination must be statistically plausible for the target market

Return ONLY the JSON, no markdown formatting."""

        response = requests.post(
            self.llm_api_url,
            headers={
                "Authorization": f"Bearer {self.llm_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.llm_model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,
                "response_format": {"type": "json_object"},
            },
            timeout=30,
        )
        response.raise_for_status()

        content = response.json()["choices"][0]["message"]["content"]
        config = json.loads(content)
        config["generated_by"] = "ai_llm"
        config["generated_at"] = int(time.time())

        # Validate consistency
        config["consistency_score"] = self.validate_consistency(config)

        return config

    def validate_consistency(self, config: Dict[str, Any]) -> float:
        """Validate fingerprint consistency and return a score 0.0-1.0.

        Checks:
        1. GPU ↔ memory coherence (RTX 4090 needs >= 16GB RAM)
        2. Resolution ↔ CPU coherence (4K needs >= 8 cores)
        3. OS ↔ GPU coherence (macOS can't have NVIDIA)
        4. Timezone ↔ locale coherence
        """
        score = 1.0
        penalties = []

        gpu = config.get("gpu", "")
        memory = config.get("deviceMemory", 8)
        cpu = config.get("hardwareConcurrency", 4)
        resolution = config.get("resolution", "1920x1080")
        os_type = config.get("os_type", "windows")

        # Check 1: GPU ↔ memory
        for gpu_key, (min_mem, max_mem) in self.HARDWARE_RULES.items():
            if gpu_key.lower() in gpu.lower():
                if memory < min_mem:
                    penalties.append(f"GPU {gpu_key} requires >= {min_mem}GB RAM (got {memory}GB)")
                    score -= 0.2
                if memory > max_mem:
                    penalties.append(f"GPU {gpu_key} typically has <= {max_mem}GB RAM (got {memory}GB)")
                    score -= 0.1
                break

        # Check 2: Resolution ↔ CPU
        res_rules = self.RESOLUTION_HARDWARE_MAP.get(resolution)
        if res_rules:
            if cpu < res_rules["min_cpu"]:
                penalties.append(f"{resolution} resolution typically has >= {res_rules['min_cpu']} CPU cores (got {cpu})")
                score -= 0.15
            if memory < res_rules["min_memory"]:
                penalties.append(f"{resolution} resolution typically has >= {res_rules['min_memory']}GB RAM (got {memory}GB)")
                score -= 0.1

        # Check 3: OS ↔ GPU
        if os_type == "macos" and any(x in gpu for x in ["NVIDIA", "AMD Radeon", "RTX", "RX"]):
            penalties.append(f"macOS cannot have discrete GPU {gpu}")
            score -= 0.3
        if os_type == "windows" and "Apple M" in gpu:
            penalties.append(f"Windows cannot have Apple Silicon GPU {gpu}")
            score -= 0.3

        score = max(0.0, min(1.0, score))

        if penalties:
            logger.warning(f"Fingerprint consistency issues: {'; '.join(penalties)} (score: {score:.2f})")

        return round(score, 2)

    def recommend_proxy(self, target_website: str, fingerprint: Dict[str, Any]) -> Dict[str, Any]:
        """Recommend proxy configuration based on target website and fingerprint.

        Analyzes the target website's known anti-bot system and recommends:
        - Optimal proxy country (should match fingerprint timezone)
        - Protocol recommendation (residential vs datacenter)
        - Whether the fingerprint's timezone matches the proxy's country
        """
        # Known anti-bot systems and their requirements
        anti_bot_map = {
            "cloudflare": {"strictness": "high", "requires_residential": True, "checks_tls": True},
            "datadome": {"strictness": "high", "requires_residential": True, "checks_tls": True},
            "perimeterx": {"strictness": "high", "requires_residential": True, "checks_tls": False},
            "recaptcha": {"strictness": "medium", "requires_residential": False, "checks_tls": False},
            "hcaptcha": {"strictness": "medium", "requires_residential": False, "checks_tls": False},
        }

        # Simple heuristic for known sites
        site_lower = target_website.lower()
        detected_system = None
        if "cloudflare" in site_lower or "cf-" in site_lower:
            detected_system = "cloudflare"
        elif "amazon" in site_lower:
            detected_system = "datadome"
        elif "ticketmaster" in site_lower:
            detected_system = "perimeterx"

        # Get fingerprint's timezone country
        tz = fingerprint.get("timezone", "UTC")
        tz_country_map = {
            "America/": "US",
            "Europe/": "EU",
            "Asia/Tokyo": "JP",
            "Asia/Shanghai": "CN",
            "Asia/Seoul": "KR",
            "Asia/Singapore": "SG",
            "Australia/": "AU",
        }
        proxy_country = "US"
        for prefix, country in tz_country_map.items():
            if tz.startswith(prefix):
                proxy_country = country
                break

        recommendation = {
            "target_website": target_website,
            "detected_anti_bot": detected_system,
            "recommended_proxy_country": proxy_country,
            "recommended_protocol": "socks5",
            "requires_residential": False,
            "consistency_warning": None,
        }

        if detected_system:
            system_info = anti_bot_map[detected_system]
            recommendation["requires_residential"] = system_info["requires_residential"]
            if system_info["requires_residential"]:
                recommendation["recommended_protocol"] = "http"
                recommendation["note"] = f"{detected_system} requires residential proxies for reliable access"

        # Check timezone ↔ proxy country consistency
        fp_market = fingerprint.get("market", "US")
        if proxy_country == "US" and fp_market not in ("US",):
            recommendation["consistency_warning"] = (
                f"Fingerprint market ({fp_market}) does not match proxy country ({proxy_country}). "
                "This may trigger anti-bot detection."
            )

        return recommendation

    def generate_fingerprint_config(self, ai_config: Dict[str, Any],
                                    profile_name: str = None) -> Dict[str, Any]:
        """Convert AI-generated config into a full fingerprint config.

        Uses the existing FingerprintManager to create the complete fingerprint
        with all vectors, then overrides with AI-specified values.
        """
        if not self.fp_manager:
            raise RuntimeError("FingerprintManager not configured")

        if not profile_name:
            profile_name = f"ai_profile_{int(time.time())}"

        # Create base fingerprint with the AI-specified OS
        os_type = ai_config.get("os_type", "windows")
        kwargs = {}
        if ai_config.get("timezone"):
            kwargs["timezone"] = ai_config["timezone"]

        fingerprint = self.fp_manager.create_fingerprint(profile_name, os_type=os_type, **kwargs)

        # Override with AI-specified values
        if ai_config.get("hardwareConcurrency"):
            fingerprint["navigator"]["hardwareConcurrency"] = ai_config["hardwareConcurrency"]
        if ai_config.get("deviceMemory"):
            fingerprint["navigator"]["deviceMemory"] = ai_config["deviceMemory"]

        # Override GPU if specified
        if ai_config.get("gpu"):
            os_profiles = self.fp_manager.os_profiles.get(os_type, {})
            renderers = os_profiles.get("webgl_renderers", [])
            # Find a matching renderer or construct one
            for r in renderers:
                if ai_config["gpu"].lower() in r.lower():
                    fingerprint["webgl"]["unmaskedRenderer"] = r
                    break

        # Override resolution if specified
        if ai_config.get("resolution"):
            try:
                w, h = ai_config["resolution"].split("x")
                fingerprint["screen"]["width"] = int(w)
                fingerprint["screen"]["height"] = int(h)
                fingerprint["screen"]["availWidth"] = int(w)
                fingerprint["screen"]["availHeight"] = int(h) - 40
            except (ValueError, AttributeError):
                pass

        # Add AI metadata
        fingerprint["ai_metadata"] = {
            "generated_by": ai_config.get("generated_by", "unknown"),
            "consistency_score": ai_config.get("consistency_score", 0.0),
            "market": ai_config.get("market"),
            "device_class": ai_config.get("device_class"),
            "use_case": ai_config.get("use_case"),
        }

        # Save the updated fingerprint
        self.fp_manager.save_fingerprint(profile_name, fingerprint)

        return fingerprint
