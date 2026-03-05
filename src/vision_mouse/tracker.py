"""MediaPipe hand tracking + gesture detection using the new Tasks API.

Uses mp.tasks.vision.HandLandmarker (NOT the deprecated mp.solutions.hands).
"""

from __future__ import annotations

import ctypes
import logging
import math
import os
import sys
import threading
from typing import Callable, Optional

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision as mp_vision
from mediapipe.tasks.python.vision import HandLandmarker, HandLandmarkerOptions

from vision_mouse.camera import CameraManager
from vision_mouse.settings_store import Settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Landmark indices (same 0-20 numbering in both old and new APIs)
# ---------------------------------------------------------------------------
WRIST = 0
THUMB_TIP = 4
INDEX_FINGER_TIP = 8
INDEX_FINGER_PIP = 6
MIDDLE_FINGER_TIP = 12
MIDDLE_FINGER_PIP = 10
RING_FINGER_TIP = 16
RING_FINGER_PIP = 14
PINKY_TIP = 20
PINKY_PIP = 18

# Gesture thresholds
PINCH_THRESHOLD = 0.05  # normalized Euclidean distance
CLICK_COOLDOWN_FRAMES = 20
SCROLL_SENSITIVITY = 0.015  # minimum vertical delta to trigger scroll


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_model_path() -> str:
    """Resolve model path whether running as script or bundled .exe."""
    if getattr(sys, "frozen", False):
        # Running as PyInstaller / Nuitka bundle
        base = sys._MEIPASS  # type: ignore[attr-defined]
    else:
        # Running from source — go up to project root
        base = os.path.dirname(os.path.abspath(__file__))
        base = os.path.normpath(os.path.join(base, "..", ".."))
    return os.path.join(base, "assets", "models", "hand_landmarker.task")


def get_screen_size() -> tuple[int, int]:
    """Return (width, height) of the primary monitor via Win32 API."""
    user32 = ctypes.windll.user32  # type: ignore[attr-defined]
    return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)


def map_to_screen(
    norm_x: float, norm_y: float, sensitivity: float
) -> tuple[int, int]:
    """Convert normalised MediaPipe coords to screen pixels."""
    screen_w, screen_h = get_screen_size()

    # Flip X because the camera mirrors the user
    norm_x = 1.0 - norm_x

    # Apply sensitivity (scale around center)
    cx, cy = 0.5, 0.5
    norm_x = cx + (norm_x - cx) * sensitivity
    norm_y = cy + (norm_y - cy) * sensitivity

    # Clamp to valid range
    norm_x = max(0.0, min(1.0, norm_x))
    norm_y = max(0.0, min(1.0, norm_y))

    # Clamp away from extreme edges (edge-jitter mitigation)
    screen_x = int(norm_x * screen_w)
    screen_y = int(norm_y * screen_h)
    screen_x = max(10, min(screen_w - 10, screen_x))
    screen_y = max(10, min(screen_h - 10, screen_y))
    return screen_x, screen_y


def _euclidean(lm1, lm2) -> float:
    """Euclidean distance between two NormalizedLandmark objects."""
    return math.sqrt((lm1.x - lm2.x) ** 2 + (lm1.y - lm2.y) ** 2)


def _finger_extended(landmarks, tip_idx: int, pip_idx: int) -> bool:
    """Return True when a finger tip is above (lower Y) its PIP joint."""
    return landmarks[tip_idx].y < landmarks[pip_idx].y


# ---------------------------------------------------------------------------
# EMA Smoothing with velocity-aware dynamic alpha
# ---------------------------------------------------------------------------

class EMAFilter:
    """Exponential Moving Average with velocity-aware smoothing."""

    def __init__(self, alpha: float = 0.5) -> None:
        # alpha: 0.0 = maximum smoothing, 1.0 = no smoothing (raw)
        self.alpha = alpha
        self._prev_x: Optional[float] = None
        self._prev_y: Optional[float] = None

    def smooth(self, x: float, y: float) -> tuple[float, float]:
        if self._prev_x is None:
            self._prev_x, self._prev_y = x, y
            return x, y

        # Velocity-aware: fast movement → less smoothing
        delta = abs(x - self._prev_x) + abs(y - self._prev_y)
        dynamic_alpha = min(1.0, self.alpha + delta * 5)

        smooth_x = dynamic_alpha * x + (1 - dynamic_alpha) * self._prev_x
        smooth_y = dynamic_alpha * y + (1 - dynamic_alpha) * self._prev_y
        self._prev_x, self._prev_y = smooth_x, smooth_y
        return smooth_x, smooth_y

    def reset(self) -> None:
        self._prev_x = None
        self._prev_y = None

    def update_alpha(self, smoothing_setting: float) -> None:
        """Convert user-facing smoothing (0=raw,1=max) to EMA alpha."""
        self.alpha = 1.0 - smoothing_setting


# ---------------------------------------------------------------------------
# Gesture enum
# ---------------------------------------------------------------------------

class Gesture:
    NONE = "none"
    MOVE = "move"
    LEFT_CLICK = "left_click"
    RIGHT_CLICK = "right_click"
    SCROLL = "scroll"
    DRAG = "drag"


# ---------------------------------------------------------------------------
# HandTracker
# ---------------------------------------------------------------------------

class HandTracker:
    """Run MediaPipe Hand Landmarker, detect gestures, and emit cursor commands."""

    def __init__(
        self,
        on_move: Callable[[int, int], None],
        on_click: Callable[[str], None],
        settings: Settings,
        on_frame: Optional[Callable[["np.ndarray", list | None, str], None]] = None,
    ) -> None:
        self.on_move = on_move
        self.on_click = on_click
        self.on_frame = on_frame  # callback(frame_bgr, landmarks, gesture)
        self.settings = settings
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._ema = EMAFilter(alpha=1.0 - settings.smoothing)
        self._current_gesture: str = Gesture.NONE

        # Gesture state
        self._left_pinch_frames = 0
        self._right_pinch_frames = 0
        self._click_cooldown = 0
        self._prev_index_y: Optional[float] = None
        self._dragging = False

        # Initialise MediaPipe HandLandmarker
        model_path = _get_model_path()
        if not os.path.isfile(model_path):
            logger.error(
                "hand_landmarker.task not found at %s — tracking disabled.",
                model_path,
            )
            self._landmarker: Optional[HandLandmarker] = None
            return

        options = HandLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=model_path),
            running_mode=mp_vision.RunningMode.VIDEO,
            num_hands=1,
            min_hand_detection_confidence=0.7,
            min_hand_presence_confidence=0.6,
            min_tracking_confidence=0.6,
        )
        self._landmarker = HandLandmarker.create_from_options(options)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self, camera_index: int) -> None:
        """Start tracking loop in a daemon thread."""
        if self._landmarker is None:
            logger.error("Cannot start tracking — HandLandmarker not initialised.")
            return
        self._stop_event.clear()
        self.camera_index = camera_index
        self._thread = threading.Thread(
            target=self._tracking_loop, daemon=True, name="HandTracker"
        )
        self._thread.start()

    def stop(self) -> None:
        """Set stop event and join the tracking thread."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None
        # Release drag if active
        if self._dragging:
            self.on_click("up")
            self._dragging = False

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    # ------------------------------------------------------------------
    # Tracking loop
    # ------------------------------------------------------------------

    def _tracking_loop(self) -> None:
        cam = CameraManager()
        if not cam.open(self.camera_index):
            logger.error("Camera %d failed to open.", self.camera_index)
            return

        frame_timestamp_ms = 0

        try:
            while not self._stop_event.is_set():
                frame = cam.read_frame()
                if frame is None:
                    continue

                # Optional low-light enhancement
                frame_processed = cv2.convertScaleAbs(frame, alpha=1.3, beta=20)
                frame_rgb = cv2.cvtColor(frame_processed, cv2.COLOR_BGR2RGB)

                mp_image = mp.Image(
                    image_format=mp.ImageFormat.SRGB, data=frame_rgb
                )

                # Monotonically increasing timestamp (~30 FPS)
                frame_timestamp_ms += 33
                result = self._landmarker.detect_for_video(
                    mp_image, frame_timestamp_ms
                )

                landmarks = None
                if result.hand_landmarks:
                    landmarks = result.hand_landmarks[0]
                    self._process_landmarks(landmarks)

                # Push annotated frame to PiP overlay if callback set
                if self.on_frame is not None:
                    try:
                        self.on_frame(
                            frame_processed, landmarks, self._current_gesture
                        )
                    except Exception:
                        pass  # overlay may have closed
        except Exception:
            logger.exception("Error in tracking loop")
        finally:
            cam.release()

    # ------------------------------------------------------------------
    # Gesture processing
    # ------------------------------------------------------------------

    def _process_landmarks(self, landmarks) -> None:
        """Run gesture detection and emit appropriate callbacks."""
        gesture = self._detect_gesture(landmarks)
        self._current_gesture = gesture

        # Cooldown management
        if self._click_cooldown > 0:
            self._click_cooldown -= 1

        if gesture == Gesture.MOVE:
            tip = landmarks[INDEX_FINGER_TIP]
            sx, sy = self._ema.smooth(tip.x, tip.y)
            screen_x, screen_y = map_to_screen(
                sx, sy, self.settings.sensitivity
            )
            self.on_move(screen_x, screen_y)

        elif gesture == Gesture.LEFT_CLICK:
            self._left_pinch_frames += 1
            if (
                self._left_pinch_frames >= self.settings.click_hold_frames
                and self._click_cooldown == 0
            ):
                self.on_click("left")
                self._left_pinch_frames = 0
                self._click_cooldown = CLICK_COOLDOWN_FRAMES
        elif gesture != Gesture.LEFT_CLICK:
            self._left_pinch_frames = 0

        if gesture == Gesture.RIGHT_CLICK:
            self._right_pinch_frames += 1
            if (
                self._right_pinch_frames >= self.settings.click_hold_frames
                and self._click_cooldown == 0
            ):
                self.on_click("right")
                self._right_pinch_frames = 0
                self._click_cooldown = CLICK_COOLDOWN_FRAMES
        elif gesture != Gesture.RIGHT_CLICK:
            self._right_pinch_frames = 0

        if gesture == Gesture.SCROLL:
            tip = landmarks[INDEX_FINGER_TIP]
            if self._prev_index_y is not None:
                delta_y = self._prev_index_y - tip.y
                if abs(delta_y) > SCROLL_SENSITIVITY:
                    direction = 1 if delta_y > 0 else -1
                    self.on_click(f"scroll_{direction}")
            self._prev_index_y = tip.y
        else:
            self._prev_index_y = None

        if gesture == Gesture.DRAG:
            tip = landmarks[INDEX_FINGER_TIP]
            sx, sy = self._ema.smooth(tip.x, tip.y)
            screen_x, screen_y = map_to_screen(
                sx, sy, self.settings.sensitivity
            )
            self.on_move(screen_x, screen_y)
            if not self._dragging:
                self.on_click("down")
                self._dragging = True
        elif self._dragging:
            self.on_click("up")
            self._dragging = False

    def _detect_gesture(self, landmarks) -> str:
        """Determine current gesture from landmark positions."""
        thumb_tip = landmarks[THUMB_TIP]
        index_tip = landmarks[INDEX_FINGER_TIP]
        middle_tip = landmarks[MIDDLE_FINGER_TIP]

        # --- Pinch detection ---
        left_pinch_dist = _euclidean(thumb_tip, index_tip)
        right_pinch_dist = _euclidean(thumb_tip, middle_tip)

        if left_pinch_dist < PINCH_THRESHOLD:
            return Gesture.LEFT_CLICK
        if right_pinch_dist < PINCH_THRESHOLD:
            return Gesture.RIGHT_CLICK

        # --- Finger extension checks ---
        index_extended = _finger_extended(landmarks, INDEX_FINGER_TIP, INDEX_FINGER_PIP)
        middle_extended = _finger_extended(landmarks, MIDDLE_FINGER_TIP, MIDDLE_FINGER_PIP)
        ring_extended = _finger_extended(landmarks, RING_FINGER_TIP, RING_FINGER_PIP)
        pinky_extended = _finger_extended(landmarks, PINKY_TIP, PINKY_PIP)

        # --- Scroll: index + middle up, ring + pinky closed ---
        if index_extended and middle_extended and not ring_extended and not pinky_extended:
            return Gesture.SCROLL

        # --- Drag: closed fist (all fingertips below PIP) ---
        if not index_extended and not middle_extended and not ring_extended and not pinky_extended:
            return Gesture.DRAG

        # --- Move: index finger extended ---
        if index_extended:
            return Gesture.MOVE

        return Gesture.NONE
