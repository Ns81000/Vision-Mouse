"""Vision Mouse — Application entry point.

Boots all components, starts the tray icon, and keeps the process alive.
"""

from __future__ import annotations

import ctypes
import logging
import os
import sys


def _setup_logging() -> None:
    """Configure logging to %APPDATA%/VisionMouse/error.log."""
    log_dir = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "VisionMouse")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "error.log")
    logging.basicConfig(
        filename=log_path,
        level=logging.ERROR,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    # Also log INFO to stderr during development
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logging.getLogger().addHandler(console)
    logging.getLogger().setLevel(logging.INFO)


def _enforce_single_instance() -> bool:
    """Return True if this is the only running instance (Windows mutex)."""
    mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "VisionMouseSingleInstance")
    if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        return False
    # Keep a reference so the mutex is not garbage-collected
    _enforce_single_instance._mutex = mutex  # type: ignore[attr-defined]
    return True


def main() -> None:
    """Application entry point."""
    _setup_logging()
    logger = logging.getLogger(__name__)

    # ── Single instance guard ──────────────────────────────
    if not _enforce_single_instance():
        logger.info("Another instance is already running. Exiting.")
        sys.exit(0)

    # ── Load settings ──────────────────────────────────────
    from vision_mouse.settings_store import SettingsStore

    settings = SettingsStore.load()
    logger.info("Settings loaded: %s", settings)

    # ── Verify model file exists ──────────────────────────
    from vision_mouse.tracker import _get_model_path

    model_path = _get_model_path()
    if not os.path.isfile(model_path):
        logger.error("MediaPipe model not found at %s", model_path)
        try:
            ctypes.windll.user32.MessageBoxW(
                0,
                f"hand_landmarker.task not found in:\n{model_path}\n\n"
                "Please download it and place it in assets/models/.\n"
                "Tracking will be disabled.",
                "Vision Mouse — Model Missing",
                0x30,  # MB_ICONWARNING
            )
        except Exception:
            pass

    # ── System tray (blocks main thread) ──────────────────
    from vision_mouse.hotkey import HotkeyManager
    from vision_mouse.ui.tray import SystemTray

    tray = SystemTray(settings)

    hotkey_manager = HotkeyManager(
        hotkey=settings.hotkey,
        on_toggle=tray.toggle_tracking,
    )
    tray.set_hotkey_manager(hotkey_manager)
    hotkey_manager.start()

    logger.info("Vision Mouse started. Hotkey: %s", settings.hotkey)
    tray.run()  # blocks — Tk mainloop on main thread, pystray in background


if __name__ == "__main__":
    main()
