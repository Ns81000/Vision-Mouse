"""Load and save user settings as a JSON file in %APPDATA%/VisionMouse/settings.json."""

from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import asdict, dataclass

logger = logging.getLogger(__name__)

CONFIG_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "VisionMouse")
CONFIG_PATH = os.path.join(CONFIG_DIR, "settings.json")


@dataclass
class Settings:
    """Application settings with sensible defaults."""

    camera_index: int = 0
    hotkey: str = "ctrl+shift+v"
    smoothing: float = 0.5          # 0.0 = raw, 1.0 = max smooth
    sensitivity: float = 1.5        # cursor speed multiplier
    click_hold_frames: int = 8      # frames to confirm a click gesture
    show_camera_preview: bool = False


class SettingsStore:
    """Handles persistence of application settings."""

    @staticmethod
    def load() -> Settings:
        """Read JSON settings, filling in defaults for missing keys.

        Never crashes on malformed JSON — falls back to defaults.
        """
        try:
            if os.path.exists(CONFIG_PATH):
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                # Only apply known keys; ignore unknown ones
                defaults = asdict(Settings())
                for key in defaults:
                    if key not in data:
                        data[key] = defaults[key]
                return Settings(**{k: data[k] for k in defaults})
        except (json.JSONDecodeError, TypeError, KeyError, ValueError) as exc:
            logger.warning("Settings file corrupted, falling back to defaults: %s", exc)
        except OSError as exc:
            logger.warning("Could not read settings file: %s", exc)

        # Return defaults and overwrite bad file
        settings = Settings()
        SettingsStore.save(settings)
        return settings

    @staticmethod
    def save(settings: Settings) -> None:
        """Write settings JSON atomically (temp file + os.replace)."""
        os.makedirs(CONFIG_DIR, exist_ok=True)
        data = asdict(settings)
        try:
            fd, tmp_path = tempfile.mkstemp(dir=CONFIG_DIR, suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
                os.replace(tmp_path, CONFIG_PATH)
            except BaseException:
                # Clean up temp file on any failure
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise
        except OSError as exc:
            logger.error("Failed to save settings: %s", exc)
