"""System tray icon with right-click menu using pystray."""

from __future__ import annotations

import logging
import os
import sys
import threading
from typing import TYPE_CHECKING, Optional

import pystray
from PIL import Image
from pystray import Icon, Menu, MenuItem

from vision_mouse.mouse_controller import MouseController
from vision_mouse.settings_store import Settings, SettingsStore
from vision_mouse.tracker import HandTracker
from vision_mouse.ui.pip_overlay import PipOverlay, annotate_frame

if TYPE_CHECKING:
    from vision_mouse.hotkey import HotkeyManager

logger = logging.getLogger(__name__)


def _get_icon_path() -> str:
    """Resolve icon path whether running as script or bundled .exe."""
    if getattr(sys, "frozen", False):
        base = sys._MEIPASS  # type: ignore[attr-defined]
    else:
        base = os.path.dirname(os.path.abspath(__file__))
        base = os.path.normpath(os.path.join(base, "..", "..", ".."))
    return os.path.join(base, "assets", "icon.ico")


def _create_default_icon() -> Image.Image:
    """Create a simple placeholder icon if icon.ico is not found."""
    from PIL import ImageDraw

    img = Image.new("RGB", (64, 64), "#1A1A1A")
    draw = ImageDraw.Draw(img)
    # Draw a stylised eye
    draw.ellipse((8, 16, 56, 48), outline="#4A9EFF", width=3)
    draw.ellipse((24, 26, 40, 38), fill="#4A9EFF")
    return img


class SystemTray:
    """System tray icon with right-click menu."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._tracking = False
        self._tracker: Optional[HandTracker] = None
        self._mouse_ctrl = MouseController()
        self._hotkey_manager: Optional["HotkeyManager"] = None
        self._pip_overlay: Optional[PipOverlay] = None
        self._tk_root = None  # Main-thread Tk root (created in run())

        # Load icon image
        icon_path = _get_icon_path()
        if os.path.isfile(icon_path):
            self._image = Image.open(icon_path)
        else:
            logger.warning("icon.ico not found at %s, using default", icon_path)
            self._image = _create_default_icon()

        self._icon = Icon(
            name="VisionMouse",
            icon=self._image,
            title="Vision Mouse",
            menu=self._build_menu(),
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_hotkey_manager(self, hm: "HotkeyManager") -> None:
        self._hotkey_manager = hm

    def run(self) -> None:
        """Start tray icon and Tk event loop on the main thread."""
        import customtkinter as ctk

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        self._tk_root = ctk.CTk()
        self._tk_root.withdraw()

        # pystray in a background thread (Tk needs the main thread on Windows)
        threading.Thread(target=self._icon.run, daemon=True).start()

        # Block main thread on Tk mainloop
        self._tk_root.mainloop()

    def toggle_tracking(self) -> None:
        """Start or stop hand tracking (called from hotkey or menu)."""
        if self._tracking:
            self._stop_tracking()
        else:
            self._start_tracking()
        # Refresh menu labels
        self._icon.update_menu()

    # ------------------------------------------------------------------
    # Menu
    # ------------------------------------------------------------------

    def _build_menu(self) -> Menu:
        return Menu(
            MenuItem(
                "Vision Mouse Active",
                action=None,
                enabled=False,
            ),
            Menu.SEPARATOR,
            MenuItem(
                lambda item: "\u23F9 Disable" if self._tracking else "\u25B6 Enable",
                self._on_toggle_menu,
            ),
            MenuItem(
                lambda item: "\U0001F441 Hide Preview" if self._pip_overlay and self._pip_overlay.is_open else "\U0001F441 Show Preview",
                self._on_toggle_pip,
            ),
            MenuItem("\u2699 Settings", self._on_settings),
            Menu.SEPARATOR,
            MenuItem("\u2715 Quit", self._on_quit),
        )

    # ------------------------------------------------------------------
    # Menu callbacks
    # ------------------------------------------------------------------

    def _on_toggle_menu(self, icon: Icon, item: MenuItem) -> None:  # noqa: ARG002
        self.toggle_tracking()

    def _on_toggle_pip(self, icon: Icon, item: MenuItem) -> None:  # noqa: ARG002
        if self._tk_root:
            self._tk_root.after(0, self._toggle_pip_overlay)

    def _on_settings(self, icon: Icon, item: MenuItem) -> None:  # noqa: ARG002
        if self._tk_root:
            self._tk_root.after(0, self._open_settings)

    def _on_quit(self, icon: Icon, item: MenuItem) -> None:  # noqa: ARG002
        self._stop_tracking()
        if self._hotkey_manager is not None:
            self._hotkey_manager.stop()
        self._icon.stop()
        if self._tk_root:
            self._tk_root.after(0, self._quit_tk)

    # ------------------------------------------------------------------
    # Tracking helpers
    # ------------------------------------------------------------------

    def _start_tracking(self) -> None:
        if self._tracking:
            return
        self._tracker = HandTracker(
            on_move=self._mouse_ctrl.move_to,
            on_click=self._handle_click,
            settings=self._settings,
            on_frame=self._on_tracker_frame,
        )
        self._tracker.start(self._settings.camera_index)
        self._tracking = True
        logger.info("Tracking started (camera %d)", self._settings.camera_index)

        # Auto-open PiP overlay if setting enabled
        if self._settings.show_camera_preview and self._tk_root:
            self._tk_root.after(0, self._open_pip_overlay)

    def _stop_tracking(self) -> None:
        if not self._tracking:
            return
        # Close PiP on the Tk main thread
        if self._tk_root:
            self._tk_root.after(0, self._close_pip_overlay)
        if self._tracker is not None:
            self._tracker.stop()
            self._tracker = None
        self._tracking = False
        logger.info("Tracking stopped")

    def _handle_click(self, action: str) -> None:
        """Route click/scroll actions from the tracker."""
        if action == "left":
            self._mouse_ctrl.click("left")
        elif action == "right":
            self._mouse_ctrl.click("right")
        elif action == "down":
            self._mouse_ctrl.press("left")
        elif action == "up":
            self._mouse_ctrl.release("left")
        elif action.startswith("scroll_"):
            direction = int(action.split("_")[1])
            self._mouse_ctrl.scroll(direction)

    # ------------------------------------------------------------------
    # PiP overlay helpers
    # ------------------------------------------------------------------

    def _on_tracker_frame(self, frame_bgr, landmarks, gesture: str) -> None:
        """Called from the tracker thread with each new frame."""
        if self._pip_overlay is None or not self._pip_overlay.is_open:
            return
        # Annotate the frame with landmarks and gesture
        annotated = annotate_frame(frame_bgr.copy(), landmarks, gesture)
        self._pip_overlay.update_frame(annotated)

    def _open_pip_overlay(self) -> None:
        """Open the PiP overlay window. Must be called on the Tk main thread."""
        if self._pip_overlay is not None and self._pip_overlay.is_open:
            return
        if self._tk_root:
            self._pip_overlay = PipOverlay(self._tk_root)

    def _close_pip_overlay(self) -> None:
        """Close the PiP overlay. Must be called on the Tk main thread."""
        if self._pip_overlay is not None:
            try:
                self._pip_overlay.close()
            except Exception:
                pass
            self._pip_overlay = None

    def _toggle_pip_overlay(self) -> None:
        """Toggle the PiP overlay on/off. Must be called on the Tk main thread."""
        if self._pip_overlay is not None and self._pip_overlay.is_open:
            self._close_pip_overlay()
        else:
            if self._tracking:
                self._open_pip_overlay()
        self._icon.update_menu()

    def _quit_tk(self) -> None:
        """Shut down the Tk event loop. Must be called on the Tk main thread."""
        self._close_pip_overlay()
        if self._tk_root:
            self._tk_root.quit()

    # ------------------------------------------------------------------
    # Settings window
    # ------------------------------------------------------------------

    def _open_settings(self) -> None:
        """Open the settings window. Must be called on the Tk main thread."""
        from vision_mouse.ui.settings_window import SettingsWindow

        SettingsWindow(self._settings, on_save=self._apply_settings)

    def _apply_settings(self, new_settings: Settings) -> None:
        """Called when the user saves new settings."""
        old_hotkey = self._settings.hotkey
        self._settings = new_settings

        # Update hotkey if changed
        if self._hotkey_manager and new_settings.hotkey != old_hotkey:
            self._hotkey_manager.update_hotkey(new_settings.hotkey)

        # Restart tracking if active to pick up new settings
        if self._tracking:
            self._stop_tracking()
            self._start_tracking()
