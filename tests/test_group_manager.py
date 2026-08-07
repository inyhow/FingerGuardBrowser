"""Tests for profile group management."""

import pytest
from src.storage.database import Database
from src.profiles.group_manager import GroupManager


@pytest.fixture
def gm(tmp_path):
    Database._instance = None
    db = Database(db_path=str(tmp_path / "test.db"))
    return GroupManager(database=db)


class TestGroupManager:
    def test_create_group(self, gm):
        group = gm.create_group("Amazon", description="Amazon accounts", color="#ff6b6b")
        assert group["name"] == "Amazon"
        assert group["description"] == "Amazon accounts"
        assert group["color"] == "#ff6b6b"

    def test_list_groups(self, gm):
        gm.create_group("Group1")
        gm.create_group("Group2")
        groups = gm.list_groups()
        assert len(groups) == 2

    def test_delete_group(self, gm):
        gm.create_group("ToDelete")
        assert gm.delete_group("ToDelete") is True
        assert gm.get_group("ToDelete") is None

    def test_assign_profile_to_group(self, gm):
        gm.create_group("Social")
        gm.db.create_profile("fb1")
        assert gm.assign_profile_to_group("fb1", "Social") is True
        profiles = gm.get_profiles_in_group("Social")
        assert len(profiles) == 1
        assert profiles[0]["name"] == "fb1"

    def test_assign_to_nonexistent_group(self, gm):
        gm.db.create_profile("p1")
        assert gm.assign_profile_to_group("p1", "Nonexistent") is False

    def test_unassign_profile(self, gm):
        gm.create_group("Social")
        gm.db.create_profile("fb1")
        gm.assign_profile_to_group("fb1", "Social")
        gm.unassign_profile_from_group("fb1")
        profiles = gm.get_profiles_in_group("Social")
        assert len(profiles) == 0

    def test_bulk_apply_settings(self, gm):
        gm.create_group("Amazon")
        gm.db.create_profile("amz1")
        gm.db.create_profile("amz2")
        gm.assign_profile_to_group("amz1", "Amazon")
        gm.assign_profile_to_group("amz2", "Amazon")

        count = gm.bulk_apply_settings("Amazon", {"timezone": "America/New_York", "webrtc": "filter"})
        assert count == 2

        p1 = gm.db.get_profile("amz1")
        p2 = gm.db.get_profile("amz2")
        assert p1["timezone"] == "America/New_York"
        assert p2["webrtc"] == "filter"

    def test_get_profiles_in_empty_group(self, gm):
        gm.create_group("Empty")
        profiles = gm.get_profiles_in_group("Empty")
        assert len(profiles) == 0

    def test_get_profiles_in_nonexistent_group(self, gm):
        profiles = gm.get_profiles_in_group("Nonexistent")
        assert len(profiles) == 0
