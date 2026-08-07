"""Profile group management with bulk operations.

Allows organizing profiles into groups (e.g., "Amazon accounts", "Social media")
and applying settings, launching, and stopping profiles in bulk.

Reference: Donut Browser's profile groups with bulk settings.
"""

from typing import Dict, Any, Optional, List
from loguru import logger


class GroupManager:
    """Manage profile groups and bulk operations."""

    def __init__(self, database=None, browser_manager=None):
        if database is None:
            from ..storage.database import Database
            database = Database()
        self.db = database
        self.browser_manager = browser_manager

    def create_group(self, name: str, description: str = "", color: str = "#4263eb",
                     settings: dict = None) -> Dict[str, Any]:
        """Create a new profile group."""
        group = self.db.create_group(name, description, color, settings)
        logger.info(f"Created group: {name}")
        return group

    def delete_group(self, name: str) -> bool:
        """Delete a profile group. Profiles are unassigned but not deleted."""
        result = self.db.delete_group(name)
        if result:
            logger.info(f"Deleted group: {name}")
        return result

    def list_groups(self) -> List[Dict[str, Any]]:
        """List all profile groups."""
        return self.db.list_groups()

    def get_group(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a specific group by name."""
        return self.db.get_group(name)

    def get_profiles_in_group(self, group_name: str) -> List[Dict[str, Any]]:
        """Get all profiles in a specific group."""
        group = self.db.get_group(group_name)
        if not group:
            return []
        return self.db.list_profiles(group_id=group["id"])

    def assign_profile_to_group(self, profile_name: str, group_name: str) -> bool:
        """Assign a profile to a group."""
        group = self.db.get_group(group_name)
        if not group:
            logger.error(f"Group not found: {group_name}")
            return False
        self.db.update_profile(profile_name, group_id=group["id"])
        return True

    def unassign_profile_from_group(self, profile_name: str) -> bool:
        """Remove a profile from its group."""
        self.db.update_profile(profile_name, group_id=None)
        return True

    def bulk_launch(self, group_name: str) -> Dict[str, Any]:
        """Launch all profiles in a group."""
        if not self.browser_manager:
            return {"error": "Browser manager not configured"}

        profiles = self.get_profiles_in_group(group_name)
        results = {"launched": [], "failed": []}

        for profile in profiles:
            if not profile.get("is_running"):
                try:
                    self.browser_manager.launch_browser(profile["name"])
                    results["launched"].append(profile["name"])
                except Exception as e:
                    logger.error(f"Failed to launch {profile['name']}: {e}")
                    results["failed"].append({"name": profile["name"], "error": str(e)})

        logger.info(f"Bulk launch for '{group_name}': {len(results['launched'])} started, "
                     f"{len(results['failed'])} failed")
        return results

    def bulk_stop(self, group_name: str) -> Dict[str, Any]:
        """Stop all running profiles in a group."""
        if not self.browser_manager:
            return {"error": "Browser manager not configured"}

        profiles = self.get_profiles_in_group(group_name)
        results = {"stopped": [], "failed": []}

        for profile in profiles:
            if profile.get("is_running"):
                try:
                    self.browser_manager.close_browser(profile["name"])
                    results["stopped"].append(profile["name"])
                except Exception as e:
                    logger.error(f"Failed to stop {profile['name']}: {e}")
                    results["failed"].append({"name": profile["name"], "error": str(e)})

        logger.info(f"Bulk stop for '{group_name}': {len(results['stopped'])} stopped, "
                     f"{len(results['failed'])} failed")
        return results

    def bulk_apply_settings(self, group_name: str, settings: dict) -> int:
        """Apply settings to all profiles in a group.

        Supported keys: proxy, timezone, webrtc, canvas_fp, webgl_fp, audio_fp,
        dns_protection, custom_dns, dns_leak_protection.
        """
        profiles = self.get_profiles_in_group(group_name)
        count = 0
        for profile in profiles:
            self.db.update_profile(profile["name"], **settings)
            count += 1

        logger.info(f"Applied settings to {count} profiles in group '{group_name}'")
        return count

    def bulk_assign_proxy(self, group_name: str, proxy_pool=None,
                          rotation: bool = False) -> int:
        """Assign proxies to all profiles in a group.

        If rotation=True, each profile gets a different healthy proxy from the pool.
        """
        profiles = self.get_profiles_in_group(group_name)
        count = 0

        if proxy_pool:
            for profile in profiles:
                if rotation:
                    proxy = proxy_pool.rotate_proxy(group_name)
                else:
                    proxy = proxy_pool.get_healthy_proxy()

                if proxy:
                    proxy_url = proxy_pool.get_proxy_url(proxy["name"])
                    if proxy_url:
                        self.db.update_profile(profile["name"], proxy=proxy_url)
                        count += 1
        else:
            logger.warning("No proxy pool provided for bulk proxy assignment")

        logger.info(f"Assigned proxies to {count} profiles in group '{group_name}'")
        return count
