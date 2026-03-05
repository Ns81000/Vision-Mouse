"""Global hotkey registration and toggle logic using the `keyboard` library."""

from __future__ import annotations

import logging
from typing import Callable, Optional

import keyboard

logger = logging.getLogger(__name__)


class HotkeyManager:
    """Register and listen for a global hotkey that toggles tracking on/off."""

    def __init__(self, hotkey: str, on_toggle: Callable[[], None]) -> None:
        self.hotkey = hotkey
        self.on_toggle = on_toggle
        self._hook: Optional[object] = None

    def start(self) -> None:
        """Register the hotkey using keyboard.add_hotkey()."""
        try:
            self._hook = keyboard.add_hotkey(
                self.hotkey, self.on_toggle, suppress=False
            )
            logger.info("Hotkey '%s' registered", self.hotkey)
        except Exception as exc:
            logger.error("Failed to register hotkey '%s': %s", self.hotkey, exc)

    def stop(self) -> None:
        """Unregister the current hotkey."""
        if self._hook is not None:
            try:
                keyboard.remove_hotkey(self._hook)
            except (ValueError, KeyError):
                pass
            self._hook = None

    def update_hotkey(self, new_hotkey: str) -> None:
        """Unregister the old hotkey and register a new one."""
        self.stop()
        self.hotkey = new_hotkey
        self.start()
