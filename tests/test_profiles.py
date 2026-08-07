import os
import shutil
import pytest
from src.browser.profile import ProfileManager

@pytest.fixture
def temp_config_dir(tmpdir):
    return str(tmpdir.mkdir("config"))

def test_create_profile(temp_config_dir):
    manager = ProfileManager(temp_config_dir)
    profile_name = "test_profile"
    manager.create_profile(profile_name, proxy="socks5://127.0.0.1:1080")

    assert profile_name in manager.profiles
    assert manager.profiles[profile_name].proxy == "socks5://127.0.0.1:1080"
    assert os.path.exists(os.path.join(temp_config_dir, "profiles.json"))

def test_load_profiles(temp_config_dir):
    manager = ProfileManager(temp_config_dir)
    profile_name = "test_profile"
    manager.create_profile(profile_name, proxy="socks5://127.0.0.1:1080")

    # Create a new manager instance to load from file
    new_manager = ProfileManager(temp_config_dir)
    assert profile_name in new_manager.profiles
    assert new_manager.profiles[profile_name].proxy == "socks5://127.0.0.1:1080"

def test_update_profile(temp_config_dir):
    manager = ProfileManager(temp_config_dir)
    profile_name = "test_profile"
    manager.create_profile(profile_name)
    manager.update_profile(profile_name, proxy="http://localhost:8080")

    assert manager.profiles[profile_name].proxy == "http://localhost:8080"

def test_delete_profile(temp_config_dir):
    manager = ProfileManager(temp_config_dir)
    profile_name = "test_profile"
    manager.create_profile(profile_name)
    manager.delete_profile(profile_name)

    assert profile_name not in manager.profiles
