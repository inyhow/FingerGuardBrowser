"""
Human Behavior Simulation Module.

Inspired by CloakBrowser's `humanize=True` flag, this module adds realistic
human-like interaction patterns to browser automation:

- Bézier curve mouse movement with easing and overshoot
- Per-character typing with random delays, thinking pauses, and typos with self-correction
- Natural scroll behavior (accelerate → cruise → decelerate)
- Random idle micro-movements between actions

Usage::

    from src.fingerprint.humanize import Humanizer

    humanizer = Humanizer(driver)
    humanizer.move_to(element)
    humanizer.click(element)
    humanizer.type_text(element, "hello world")
    humanizer.scroll_by(0, 500)
"""

import random
import math
import time
from loguru import logger
from typing import Optional, Tuple, List


class Humanizer:
    """Inject human-like interaction patterns via CDP Input domain."""

    def __init__(self, driver, config: dict = None):
        self.driver = driver
        self.config = config or {}
        # Defaults — tuned to feel natural without being too slow
        self.mistype_chance = self.config.get("mistype_chance", 0.03)
        self.typing_delay_min = self.config.get("typing_delay_min", 50)   # ms
        self.typing_delay_max = self.config.get("typing_delay_max", 150)  # ms
        self.thinking_pause_chance = self.config.get("thinking_pause_chance", 0.1)
        self.thinking_pause_min = self.config.get("thinking_pause_min", 300)   # ms
        self.thinking_pause_max = self.config.get("thinking_pause_max", 1000)  # ms
        self.mouse_speed = self.config.get("mouse_speed", 1.0)  # multiplier
        self.overshoot_chance = self.config.get("overshoot_chance", 0.3)
        self.idle_between = self.config.get("idle_between", True)

    # ── Bézier curve utilities ──────────────────────────────────────────

    @staticmethod
    def _cubic_bezier(t: float, p0: Tuple, p1: Tuple, p2: Tuple, p3: Tuple) -> Tuple[float, float]:
        """Evaluate cubic Bézier curve at parameter t (0..1)."""
        u = 1 - t
        x = (u**3 * p0[0] + 3 * u**2 * t * p1[0] + 3 * u * t**2 * p2[0] + t**3 * p3[0])
        y = (u**3 * p0[1] + 3 * u**2 * t * p1[1] + 3 * u * t**2 * p2[1] + t**3 * p3[1])
        return (x, y)

    @staticmethod
    def _ease_out_quart(t: float) -> float:
        """Ease-out quartic: fast start, slow end (natural mouse deceleration)."""
        return 1 - (1 - t) ** 4

    @staticmethod
    def _ease_in_out_cubic(t: float) -> float:
        """Ease-in-out cubic: smooth acceleration and deceleration."""
        if t < 0.5:
            return 4 * t ** 3
        return 1 - ((-2 * t + 2) ** 3) / 2

    def _generate_bezier_path(
        self, start: Tuple[float, float], end: Tuple[float, float]
    ) -> List[Tuple[float, float]]:
        """Generate a list of (x, y) points along a Bézier curve from start to end.

        Control points are randomized to create natural-looking arcs.
        May include overshoot past the target.
        """
        # Distance determines number of steps
        dist = math.hypot(end[0] - start[0], end[1] - start[1])
        num_steps = max(10, int(dist / 5))  # ~5px per step

        # Random control points perpendicular to the line for natural curvature
        mid_x = (start[0] + end[0]) / 2
        mid_y = (start[1] + end[1]) / 2
        perp_x = -(end[1] - start[1]) / max(dist, 1)
        perp_y = (end[0] - start[0]) / max(dist, 1)

        # Offset control points from the midpoint
        offset1 = random.uniform(-dist * 0.3, dist * 0.3)
        offset2 = random.uniform(-dist * 0.3, dist * 0.3)
        cp1 = (mid_x - (end[0] - start[0]) * 0.25 + perp_x * offset1,
               mid_y - (end[1] - start[1]) * 0.25 + perp_y * offset1)
        cp2 = (mid_x + (end[0] - start[0]) * 0.25 + perp_x * offset2,
               mid_y + (end[1] - start[1]) * 0.25 + perp_y * offset2)

        # Overshoot: extend past the target then come back
        overshoot_target = None
        if random.random() < self.overshoot_chance and dist > 20:
            overshoot_dist = random.uniform(5, 15)
            direction = ((end[0] - start[0]) / max(dist, 1), (end[1] - start[1]) / max(dist, 1))
            overshoot_target = (end[0] + direction[0] * overshoot_dist,
                                end[1] + direction[1] * overshoot_dist)

        path = []
        for i in range(num_steps + 1):
            t = i / num_steps
            eased_t = self._ease_in_out_cubic(t)
            x, y = self._cubic_bezier(eased_t, start, cp1, cp2, end if not overshoot_target else overshoot_target)
            path.append((x, y))

        # If overshooting, add return path
        if overshoot_target:
            return_steps = max(5, int(overshoot_dist / 3))
            for i in range(1, return_steps + 1):
                t = i / return_steps
                eased_t = self._ease_out_quart(t)
                x = overshoot_target[0] + (end[0] - overshoot_target[0]) * eased_t
                y = overshoot_target[1] + (end[1] - overshoot_target[1]) * eased_t
                path.append((x, y))

        return path

    # ── CDP dispatch helpers ────────────────────────────────────────────

    def _dispatch_mouse(self, x: float, y: float, button: str = "none",
                        button_type: str = "mousePressed" or "mouseMoved" or "mouseReleased"):
        """Dispatch a mouse event via CDP Input domain."""
        try:
            self.driver.execute_cdp_cmd("Input.dispatchMouseEvent", {
                "type": button_type,
                "x": x,
                "y": y,
                "button": button,
                "buttons": 1 if button_type == "mousePressed" else 0,
                "clickCount": 1 if button_type == "mousePressed" else 0,
                "pointerType": "mouse",
            })
        except Exception as e:
            logger.debug(f"Mouse dispatch error: {e}")

    def _dispatch_key(self, key: str, code: str = "", key_code: int = 0,
                      event_type: str = "keyDown" or "keyUp" or "char"):
        """Dispatch a key event via CDP Input domain."""
        try:
            params = {
                "type": event_type,
                "key": key,
                "text": key if len(key) == 1 and key.isprintable() else "",
                "modifiers": 0,
                "timestamp": int(time.time() * 1000),
            }
            if code:
                params["code"] = code
            if key_code:
                params["windowsVirtualKeyCode"] = key_code
            self.driver.execute_cdp_cmd("Input.dispatchKeyEvent", params)
        except Exception as e:
            logger.debug(f"Key dispatch error: {e}")

    # ── Public API ──────────────────────────────────────────────────────

    def get_element_center(self, element) -> Tuple[float, float]:
        """Get the center coordinates of a Selenium element."""
        rect = element.rect
        return (rect["x"] + rect["width"] / 2, rect["y"] + rect["height"] / 2)

    def move_to(self, x: float, y: float, element=None):
        """Move mouse to (x, y) or the center of an element using a Bézier curve.

        If element is provided, x and y are relative to the element's center.
        """
        if element is not None:
            cx, cy = self.get_element_center(element)
            x, y = cx + x, cy + y

        # Get current mouse position (approximate — track internally)
        start = getattr(self, "_last_pos", (random.uniform(100, 400), random.uniform(100, 400)))

        path = self._generate_bezier_path(start, (x, y))
        for px, py in path:
            self._dispatch_mouse(px, py, button_type="mouseMoved")
            time.sleep(random.uniform(0.005, 0.015) / self.mouse_speed)

        self._last_pos = (x, y)

        # Idle micro-movement
        if self.idle_between and random.random() < 0.15:
            time.sleep(random.uniform(0.1, 0.3))
            # Small jitter
            jx = x + random.uniform(-3, 3)
            jy = y + random.uniform(-3, 3)
            self._dispatch_mouse(jx, jy, button_type="mouseMoved")
            time.sleep(random.uniform(0.05, 0.15))

    def click(self, x: float = None, y: float = None, element=None,
              button: str = "left", hold_duration: float = 0.05):
        """Click at (x, y) or on an element with natural mouse movement.

        Moves to the target first via Bézier curve, then presses and releases.
        """
        if element is not None:
            cx, cy = self.get_element_center(element)
            if x is not None:
                cx += x
            if y is not None:
                cy += y
            x, y = cx, cy
        elif x is None or y is None:
            raise ValueError("Must provide x,y or element")

        # Move to target first
        self.move_to(x, y)

        # Small pause before click (natural hesitation)
        time.sleep(random.uniform(0.05, 0.15))

        # Press
        self._dispatch_mouse(x, y, button=button, button_type="mousePressed")
        time.sleep(hold_duration + random.uniform(0.02, 0.08))  # Natural hold
        # Release
        self._dispatch_mouse(x, y, button=button, button_type="mouseReleased")

        logger.debug(f"Clicked at ({x:.0f}, {y:.0f})")

    def type_text(self, element, text: str, clear_first: bool = True):
        """Type text into an element with realistic per-character timing.

        Features:
        - Clears existing content first (if clear_first)
        - Per-character random delay
        - Occasional typos with self-correction
        - Thinking pauses mid-text
        """
        if clear_first:
            try:
                element.click()
            except Exception:
                pass
            # Clear via Ctrl+A + Delete
            self._dispatch_key("a", "KeyA", 65, "keyDown")
            self._dispatch_key("a", "KeyA", 65, "keyUp")
            self._dispatch_key("Delete", "Delete", 46, "keyDown")
            self._dispatch_key("Delete", "Delete", 46, "keyUp")
            time.sleep(random.uniform(0.1, 0.3))

        for i, char in enumerate(text):
            # Thinking pause
            if random.random() < self.thinking_pause_chance:
                pause = random.uniform(
                    self.thinking_pause_min / 1000,
                    self.thinking_pause_max / 1000,
                )
                time.sleep(pause)

            # Typo with self-correction
            if random.random() < self.mistype_chance and char.isalpha():
                wrong_char = random.choice(
                    "abcdefghijklmnopqrstuvwxyz" if char.islower() else "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
                )
                # Type wrong character
                self._dispatch_key(wrong_char, "", ord(wrong_char), "keyDown")
                self._dispatch_key(wrong_char, "", ord(wrong_char), "keyUp")
                time.sleep(random.uniform(0.05, 0.15))  # Notice the mistake
                # Backspace
                self._dispatch_key("Backspace", "Backspace", 8, "keyDown")
                self._dispatch_key("Backspace", "Backspace", 8, "keyUp")
                time.sleep(random.uniform(0.03, 0.1))  # Brief pause
                # Type correct character
                self._dispatch_key(char, "", ord(char), "keyDown")
                self._dispatch_key(char, "", ord(char), "keyUp")
            else:
                # Normal character
                self._dispatch_key(char, "", ord(char), "keyDown")
                self._dispatch_key(char, "", ord(char), "keyUp")

            # Per-character delay
            delay = random.uniform(
                self.typing_delay_min / 1000,
                self.typing_delay_max / 1000,
            )
            time.sleep(delay)

        logger.debug(f"Typed '{text[:20]}...' into element")

    def scroll_by(self, dx: int = 0, dy: int = 0, element=None):
        """Scroll by (dx, dy) pixels with natural acceleration/deceleration.

        Uses multiple mouseWheel events to simulate natural scrolling.
        """
        total = abs(dy) if dy != 0 else abs(dx)
        if total == 0:
            return

        # Break into micro-steps with acceleration profile
        num_steps = max(3, int(total / 50))
        steps = []
        for i in range(num_steps):
            t = i / max(num_steps - 1, 1)
            # Accelerate → cruise → decelerate
            if t < 0.3:
                speed = self._ease_in_out_cubic(t / 0.3) * 0.5
            elif t > 0.7:
                speed = 1 - self._ease_in_out_cubic((t - 0.7) / 0.3) * 0.5
            else:
                speed = 1.0
            step_size = int(total / num_steps * speed)
            steps.append(step_size)

        # Normalize to match total
        scale = total / max(sum(steps), 1)
        steps = [max(1, int(s * scale)) for s in steps]

        x, y = getattr(self, "_last_pos", (400, 300))
        for step in steps:
            try:
                self.driver.execute_cdp_cmd("Input.dispatchMouseEvent", {
                    "type": "mouseWheel",
                    "x": x,
                    "y": y,
                    "deltaX": int(dx * step / total) if dx else 0,
                    "deltaY": int(dy * step / total) if dy else 0,
                    "pointerType": "mouse",
                })
            except Exception as e:
                # Fallback: use JS scroll
                try:
                    self.driver.execute_script(f"window.scrollBy({int(dx * step / total)}, {int(dy * step / total)});")
                except Exception:
                    pass
            time.sleep(random.uniform(0.01, 0.04))

        logger.debug(f"Scrolled by ({dx}, {dy})")

    def scroll_to_element(self, element):
        """Scroll until an element is in view, with natural movement."""
        try:
            # Get element position
            rect = element.rect
            viewport_h = self.driver.execute_script("return window.innerHeight;")
            current_scroll = self.driver.execute_script("return window.scrollY;")
            target_scroll = rect["y"] - viewport_h / 2

            dy = int(target_scroll - current_scroll)
            if abs(dy) > 10:
                self.scroll_by(0, dy)
        except Exception as e:
            logger.debug(f"Scroll to element error: {e}")
            # Fallback: native scrollIntoView
            try:
                self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", element)
            except Exception:
                pass

    def random_idle(self, duration_range: Tuple[float, float] = (0.5, 2.0)):
        """Simulate idle human behavior — small mouse movements and pauses.

        Useful for appearing more human between automated actions.
        """
        duration = random.uniform(*duration_range)
        end_time = time.time() + duration

        while time.time() < end_time:
            action = random.choice(["move", "pause", "scroll"])
            if action == "move":
                # Small random mouse movement
                cx, cy = getattr(self, "_last_pos", (400, 300))
                nx = cx + random.uniform(-100, 100)
                ny = cy + random.uniform(-100, 100)
                nx = max(10, min(nx, self.driver.execute_script("return window.innerWidth;") - 10))
                ny = max(10, min(ny, self.driver.execute_script("return window.innerHeight;") - 10))
                self.move_to(nx, ny)
            elif action == "scroll":
                self.scroll_by(0, random.randint(-200, 200))
            else:
                time.sleep(random.uniform(0.3, 1.0))

    def human_navigate(self, url: str):
        """Navigate to a URL with human-like behavior (small delay, then navigate)."""
        # Small hesitation before navigating
        time.sleep(random.uniform(0.2, 0.8))
        self.driver.get(url)
        # Wait a bit for page to start loading, then move mouse
        time.sleep(random.uniform(0.5, 1.5))
        self.move_to(random.uniform(200, 600), random.uniform(200, 400))
