"""Camera enumeration and frame capture via OpenCV."""

from __future__ import annotations

import logging
from typing import Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class CameraManager:
    """Enumerate available cameras, open a selected camera, and yield frames."""

    def __init__(self) -> None:
        self._cap: Optional[cv2.VideoCapture] = None

    @staticmethod
    def list_cameras() -> list[dict]:
        """Try indices 0–9, return list of available cameras.

        Returns a list of dicts: [{"index": 0, "name": "Camera 0"}, ...]
        """
        cameras: list[dict] = []
        for i in range(10):
            cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
            if cap.isOpened():
                cameras.append({"index": i, "name": f"Camera {i}"})
                cap.release()
        return cameras

    def open(self, camera_index: int) -> bool:
        """Open the camera at *camera_index*.

        Uses CAP_DSHOW on Windows for fastest init. Sets default 640x480.
        Returns True on success.
        """
        self.release()
        self._cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
        if not self._cap.isOpened():
            logger.error("Failed to open camera index %d", camera_index)
            self._cap = None
            return False
        # Default to 640x480 for optimal MediaPipe performance
        self.set_resolution(640, 480)
        return True

    def read_frame(self) -> Optional[np.ndarray]:
        """Read one frame. Returns BGR numpy array or None on failure."""
        if self._cap is None or not self._cap.isOpened():
            return None
        ret, frame = self._cap.read()
        if not ret:
            return None
        return frame

    def set_resolution(self, width: int, height: int) -> None:
        """Set capture resolution via cv2.CAP_PROP_FRAME_WIDTH/HEIGHT."""
        if self._cap is not None:
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

    def release(self) -> None:
        """Release the camera resource."""
        if self._cap is not None:
            self._cap.release()
            self._cap = None
