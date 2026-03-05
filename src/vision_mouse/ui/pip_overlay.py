"""Floating PiP (Picture-in-Picture) camera overlay with hand landmark visualisation.

A borderless, always-on-top, draggable and resizable dark-themed window that
renders the live camera feed with MediaPipe hand landmarks, skeleton
connections, and the currently detected gesture label drawn on top.
"""

from __future__ import annotations

import logging
import threading
import tkinter as tk
from typing import Optional

import cv2
import customtkinter as ctk
import numpy as np
from PIL import Image, ImageTk

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Hand skeleton connections for drawing (MediaPipe 21-landmark topology)
# ---------------------------------------------------------------------------
HAND_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4),        # thumb
    (0, 5), (5, 6), (6, 7), (7, 8),        # index
    (0, 9), (9, 10), (10, 11), (11, 12),   # middle
    (0, 13), (13, 14), (14, 15), (15, 16), # ring
    (0, 17), (17, 18), (18, 19), (19, 20), # pinky
    (5, 9), (9, 13), (13, 17),             # palm
]

# Landmark colours by finger group
_FINGER_COLORS = {
    "thumb":  (74, 158, 255),   # blue  (#4A9EFF)
    "index":  (0, 230, 118),    # green
    "middle": (255, 214, 0),    # yellow
    "ring":   (255, 111, 0),    # orange
    "pinky":  (234, 67, 53),    # red
    "palm":   (140, 140, 140),  # grey
}

def _finger_group(idx: int) -> str:
    if idx <= 4:
        return "thumb"
    if idx <= 8:
        return "index"
    if idx <= 12:
        return "middle"
    if idx <= 16:
        return "ring"
    if idx <= 20:
        return "pinky"
    return "palm"

# Gesture display labels & colours
_GESTURE_DISPLAY = {
    "none":        ("",              (120, 120, 120)),
    "move":        ("MOVING",        (74, 158, 255)),
    "left_click":  ("LEFT CLICK",    (0, 230, 118)),
    "right_click": ("RIGHT CLICK",   (255, 111, 0)),
    "scroll":      ("SCROLL",        (255, 214, 0)),
    "drag":        ("DRAG",          (234, 67, 53)),
}

# ---------------------------------------------------------------------------
# Frame annotation — draws on a BGR OpenCV frame
# ---------------------------------------------------------------------------

def annotate_frame(
    frame: np.ndarray,
    landmarks: list | None = None,
    gesture: str = "none",
) -> np.ndarray:
    """Draw hand skeleton, landmark dots, gesture label and HUD onto *frame*.

    Parameters
    ----------
    frame : BGR numpy array (will be mutated in place).
    landmarks : list of NormalizedLandmark (21 items) or None.
    gesture : one of the Gesture class strings.

    Returns the same frame reference (mutated).
    """
    h, w = frame.shape[:2]

    # Flip horizontally so it mirrors the user (selfie view)
    frame = cv2.flip(frame, 1)

    # ── Dark semi-transparent overlay bar at top ────────────────────
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, 38), (26, 26, 26), -1)
    cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)

    # ── Gesture label (top-left) ────────────────────────────────────
    label, colour = _GESTURE_DISPLAY.get(gesture, ("", (120, 120, 120)))
    if label:
        cv2.putText(
            frame, label, (12, 26),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6, colour, 2, cv2.LINE_AA,
        )

    # ── FPS / status dot (top-right) ───────────────────────────────
    dot_colour = (0, 230, 118) if landmarks else (80, 80, 80)
    cv2.circle(frame, (w - 20, 19), 7, dot_colour, -1, cv2.LINE_AA)

    if landmarks is None:
        # No hand — draw a hint
        cv2.putText(
            frame, "No hand detected", (w // 2 - 90, h // 2),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (100, 100, 100), 1, cv2.LINE_AA,
        )
        return frame

    # ── Convert normalised landmarks to pixel coords ───────────────
    pts = [(int((1.0 - lm.x) * w), int(lm.y * h)) for lm in landmarks]
    # Note: x is flipped again because frame was already flipped above

    # ── Draw skeleton connections ──────────────────────────────────
    for i, j in HAND_CONNECTIONS:
        group = _finger_group(j)
        col = _FINGER_COLORS.get(group, (140, 140, 140))
        cv2.line(frame, pts[i], pts[j], col, 2, cv2.LINE_AA)

    # ── Draw landmark dots ─────────────────────────────────────────
    for idx, (px, py) in enumerate(pts):
        group = _finger_group(idx)
        col = _FINGER_COLORS.get(group, (140, 140, 140))
        # Larger dot for finger tips
        radius = 6 if idx in (4, 8, 12, 16, 20) else 3
        cv2.circle(frame, (px, py), radius, col, -1, cv2.LINE_AA)
        cv2.circle(frame, (px, py), radius, (255, 255, 255), 1, cv2.LINE_AA)

    # ── Index finger crosshair (cursor control point) ─────────────
    ix, iy = pts[8]
    cross_size = 12
    cv2.line(frame, (ix - cross_size, iy), (ix + cross_size, iy),
             (255, 255, 255), 1, cv2.LINE_AA)
    cv2.line(frame, (ix, iy - cross_size), (ix, iy + cross_size),
             (255, 255, 255), 1, cv2.LINE_AA)

    # ── Pinch distance indicator ──────────────────────────────────
    if gesture in ("left_click", "right_click"):
        thumb_pt = pts[4]
        target_pt = pts[8] if gesture == "left_click" else pts[12]
        cv2.line(frame, thumb_pt, target_pt, (0, 230, 118), 2, cv2.LINE_AA)
        mid_x = (thumb_pt[0] + target_pt[0]) // 2
        mid_y = (thumb_pt[1] + target_pt[1]) // 2
        cv2.circle(frame, (mid_x, mid_y), 8, (0, 230, 118), 2, cv2.LINE_AA)

    return frame


# ---------------------------------------------------------------------------
# PiP Overlay Window
# ---------------------------------------------------------------------------

# Default and min/max dimensions
DEFAULT_W, DEFAULT_H = 320, 240
MIN_W, MIN_H = 200, 150
MAX_W, MAX_H = 640, 480
RESIZE_GRIP = 14  # pixels in bottom-right corner that act as resize handle


class PipOverlay(ctk.CTkToplevel):
    """Borderless, draggable, resizable floating camera preview overlay."""

    _instance: Optional["PipOverlay"] = None

    def __init__(self, master: tk.Misc | None = None) -> None:
        # Singleton — only one overlay at a time
        if PipOverlay._instance is not None:
            try:
                if PipOverlay._instance.winfo_exists():
                    PipOverlay._instance.lift()
                    return
            except Exception:
                pass
        PipOverlay._instance = self

        super().__init__(master)

        # ── Window chrome ──────────────────────────────────────
        self.overrideredirect(True)          # borderless
        self.attributes("-topmost", True)    # always on top
        self.configure(fg_color="#1A1A1A")
        self._width = DEFAULT_W
        self._height = DEFAULT_H

        # Position at bottom-right of screen with 20px margin
        scr_w = self.winfo_screenwidth()
        scr_h = self.winfo_screenheight()
        x = scr_w - self._width - 20
        y = scr_h - self._height - 60
        self.geometry(f"{self._width}x{self._height}+{x}+{y}")

        # ── Title bar (thin, dark, draggable) ──────────────────
        self._title_bar = ctk.CTkFrame(
            self, height=28, fg_color="#2A2A2A", corner_radius=0,
        )
        self._title_bar.pack(fill="x", side="top")
        self._title_bar.pack_propagate(False)

        ctk.CTkLabel(
            self._title_bar,
            text="  \U0001F441 Preview",
            font=ctk.CTkFont(size=11),
            text_color="#999999",
            anchor="w",
        ).pack(side="left", padx=4)

        # Size toggle button (S / M / L cycle)
        self._size_idx = 0
        self._sizes = [
            (DEFAULT_W, DEFAULT_H, "S"),
            (440, 330, "M"),
            (MAX_W, MAX_H, "L"),
        ]
        self._size_btn = ctk.CTkButton(
            self._title_bar, text="S", width=24, height=20,
            fg_color="#3A3A3A", hover_color="#4A4A4A",
            text_color="#999999", font=ctk.CTkFont(size=10),
            corner_radius=4, command=self._cycle_size,
        )
        self._size_btn.pack(side="right", padx=(0, 4), pady=4)

        # Close button
        self._close_btn = ctk.CTkButton(
            self._title_bar, text="\u2715", width=24, height=20,
            fg_color="#3A3A3A", hover_color="#C0392B",
            text_color="#999999", font=ctk.CTkFont(size=11),
            corner_radius=4, command=self.close,
        )
        self._close_btn.pack(side="right", padx=(0, 2), pady=4)

        # ── Canvas for video frames ───────────────────────────
        self._canvas = tk.Canvas(
            self, bg="#1A1A1A", highlightthickness=0,
            width=self._width, height=self._height - 28,
        )
        self._canvas.pack(fill="both", expand=True)

        # ── Resize grip (bottom-right corner visual cue) ──────
        self._canvas.bind("<Configure>", self._on_canvas_configure)

        # ── Drag-to-move bindings ─────────────────────────────
        self._drag_x = 0
        self._drag_y = 0
        self._title_bar.bind("<ButtonPress-1>", self._start_drag)
        self._title_bar.bind("<B1-Motion>", self._on_drag)
        for child in self._title_bar.winfo_children():
            # Let labels also be draggable
            child.bind("<ButtonPress-1>", self._start_drag)
            child.bind("<B1-Motion>", self._on_drag)

        # ── Resize bindings (bottom-right corner of canvas) ───
        self._resizing = False
        self._canvas.bind("<ButtonPress-1>", self._maybe_start_resize)
        self._canvas.bind("<B1-Motion>", self._on_resize)
        self._canvas.bind("<ButtonRelease-1>", self._end_resize)
        self._canvas.bind("<Motion>", self._update_resize_cursor)

        # ── Frame state ────────────────────────────────────────
        self._photo: Optional[ImageTk.PhotoImage] = None
        self._closed = False
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update_frame(self, frame_bgr: np.ndarray) -> None:
        """Push a new annotated BGR frame to display. Thread-safe."""
        if self._closed:
            return
        try:
            cw = self._canvas.winfo_width()
            ch = self._canvas.winfo_height()
            if cw < 10 or ch < 10:
                return

            # Resize frame to fit canvas
            frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            frame_resized = cv2.resize(frame_rgb, (cw, ch), interpolation=cv2.INTER_AREA)

            img = Image.fromarray(frame_resized)
            photo = ImageTk.PhotoImage(image=img)

            with self._lock:
                self._photo = photo  # prevent GC

            # Schedule canvas update on Tk main loop
            self._canvas.after(0, self._draw_photo, photo)
        except Exception:
            pass  # Window might be closing

    def close(self) -> None:
        """Gracefully close the overlay."""
        self._closed = True
        PipOverlay._instance = None
        try:
            self.destroy()
        except Exception:
            pass

    @property
    def is_open(self) -> bool:
        if self._closed:
            return False
        try:
            return self.winfo_exists()
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Internals: drawing
    # ------------------------------------------------------------------

    def _draw_photo(self, photo: ImageTk.PhotoImage) -> None:
        try:
            self._canvas.delete("all")
            self._canvas.create_image(0, 0, anchor="nw", image=photo)
            # Draw resize grip indicator (3 small diagonal lines)
            cw = self._canvas.winfo_width()
            ch = self._canvas.winfo_height()
            for i in range(3):
                offset = 4 + i * 4
                self._canvas.create_line(
                    cw - offset, ch,
                    cw, ch - offset,
                    fill="#555555", width=1,
                )
        except Exception:
            pass

    def _on_canvas_configure(self, event) -> None:
        pass  # placeholder for future use

    # ------------------------------------------------------------------
    # Drag-to-move
    # ------------------------------------------------------------------

    def _start_drag(self, event) -> None:
        self._drag_x = event.x_root - self.winfo_x()
        self._drag_y = event.y_root - self.winfo_y()

    def _on_drag(self, event) -> None:
        x = event.x_root - self._drag_x
        y = event.y_root - self._drag_y
        self.geometry(f"+{x}+{y}")

    # ------------------------------------------------------------------
    # Corner resize
    # ------------------------------------------------------------------

    def _in_resize_zone(self, event) -> bool:
        cw = self._canvas.winfo_width()
        ch = self._canvas.winfo_height()
        return event.x >= cw - RESIZE_GRIP and event.y >= ch - RESIZE_GRIP

    def _update_resize_cursor(self, event) -> None:
        if self._in_resize_zone(event):
            self._canvas.configure(cursor="size_nw_se")
        else:
            self._canvas.configure(cursor="")

    def _maybe_start_resize(self, event) -> None:
        if self._in_resize_zone(event):
            self._resizing = True
            self._resize_start_x = event.x_root
            self._resize_start_y = event.y_root
            self._resize_start_w = self.winfo_width()
            self._resize_start_h = self.winfo_height()

    def _on_resize(self, event) -> None:
        if not self._resizing:
            return
        dx = event.x_root - self._resize_start_x
        dy = event.y_root - self._resize_start_y
        new_w = max(MIN_W, min(MAX_W, self._resize_start_w + dx))
        new_h = max(MIN_H, min(MAX_H, self._resize_start_h + dy))
        self._width = new_w
        self._height = new_h
        self.geometry(f"{new_w}x{new_h}")

    def _end_resize(self, event) -> None:
        self._resizing = False

    # ------------------------------------------------------------------
    # Size presets (S / M / L cycle)
    # ------------------------------------------------------------------

    def _cycle_size(self) -> None:
        self._size_idx = (self._size_idx + 1) % len(self._sizes)
        w, h, label = self._sizes[self._size_idx]
        self._width = w
        self._height = h
        self._size_btn.configure(text=label)
        # Keep position, just change size
        x = self.winfo_x()
        y = self.winfo_y()
        self.geometry(f"{w}x{h}+{x}+{y}")
