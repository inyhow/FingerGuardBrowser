import pytest
import responses
import os
from src.browser.browser_manager import BrowserManager

@pytest.fixture
def browser_manager(tmpdir):
    manager = BrowserManager()
    config_dir = str(tmpdir.mkdir("config"))
    manager.config_dir = config_dir
    manager.profile_manager.config_dir = config_dir
    manager.profile_manager.profiles_file = os.path.join(config_dir, "profiles.json")
    return manager

@responses.activate
def test_check_proxy_success_ipapi(browser_manager):
    """Test proxy validation with ipapi.co source."""
    responses.add(
        responses.GET,
        "https://ipapi.co/json/",
        json={
            "ip": "1.2.3.4",
            "country_name": "United States",
            "country_code": "US",
            "city": "New York",
            "org": "Test ISP",
            "timezone": "America/New_York",
            "latitude": 40.7128,
            "longitude": -74.0060,
            "asn": "AS12345",
        },
        status=200
    )

    result = browser_manager.check_proxy("http://mock-proxy:8080")
    assert result["status"] == "success"
    assert result["ip"] == "1.2.3.4"
    assert result["country"] == "United States"
    assert result["timezone"] == "America/New_York"
    assert result["latitude"] == 40.7128

@responses.activate
def test_check_proxy_success_ipwhois(browser_manager):
    """Test proxy validation fallback to ipwho.is source."""
    # First source fails
    responses.add(
        responses.GET,
        "https://ipapi.co/json/",
        json={"error": True},
        status=500
    )
    # Second source succeeds
    responses.add(
        responses.GET,
        "https://ipwho.is/",
        json={
            "success": True,
            "ip": "5.6.7.8",
            "country": "United Kingdom",
            "country_code": "GB",
            "city": "London",
            "connection": {"isp": "UK ISP", "asn": "AS67890"},
            "timezone": {"id": "Europe/London"},
            "latitude": 51.5074,
            "longitude": -0.1278,
        },
        status=200
    )

    result = browser_manager.check_proxy("http://mock-proxy:8080")
    assert result["status"] == "success"
    assert result["ip"] == "5.6.7.8"
    assert result["country"] == "United Kingdom"
    assert result["timezone"] == "Europe/London"

@responses.activate
def test_check_proxy_all_sources_fail(browser_manager):
    """Test proxy validation when all sources fail."""
    responses.add(
        responses.GET,
        "https://ipapi.co/json/",
        json={"error": True},
        status=500
    )
    responses.add(
        responses.GET,
        "https://ipwho.is/",
        json={"success": False, "message": "Invalid IP"},
        status=200
    )
    responses.add(
        responses.GET,
        "https://api.ipify.org?format=json",
        json={},
        status=500
    )

    result = browser_manager.check_proxy("http://invalid-proxy:8080")
    assert result["status"] == "error"

@responses.activate
def test_check_proxy_uses_https(browser_manager):
    """Proxy validation must use HTTPS, not HTTP (security requirement)."""
    responses.add(
        responses.GET,
        "https://ipapi.co/json/",
        json={"ip": "1.2.3.4", "country_name": "US", "country_code": "US",
              "city": "NYC", "org": "ISP", "timezone": "America/New_York",
              "latitude": 40.0, "longitude": -74.0, "asn": "AS1"},
        status=200
    )

    result = browser_manager.check_proxy("http://mock-proxy:8080")
    assert result["status"] == "success"

    # Verify no HTTP (plaintext) calls were made
    for call in responses.calls:
        assert call.request.url.startswith("https://"), \
            f"Proxy validation must use HTTPS, got: {call.request.url}"

def test_check_proxy_no_proxy(browser_manager):
    """Test proxy validation with empty proxy."""
    result = browser_manager.check_proxy("")
    assert result["status"] == "error"
    assert "No proxy" in result["message"]

@responses.activate
def test_check_proxy_caching(browser_manager):
    """Test that proxy validation results are cached."""
    responses.add(
        responses.GET,
        "https://ipapi.co/json/",
        json={"ip": "1.2.3.4", "country_name": "US", "country_code": "US",
              "city": "NYC", "org": "ISP", "timezone": "America/New_York",
              "latitude": 40.0, "longitude": -74.0, "asn": "AS1"},
        status=200
    )

    # First call — should hit the API
    result1 = browser_manager.check_proxy("http://mock-proxy:8080")
    assert result1["status"] == "success"

    # Second call — should use cache (responses mock will raise if called again)
    # Note: responses library doesn't enforce call count by default,
    # but if it makes another HTTP call it will fail because responses
    # is exhausted. We need to add the response again to verify it's NOT called.
    # Instead, verify the cache dict is populated.
    assert "http://mock-proxy:8080" in browser_manager._proxy_cache

    # Reset responses to ensure no more calls are made
    responses.reset()

    # Third call — should use cache without any HTTP request
    result3 = browser_manager.check_proxy("http://mock-proxy:8080")
    assert result3["status"] == "success"
    assert result3["ip"] == "1.2.3.4"

def test_get_profile_data_dir(browser_manager):
    """Test that profile data directory is created and isolated."""
    data_dir = browser_manager._get_profile_data_dir("test_isolation_profile")
    assert os.path.exists(data_dir)
    assert "test_isolation_profile" in data_dir
    assert "chrome_data" in data_dir
