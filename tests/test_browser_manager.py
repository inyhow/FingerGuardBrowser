import os
import pytest
from unittest.mock import MagicMock, patch
from src.browser import browser_manager as bm_module
from src.browser.browser_manager import BrowserManager

@pytest.fixture
def browser_manager(tmpdir):
    # Redirect persistent app data into a temp directory so tests stay isolated
    # and do not depend on os.path.dirname patching internals.
    test_root = str(tmpdir)
    with patch('src.browser.browser_manager.data_path') as mock_data_path, \
         patch('src.utils.app_paths.user_data_dir', return_value=test_root):
        def _data_path(*parts):
            path = os.path.join(test_root, *parts)
            os.makedirs(os.path.dirname(path) if parts else path, exist_ok=True)
            return path
        mock_data_path.side_effect = _data_path
        manager = BrowserManager()
        config_dir = _data_path("profiles", "config")
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

def test_launch_browser(browser_manager):
    """Test browser launch with mocked undetected_chromedriver."""
    browser_manager.create_profile("test_launch")

    # Create a mock for undetected_chromedriver module
    mock_uc = MagicMock()
    mock_driver = MagicMock()
    mock_uc.Chrome.return_value = mock_driver
    mock_uc.ChromeOptions.return_value = MagicMock()

    # Patch the _ensure_uc function to return our mock
    with patch.object(bm_module, 'uc', mock_uc):
        driver = browser_manager.launch_browser("test_launch")

    assert driver == mock_driver
    assert browser_manager.is_profile_running("test_launch")
    mock_uc.Chrome.assert_called_once()

def test_close_browser(browser_manager):
    """Test browser close with mocked undetected_chromedriver."""
    browser_manager.create_profile("test_close")

    mock_uc = MagicMock()
    mock_driver = MagicMock()
    mock_uc.Chrome.return_value = mock_driver
    mock_uc.ChromeOptions.return_value = MagicMock()

    with patch.object(bm_module, 'uc', mock_uc):
        browser_manager.launch_browser("test_close")

    assert browser_manager.is_profile_running("test_close")

    browser_manager.close_browser("test_close")

    assert not browser_manager.is_profile_running("test_close")
    mock_driver.quit.assert_called_once()
