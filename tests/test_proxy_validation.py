import pytest
import responses
from src.browser.browser_manager import BrowserManager

@pytest.fixture
def browser_manager(tmpdir):
    manager = BrowserManager()
    config_dir = str(tmpdir.mkdir("config"))
    manager.config_dir = config_dir
    manager.profile_manager.config_dir = config_dir
    manager.profile_manager.profiles_file = os.path.join(config_dir, "profiles.json")
    return manager

import os

@responses.activate
def test_check_proxy_success(browser_manager):
    responses.add(
        responses.GET,
        "http://ip-api.com/json/",
        json={
            "status": "success",
            "query": "1.2.3.4",
            "country": "United States",
            "city": "New York",
            "isp": "Test ISP",
            "timezone": "America/New_York"
        },
        status=200
    )

    result = browser_manager.check_proxy("http://mock-proxy:8080")
    assert result["status"] == "success"
    assert result["ip"] == "1.2.3.4"
    assert result["country"] == "United States"

@responses.activate
def test_check_proxy_failure(browser_manager):
    responses.add(
        responses.GET,
        "http://ip-api.com/json/",
        json={"status": "fail", "message": "invalid query"},
        status=200
    )

    result = browser_manager.check_proxy("http://invalid-proxy:8080")
    assert result["status"] == "error"
