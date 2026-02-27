import os
import pytest
from unittest.mock import MagicMock, patch
from src.browser.browser_manager import BrowserManager

@pytest.fixture
def browser_manager(tmpdir):
    with patch('src.browser.browser_manager.os.path.dirname') as mock_dir:
        config_dir = str(tmpdir.mkdir("config"))
        mock_dir.return_value = os.path.dirname(config_dir)
        manager = BrowserManager()
        # Ensure the config dir is actually what we want
        manager.config_dir = config_dir
        manager.profile_manager.config_dir = config_dir
        manager.profile_manager.profiles_file = os.path.join(config_dir, "profiles.json")
        return manager

def test_list_profiles_initially_empty(browser_manager):
    assert len(browser_manager.list_profiles()) == 0

def test_create_and_list_profile(browser_manager):
    browser_manager.create_profile("test1")
    profiles = browser_manager.list_profiles()
    assert "test1" in profiles

@patch('src.browser.browser_manager.uc.Chrome')
def test_launch_browser(mock_chrome, browser_manager):
    browser_manager.create_profile("test_launch")

    # Mocking uc.Chrome
    mock_driver = MagicMock()
    mock_chrome.return_value = mock_driver

    driver = browser_manager.launch_browser("test_launch")

    assert driver == mock_driver
    assert browser_manager.is_profile_running("test_launch")
    mock_chrome.assert_called_once()

@patch('src.browser.browser_manager.uc.Chrome')
def test_close_browser(mock_chrome, browser_manager):
    browser_manager.create_profile("test_close")
    mock_driver = MagicMock()
    mock_chrome.return_value = mock_driver

    browser_manager.launch_browser("test_close")
    browser_manager.close_browser("test_close")

    assert not browser_manager.is_profile_running("test_close")
    mock_driver.quit.assert_called_once()
