"""CustomTkinter settings panel — dark mode, modern, minimal."""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING, Optional

import customtkinter as ctk
import keyboard

from vision_mouse.camera import CameraManager
from vision_mouse.settings_store import Settings, SettingsStore

if TYPE_CHECKING:
    from typing import Callable

logger = logging.getLogger(__name__)

# Singleton guard
_instance: Optional["SettingsWindow"] = None


class SettingsWindow(ctk.CTkToplevel):
    """A 420×580 always-on-top dark settings panel."""

    def __init__(
        self,
        settings: Settings,
        on_save: Callable[[Settings], None],
    ) -> None:
        global _instance
        if _instance is not None and _instance.winfo_exists():
            _instance.lift()
            _instance.focus_force()
            return
        _instance = self

        super().__init__()

        self._settings = settings
        self._on_save = on_save

        # ── Theme ──────────────────────────────────────────────
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # ── Window ─────────────────────────────────────────────
        self.title("Vision Mouse \u2014 Settings")
        self.geometry("420x580")
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.configure(fg_color="#1A1A1A")
        self._center_on_screen()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # ── Build UI ──────────────────────────────────────────
        self._build()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build(self) -> None:
        pad_x = 20
        pad_y = (6, 6)

        # Header
        ctk.CTkLabel(
            self,
            text="Vision Mouse",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color="#FFFFFF",
        ).pack(pady=(18, 2))
        ctk.CTkLabel(
            self,
            text="v1.0.0  \u2014  Settings",
            font=ctk.CTkFont(size=12),
            text_color="#999999",
        ).pack(pady=(0, 12))

        # ── Camera ─────────────────────────────────────────────
        self._section_label("CAMERA")
        cameras = CameraManager.list_cameras()
        cam_names = [c["name"] for c in cameras] if cameras else ["No camera found"]
        current_cam = next(
            (c["name"] for c in cameras if c["index"] == self._settings.camera_index),
            cam_names[0],
        )
        self._camera_var = ctk.StringVar(value=current_cam)
        self._camera_combo = ctk.CTkComboBox(
            self,
            width=380,
            height=36,
            values=cam_names,
            variable=self._camera_var,
            state="readonly",
        )
        self._camera_combo.pack(padx=pad_x, pady=pad_y)
        self._cameras = cameras

        # ── Hotkey ─────────────────────────────────────────────
        self._section_label("HOTKEY")
        hotkey_frame = ctk.CTkFrame(self, fg_color="transparent")
        hotkey_frame.pack(padx=pad_x, pady=pad_y, fill="x")

        self._hotkey_var = ctk.StringVar(value=self._settings.hotkey)
        self._hotkey_entry = ctk.CTkEntry(
            hotkey_frame, textvariable=self._hotkey_var, width=260, height=36
        )
        self._hotkey_entry.pack(side="left", padx=(0, 10))

        self._record_btn = ctk.CTkButton(
            hotkey_frame,
            text="Record",
            width=100,
            height=36,
            command=self._record_hotkey,
        )
        self._record_btn.pack(side="left")

        # ── Sensitivity ────────────────────────────────────────
        self._section_label("SENSITIVITY")
        self._sens_label = ctk.CTkLabel(
            self,
            text=f"{self._settings.sensitivity:.1f}",
            font=ctk.CTkFont(size=12),
            text_color="#FFFFFF",
        )
        self._sens_label.pack()
        self._sens_slider = ctk.CTkSlider(
            self,
            from_=0.5,
            to=3.0,
            number_of_steps=25,
            width=320,
            height=18,
            button_color="#4A9EFF",
            command=self._on_sens_change,
        )
        self._sens_slider.set(self._settings.sensitivity)
        self._sens_slider.pack(padx=pad_x, pady=pad_y)

        # ── Smoothing ─────────────────────────────────────────
        self._section_label("SMOOTHING")
        self._smooth_label = ctk.CTkLabel(
            self,
            text=f"{self._settings.smoothing:.2f}",
            font=ctk.CTkFont(size=12),
            text_color="#FFFFFF",
        )
        self._smooth_label.pack()
        self._smooth_slider = ctk.CTkSlider(
            self,
            from_=0.0,
            to=1.0,
            number_of_steps=20,
            width=320,
            height=18,
            button_color="#4A9EFF",
            command=self._on_smooth_change,
        )
        self._smooth_slider.set(self._settings.smoothing)
        self._smooth_slider.pack(padx=pad_x, pady=pad_y)

        # ── Click Hold Frames ─────────────────────────────────
        self._section_label("CLICK HOLD FRAMES")
        self._chf_label = ctk.CTkLabel(
            self,
            text=str(self._settings.click_hold_frames),
            font=ctk.CTkFont(size=12),
            text_color="#FFFFFF",
        )
        self._chf_label.pack()
        self._chf_slider = ctk.CTkSlider(
            self,
            from_=3,
            to=20,
            number_of_steps=17,
            width=320,
            height=18,
            button_color="#4A9EFF",
            command=self._on_chf_change,
        )
        self._chf_slider.set(self._settings.click_hold_frames)
        self._chf_slider.pack(padx=pad_x, pady=pad_y)

        # ── Camera Preview (PiP Overlay) ──────────────────────
        self._section_label("CAMERA PREVIEW")
        self._preview_var = ctk.BooleanVar(value=self._settings.show_camera_preview)
        self._preview_switch = ctk.CTkSwitch(
            self,
            text="Auto-open PiP overlay when tracking starts",
            variable=self._preview_var,
            font=ctk.CTkFont(size=12),
        )
        self._preview_switch.pack(padx=pad_x, pady=(4, 2), anchor="w")
        ctk.CTkLabel(
            self,
            text="Floating window with live hand tracking visualisation",
            font=ctk.CTkFont(size=10),
            text_color="#666666",
        ).pack(padx=pad_x, pady=(0, 6), anchor="w")

        # ── Save button ──────────────────────────────────────
        ctk.CTkButton(
            self,
            text="Save Settings",
            width=380,
            height=42,
            fg_color="#4A9EFF",
            command=self._save,
        ).pack(padx=pad_x, pady=(18, 12))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _section_label(self, text: str) -> None:
        ctk.CTkLabel(
            self,
            text=text,
            font=ctk.CTkFont(size=11),
            text_color="#999999",
            anchor="w",
        ).pack(padx=20, pady=(12, 2), anchor="w")

    def _center_on_screen(self) -> None:
        self.update_idletasks()
        w, h = 420, 580
        sx = (self.winfo_screenwidth() - w) // 2
        sy = (self.winfo_screenheight() - h) // 2
        self.geometry(f"{w}x{h}+{sx}+{sy}")

    # ------------------------------------------------------------------
    # Slider callbacks
    # ------------------------------------------------------------------

    def _on_sens_change(self, value: float) -> None:
        self._sens_label.configure(text=f"{value:.1f}")

    def _on_smooth_change(self, value: float) -> None:
        self._smooth_label.configure(text=f"{value:.2f}")

    def _on_chf_change(self, value: float) -> None:
        self._chf_label.configure(text=str(int(round(value))))

    # ------------------------------------------------------------------
    # Hotkey recording
    # ------------------------------------------------------------------

    def _record_hotkey(self) -> None:
        self._record_btn.configure(text="Listening...", state="disabled")

        def _listen() -> None:
            try:
                combo = keyboard.read_hotkey(suppress=False)
            except Exception:
                combo = self._settings.hotkey
            # Schedule UI update on the main thread
            self.after(0, lambda: self._finish_record(combo))

        threading.Thread(target=_listen, daemon=True).start()

    def _finish_record(self, combo: str) -> None:
        self._hotkey_var.set(combo)
        self._record_btn.configure(text="Record", state="normal")

        # Warn about common system-shortcut conflicts
        dangerous = {"ctrl+c", "ctrl+v", "ctrl+x", "ctrl+z", "alt+f4", "ctrl+alt+delete"}
        if combo.lower() in dangerous:
            logger.warning("Hotkey '%s' may conflict with a system shortcut.", combo)

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    def _save(self) -> None:
        # Resolve camera index from name
        cam_name = self._camera_var.get()
        cam_index = 0
        for c in self._cameras:
            if c["name"] == cam_name:
                cam_index = c["index"]
                break

        new_settings = Settings(
            camera_index=cam_index,
            hotkey=self._hotkey_var.get(),
            smoothing=round(self._smooth_slider.get(), 2),
            sensitivity=round(self._sens_slider.get(), 1),
            click_hold_frames=int(round(self._chf_slider.get())),
            show_camera_preview=self._preview_var.get(),
        )
        SettingsStore.save(new_settings)
        self._on_save(new_settings)
        self._on_close()

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def _on_close(self) -> None:
        global _instance
        _instance = None
        self.destroy()
