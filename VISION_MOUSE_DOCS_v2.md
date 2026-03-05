# 👁️ Vision Mouse — Developer Documentation

> Complete build guide for GitHub Copilot. Follow this document top to bottom to build the full Vision Mouse application.
>
> **Documentation version: 2.0** | Target Python: 3.11+ | Target OS: Windows 10/11
>
> ⚠️ **What changed from v1.0:** MediaPipe migrated to the new Tasks API (`mp.tasks.vision.HandLandmarker`). The legacy `mp.solutions.hands` API is officially deprecated and unmaintained. Version pins updated. Packaging section expanded with `cx_Freeze` and `Nuitka` alternatives.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Tech Stack](#2-tech-stack)
3. [Project Structure](#3-project-structure)
4. [Setup & Tooling (uv)](#4-setup--tooling-uv)
5. [Dependencies](#5-dependencies)
6. [Module Breakdown](#6-module-breakdown)
   - [main.py](#61-mainpy)
   - [hotkey.py](#62-hotkeypy)
   - [camera.py](#63-camerapy)
   - [tracker.py](#64-trackerpy)
   - [mouse_controller.py](#65-mouse_controllerpy)
   - [settings_store.py](#66-settings_storepy)
   - [ui/settings_window.py](#67-uisettings_windowpy)
   - [ui/tray.py](#68-uitraypy)
7. [Core Logic Deep Dive](#7-core-logic-deep-dive)
   - [Hand Landmark Map](#71-hand-landmark-map)
   - [Gesture Definitions](#72-gesture-definitions)
   - [Coordinate Mapping](#73-coordinate-mapping)
   - [Smoothing Algorithm](#74-smoothing-algorithm)
8. [Settings Schema](#8-settings-schema)
9. [UI Design Spec](#9-ui-design-spec)
10. [Hotkey System](#10-hotkey-system)
11. [Packaging](#11-packaging)
12. [Error Handling Rules](#12-error-handling-rules)
13. [Performance Constraints](#13-performance-constraints)
14. [Known Edge Cases](#14-known-edge-cases)

---

## 1. Project Overview

**Vision Mouse** is a fully offline, real-time hand gesture mouse controller for Windows. The user activates it via a global hotkey. Their laptop or USB webcam then tracks their hand using MediaPipe, and the OS mouse cursor moves and clicks based on finger gestures — no physical mouse required.

### Core Requirements

| Requirement | Detail |
|---|---|
| **Offline** | Zero network calls. All ML models bundled locally. |
| **Any Windows machine** | Ships as a single `.exe` via PyInstaller (or `cx_Freeze` / Nuitka — see Section 11) |
| **Any camera** | User selects camera index in settings |
| **Hotkey toggle** | Single key combo activates/deactivates tracking |
| **Low latency** | Target ≤ 30ms end-to-end (camera → cursor move) |
| **Memory efficient** | Target < 250MB RAM during active tracking |
| **No multi-monitor** | Single primary display only. No coordinate remapping. |

---

## 2. Tech Stack

| Purpose | Library | Version | Why |
|---|---|---|---|
| Hand tracking | `mediapipe` | `>=0.10.32` | 21-landmark hand model, CPU-only, ~8MB model. **Use new Tasks API — legacy `mp.solutions` is deprecated.** |
| Camera capture | `opencv-python` | `>=4.10.0` | Universal camera access, fast frame decode |
| Mouse control | `pynput` | `>=1.7.6` | Cross-platform, no admin rights needed |
| Global hotkey | `keyboard` | `>=0.13.5` | System-wide key listener, works in background |
| Settings UI | `customtkinter` | `>=5.2.2` | Modern minimal dark UI built on top of Tkinter |
| System tray | `pystray` | `>=0.19.5` | Tray icon with right-click menu |
| Settings storage | `json` (stdlib) | — | No DB needed, flat JSON file |
| Packaging | `PyInstaller` | `>=6.0.0` | Single `.exe`, bundles everything. See Section 11 for faster alternatives. |
| Package manager | `uv` | latest | Fast, modern Python package manager |
| Tray icon image | `Pillow` | `>=10.4.0` | Required by pystray for icon rendering |

### ⚠️ MediaPipe API Migration Notice

The old `mp.solutions.hands` API is **officially deprecated** by Google as of 2023 and receives no further updates or bug fixes. All code in this document uses the **new Tasks API** (`mp.tasks.vision.HandLandmarker`). Key differences:

| Legacy API (❌ Do NOT use) | New Tasks API (✅ Use this) |
|---|---|
| `mp.solutions.hands.Hands()` | `mp.tasks.vision.HandLandmarker.create_from_options()` |
| `results.multi_hand_landmarks` | `result.hand_landmarks` |
| Inline landmark objects | `NormalizedLandmark` objects from `mediapipe.tasks.components.containers` |
| Model loaded internally | Explicit `.task` model file path required |
| No GPU option | Optional GPU delegate available |

You must download the hand landmarker model file and bundle it with the app:
- **Download:** `hand_landmarker.task` from the [MediaPipe Models page](https://developers.google.com/mediapipe/solutions/vision/hand_landmarker#models)
- **Bundle path:** `assets/models/hand_landmarker.task`
- **PyInstaller:** Include via `--add-data "assets;assets"` (already in `build.bat`)

---

## 3. Project Structure

```
vision-mouse/
├── pyproject.toml                   # uv project config + dependencies
├── README.md
├── VISION_MOUSE_DOCS.md             # This file
├── build.bat                        # One-click PyInstaller build script
├── assets/
│   ├── icon.ico                     # App icon (used for tray + exe)
│   └── models/
│       └── hand_landmarker.task     # ⚠️ NEW: Required MediaPipe Tasks model file
├── src/
│   └── vision_mouse/
│       ├── __init__.py
│       ├── main.py                  # Entry point
│       ├── hotkey.py                # Global hotkey registration + toggle logic
│       ├── camera.py                # Camera enumeration + frame capture
│       ├── tracker.py               # MediaPipe hand tracking + gesture detection
│       ├── mouse_controller.py      # Cursor movement + click simulation
│       ├── settings_store.py        # Load/save settings to JSON
│       └── ui/
│           ├── __init__.py
│           ├── settings_window.py   # CustomTkinter settings panel
│           └── tray.py              # System tray icon + menu
```

---

## 4. Setup & Tooling (uv)

### Initialize the project

```bash
uv init vision-mouse
cd vision-mouse
uv venv
```

### Install dependencies

```bash
uv add mediapipe opencv-python pynput keyboard customtkinter pystray Pillow pyinstaller
```

### Download the MediaPipe model

```bash
# Create the models directory and download the hand landmarker model
mkdir -p assets/models
curl -o assets/models/hand_landmarker.task \
  https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task
```

> Alternatively, download manually from the MediaPipe Models page and place it at `assets/models/hand_landmarker.task`.

### Run the app

```bash
uv run src/vision_mouse/main.py
```

### Build the exe

```bash
build.bat
```

---

## 5. Dependencies

### `pyproject.toml`

```toml
[project]
name = "vision-mouse"
version = "1.0.0"
description = "Offline hand gesture mouse controller for Windows"
requires-python = ">=3.11"

dependencies = [
    "mediapipe>=0.10.32",
    "opencv-python>=4.10.0",
    "pynput>=1.7.6",
    "keyboard>=0.13.5",
    "customtkinter>=5.2.2",
    "pystray>=0.19.5",
    "Pillow>=10.4.0",
    "pyinstaller>=6.0.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/vision_mouse"]
```

---

## 6. Module Breakdown

### 6.1 `main.py`

**Responsibility:** Application entry point. Boots all components, starts the tray icon, and keeps the process alive.

**Logic:**
1. Enforce single instance via Windows mutex (see Section 14)
2. Load settings from `settings_store.py`
3. Initialize `HotkeyManager` with the saved hotkey
4. Initialize `SystemTray`
5. Call `tray.run()` — this blocks the main thread (required by pystray)
6. The tracking loop runs in a separate daemon thread when toggled ON

```python
# Pseudocode outline for Copilot:

def main():
    # Enforce single instance
    import ctypes
    mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "VisionMouseSingleInstance")
    if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        sys.exit(0)

    settings = SettingsStore.load()
    tray = SystemTray(settings)
    hotkey_manager = HotkeyManager(
        hotkey=settings.hotkey,
        on_toggle=tray.toggle_tracking
    )
    hotkey_manager.start()
    tray.run()  # blocks

if __name__ == "__main__":
    main()
```

**Important:** Never call `tray.run()` from a non-main thread. pystray requires it on the main thread on Windows.

---

### 6.2 `hotkey.py`

**Responsibility:** Register and listen for a global hotkey that toggles tracking on/off.

**Class:** `HotkeyManager`

**Methods:**
- `__init__(self, hotkey: str, on_toggle: Callable)` — stores hotkey string and callback
- `start(self)` — registers the hotkey using `keyboard.add_hotkey()`
- `stop(self)` — unregisters with `keyboard.remove_hotkey()`
- `update_hotkey(self, new_hotkey: str)` — unregisters old, registers new

**Hotkey format:** Standard `keyboard` library format strings, e.g. `"ctrl+shift+f"`, `"alt+v"`, `"f9"`

**Implementation notes:**
- Use `keyboard.add_hotkey(hotkey, callback, suppress=False)`
- The callback must be thread-safe — it will fire from the keyboard listener thread
- `on_toggle` should flip a shared `threading.Event` or boolean flag

```python
# Pseudocode:
class HotkeyManager:
    def start(self):
        keyboard.add_hotkey(self.hotkey, self.on_toggle)

    def update_hotkey(self, new_hotkey):
        keyboard.remove_hotkey(self.hotkey)
        self.hotkey = new_hotkey
        keyboard.add_hotkey(self.hotkey, self.on_toggle)
```

---

### 6.3 `camera.py`

**Responsibility:** Enumerate available cameras, open selected camera, and yield frames.

**Class:** `CameraManager`

**Methods:**
- `list_cameras() -> list[dict]` — static method, returns `[{"index": 0, "name": "Camera 0"}, ...]`
- `open(camera_index: int)` — opens the camera with OpenCV
- `read_frame() -> np.ndarray | None` — reads one frame, returns BGR numpy array or None on failure
- `release()` — releases the camera resource
- `set_resolution(width: int, height: int)` — sets capture resolution via `cv2.CAP_PROP_FRAME_WIDTH/HEIGHT`

**Camera enumeration logic:**
```python
# Try indices 0–9, check if cap.isOpened(), collect valid ones
def list_cameras() -> list[dict]:
    cameras = []
    for i in range(10):
        cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)  # CAP_DSHOW for Windows
        if cap.isOpened():
            cameras.append({"index": i, "name": f"Camera {i}"})
            cap.release()
    return cameras
```

**Important:** Always use `cv2.CAP_DSHOW` backend on Windows for fastest initialization and best compatibility.

**Resolution:** Default to `640x480`. This is the optimal balance of speed vs. tracking accuracy for MediaPipe.

---

### 6.4 `tracker.py`

**Responsibility:** Run MediaPipe Hand Landmarker on camera frames, extract landmarks, detect gestures, and emit cursor commands.

**Class:** `HandTracker`

**Constructor params:**
- `on_move: Callable[[int, int], None]` — callback with absolute screen (x, y)
- `on_click: Callable[[str], None]` — callback with `"left"`, `"right"`, `"down"`, `"up"`
- `settings: Settings`

**Methods:**
- `start(camera_index: int)` — starts tracking loop in a daemon thread
- `stop()` — sets stop event, joins thread
- `_tracking_loop()` — main loop: read frame → process → detect gesture → emit

**⚠️ Updated MediaPipe Tasks API setup:**

```python
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision as mp_vision
from mediapipe.tasks.python.vision import HandLandmarkerOptions, HandLandmarker
from mediapipe.tasks.python.vision.core.vision_task_running_mode import VisionTaskRunningMode
import sys, os

def _get_model_path() -> str:
    """Resolve model path whether running as script or bundled .exe."""
    if getattr(sys, 'frozen', False):
        # Running as PyInstaller bundle
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.abspath(__file__))
        base = os.path.join(base, '..', '..', '..')  # up to project root
    return os.path.join(base, 'assets', 'models', 'hand_landmarker.task')


class HandTracker:
    def __init__(self, on_move, on_click, settings):
        self.on_move = on_move
        self.on_click = on_click
        self.settings = settings
        self._stop_event = threading.Event()
        self._ema = EMAFilter(alpha=1.0 - settings.smoothing)

        model_path = _get_model_path()
        options = HandLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=model_path),
            running_mode=VisionTaskRunningMode.VIDEO,   # VIDEO mode for live streams
            num_hands=1,                                 # Track only one hand for performance
            min_hand_detection_confidence=0.7,
            min_hand_presence_confidence=0.6,
            min_tracking_confidence=0.6,
        )
        self._landmarker = HandLandmarker.create_from_options(options)
```

**Tracking loop structure (Tasks API):**

```python
def _tracking_loop(self):
    cam = CameraManager()
    cam.open(self.camera_index)
    frame_timestamp_ms = 0

    while not self._stop_event.is_set():
        frame = cam.read_frame()
        if frame is None:
            continue

        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Wrap frame in MediaPipe Image
        mp_image = mp.Image(
            image_format=mp.ImageFormat.SRGB,
            data=frame_rgb
        )

        # Tasks API requires a monotonically increasing timestamp in milliseconds
        frame_timestamp_ms += 33  # ~30 FPS
        result = self._landmarker.detect_for_video(mp_image, frame_timestamp_ms)

        if result.hand_landmarks:
            landmarks = result.hand_landmarks[0]  # First hand
            self._process_landmarks(landmarks, frame.shape)

    cam.release()
    self._landmarker.close()
```

**Accessing landmark coordinates (Tasks API):**

```python
# Tasks API landmarks are NormalizedLandmark objects (same .x, .y, .z as before)
# Index constants are the same 0-20 numbering

INDEX_TIP  = 8
INDEX_PIP  = 6
THUMB_TIP  = 4
MIDDLE_TIP = 12

tip = landmarks[INDEX_TIP]
x, y = tip.x, tip.y   # normalized 0.0–1.0
```

---

### 6.5 `mouse_controller.py`

**Responsibility:** Translate (x, y) coordinates and gesture signals into actual OS mouse events.

**Class:** `MouseController`

**Uses:** `pynput.mouse.Controller`

**Methods:**
- `move_to(x: int, y: int)` — moves cursor to absolute screen position
- `click(button: str)` — `"left"` or `"right"` single click
- `press(button: str)` — mouse button down (for drag)
- `release(button: str)` — mouse button up
- `scroll(direction: int)` — scroll up (+1) or down (-1)

**Implementation:**
```python
from pynput.mouse import Button, Controller

class MouseController:
    def __init__(self):
        self._mouse = Controller()

    def move_to(self, x: int, y: int):
        self._mouse.position = (x, y)

    def click(self, button: str):
        btn = Button.left if button == "left" else Button.right
        self._mouse.click(btn)

    def press(self, button: str):
        btn = Button.left if button == "left" else Button.right
        self._mouse.press(btn)

    def release(self, button: str):
        btn = Button.left if button == "left" else Button.right
        self._mouse.release(btn)

    def scroll(self, direction: int):
        self._mouse.scroll(0, direction * 3)
```

---

### 6.6 `settings_store.py`

**Responsibility:** Load and save user settings as a JSON file in `%APPDATA%/VisionMouse/settings.json`.

**Class:** `SettingsStore`

**Methods:**
- `load() -> Settings` — reads JSON, fills in defaults for missing keys
- `save(settings: Settings)` — writes JSON atomically

**Settings dataclass:**
```python
from dataclasses import dataclass, field

@dataclass
class Settings:
    camera_index: int = 0
    hotkey: str = "ctrl+shift+v"
    smoothing: float = 0.5          # 0.0 = raw, 1.0 = max smooth
    sensitivity: float = 1.5        # cursor speed multiplier
    click_hold_frames: int = 8      # frames to confirm a click gesture
    show_camera_preview: bool = False
```

**Storage path:**
```python
import os
CONFIG_PATH = os.path.join(os.environ["APPDATA"], "VisionMouse", "settings.json")
```

**Atomic save:** Write to a temp file then `os.replace()` to avoid corruption.

---

### 6.7 `ui/settings_window.py`

**Responsibility:** A minimal, modern settings panel built with CustomTkinter. Opens when user clicks "Settings" in tray menu.

**Class:** `SettingsWindow(ctk.CTkToplevel)`

**UI Sections (top to bottom):**

1. **Header** — App name + version, minimal, centered
2. **Camera** — Dropdown to select camera index (populated from `CameraManager.list_cameras()`)
3. **Hotkey** — Text input + "Record" button (user presses key combo, it captures it)
4. **Sensitivity** — Slider (0.5 → 3.0, step 0.1)
5. **Smoothing** — Slider (0.0 → 1.0, step 0.05)
6. **Click Hold Frames** — Slider (3 → 20, integer steps) — how many frames a pinch must hold to register as a click
7. **Camera Preview** — Toggle switch (on/off)
8. **Save button** — Saves and closes window

**Design rules (see Section 9 for full spec):**
- Dark mode only (`ctk.set_appearance_mode("dark")`)
- No borders, flat design
- Consistent padding: 20px horizontal, 12px vertical between sections
- Only one window instance at a time (check `self._instance` before opening)

**Hotkey recording logic:**
```python
# When user clicks "Record Hotkey":
# 1. Change button label to "Press keys..."
# 2. Listen for next key combo via keyboard.read_hotkey(suppress=False) in a daemon thread
# 3. Display the captured hotkey string in the input field
# 4. Restore button label to "Record"
```

---

### 6.8 `ui/tray.py`

**Responsibility:** System tray icon with right-click menu.

**Class:** `SystemTray`

**Tray menu items:**
```
✅ Vision Mouse Active   ← status indicator (greyed out, not clickable)
─────────────────────
▶ Enable / ⏹ Disable   ← toggles tracking (label changes based on state)
⚙ Settings              ← opens SettingsWindow
─────────────────────
✕ Quit                  ← exits app cleanly
```

**Implementation notes:**
- Use `pystray.Icon` with a `pystray.Menu`
- Icon image: load `assets/icon.ico` with Pillow → pass to `pystray.Icon`
- `toggle_tracking()`: starts or stops `HandTracker` thread, updates menu item label
- `open_settings()`: instantiates `SettingsWindow` if not already open
- `quit()`: calls `tracker.stop()`, `hotkey_manager.stop()`, `icon.stop()`

---

## 7. Core Logic Deep Dive

### 7.1 Hand Landmark Map

MediaPipe returns 21 landmarks (index 0–20). Key ones used:

```
WRIST               = 0
THUMB_TIP           = 4
INDEX_FINGER_TIP    = 8
INDEX_FINGER_PIP    = 6   (middle joint, used for gesture logic)
MIDDLE_FINGER_TIP   = 12
RING_FINGER_TIP     = 16
PINKY_TIP           = 20
```

Each landmark has `.x`, `.y` (normalized 0.0–1.0 relative to frame size) and `.z` (depth, not used).

> **Note:** The landmark indices are identical in both the old and new MediaPipe APIs. Only the way you access the result object changes (see Section 6.4).

---

### 7.2 Gesture Definitions

All gestures are detected in `tracker.py` → `_detect_gesture(landmarks)` method.

#### Cursor Movement
- **Trigger:** Index finger is extended upward (tip Y < PIP Y)
- **Control point:** `INDEX_FINGER_TIP` (landmark 8)
- **Action:** Map tip position to screen coordinates → call `mouse_controller.move_to(x, y)`
- **Active when:** No click gesture is happening

#### Left Click
- **Trigger:** Pinch — `THUMB_TIP` and `INDEX_FINGER_TIP` distance < threshold
- **Threshold:** Euclidean distance < `0.05` (normalized units)
- **Confirmation:** Must hold for `settings.click_hold_frames` consecutive frames
- **Action:** `mouse_controller.click("left")`
- **Cooldown:** 20 frames after click before next click can register

#### Right Click
- **Trigger:** Pinch — `THUMB_TIP` and `MIDDLE_FINGER_TIP` distance < threshold
- **Threshold:** Same as left click (`0.05`)
- **Confirmation:** Same frame hold requirement
- **Action:** `mouse_controller.click("right")`

#### Scroll
- **Trigger:** Index + Middle fingers both extended, ring + pinky closed
- **Control:** Track vertical movement delta of index tip between frames
- **Action:** `mouse_controller.scroll(direction)` — positive = up, negative = down

#### Drag (optional, implement last)
- **Trigger:** Closed fist — all fingertips below their PIP joints
- **Action:** `mouse_controller.press("left")` while moving, `mouse_controller.release("left")` when fist opens

---

### 7.3 Coordinate Mapping

Convert normalized MediaPipe coordinates (0.0–1.0) to screen pixels.

```python
import ctypes

def get_screen_size() -> tuple[int, int]:
    user32 = ctypes.windll.user32
    return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)  # width, height

def map_to_screen(norm_x: float, norm_y: float, sensitivity: float) -> tuple[int, int]:
    screen_w, screen_h = get_screen_size()

    # Flip X because camera mirrors the user
    norm_x = 1.0 - norm_x

    # Apply sensitivity (scale around center)
    center_x, center_y = 0.5, 0.5
    norm_x = center_x + (norm_x - center_x) * sensitivity
    norm_y = center_y + (norm_y - center_y) * sensitivity

    # Clamp to valid range
    norm_x = max(0.0, min(1.0, norm_x))
    norm_y = max(0.0, min(1.0, norm_y))

    screen_x = int(norm_x * screen_w)
    screen_y = int(norm_y * screen_h)
    return screen_x, screen_y
```

**Note:** Always use `ctypes.windll.user32.GetSystemMetrics` instead of `pyautogui.size()` — it's faster and has no dependencies.

---

### 7.4 Smoothing Algorithm

Raw landmark positions are jittery. Apply **exponential moving average (EMA)** to smooth cursor movement.

```python
class EMAFilter:
    def __init__(self, alpha: float = 0.5):
        # alpha: 0.0 = maximum smoothing, 1.0 = no smoothing (raw)
        self.alpha = alpha
        self._prev_x: float | None = None
        self._prev_y: float | None = None

    def smooth(self, x: float, y: float) -> tuple[float, float]:
        if self._prev_x is None:
            self._prev_x, self._prev_y = x, y
            return x, y
        smooth_x = self.alpha * x + (1 - self.alpha) * self._prev_x
        smooth_y = self.alpha * y + (1 - self.alpha) * self._prev_y
        self._prev_x, self._prev_y = smooth_x, smooth_y
        return smooth_x, smooth_y

    def update_alpha(self, smoothing_setting: float):
        # settings.smoothing is 0.0 (most smooth) → 1.0 (raw)
        # EMA alpha is the inverse relationship
        self.alpha = 1.0 - smoothing_setting
```

Instantiate one `EMAFilter` in `HandTracker`, apply it to index finger tip coordinates every frame before mapping to screen.

---

## 8. Settings Schema

**File location:** `%APPDATA%/VisionMouse/settings.json`

```json
{
  "camera_index": 0,
  "hotkey": "ctrl+shift+v",
  "smoothing": 0.5,
  "sensitivity": 1.5,
  "click_hold_frames": 8,
  "show_camera_preview": false
}
```

**Defaults** are always applied for any missing key (forward compatibility). Never crash on malformed JSON — catch `json.JSONDecodeError` and fall back to defaults.

---

## 9. UI Design Spec

### Theme
- **Mode:** Dark only
- **Primary accent:** `#4A9EFF` (blue)
- **Background:** `#1A1A1A`
- **Surface:** `#2A2A2A`
- **Text primary:** `#FFFFFF`
- **Text secondary:** `#999999`
- **Font:** System default (CustomTkinter default sans-serif)

### Window
- **Size:** `420 x 580` px, fixed (non-resizable)
- **Title:** `Vision Mouse — Settings`
- **Centered** on screen on open
- **Always on top:** Yes

### Component styling
```python
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# Window
window = ctk.CTkToplevel()
window.geometry("420x580")
window.resizable(False, False)
window.title("Vision Mouse — Settings")

# Section labels (e.g. "CAMERA", "HOTKEY")
ctk.CTkLabel(text="CAMERA", font=("", 11), text_color="#999999")

# Dropdown
ctk.CTkComboBox(width=380, height=36)

# Sliders
ctk.CTkSlider(width=320, height=18, button_color="#4A9EFF")

# Toggle
ctk.CTkSwitch(text="Show Camera Preview")

# Save button
ctk.CTkButton(text="Save Settings", width=380, height=42, fg_color="#4A9EFF")
```

---

## 10. Hotkey System

The default hotkey is `ctrl+shift+v`. User can change it in settings.

**Hotkey capture flow in UI:**
1. User clicks "Record" button next to hotkey field
2. Button text changes to `"Listening..."`
3. Call `keyboard.read_hotkey(suppress=False)` in a separate thread (it blocks)
4. When key combo is released, the string is returned (e.g. `"ctrl+shift+f"`)
5. Update the text field with the result
6. Button text reverts to `"Record"`

**Hotkey string examples:**
- `"ctrl+shift+v"`
- `"alt+f9"`
- `"f8"`

**Important:** Validate that the hotkey doesn't conflict with common system shortcuts before saving. Warn (don't block) if user sets something like `"ctrl+c"`.

---

## 11. Packaging

Three options are available, ordered from simplest to best performance. Choose based on your priorities.

---

### Option A: PyInstaller (Default — simplest)

**Best for:** Getting a working `.exe` quickly. Most tested with MediaPipe.

**Startup time:** ~5–15 seconds (slow due to temp extraction on first launch)

### `build.bat`

```bat
@echo off
echo Building Vision Mouse...
uv run pyinstaller ^
    --onefile ^
    --windowed ^
    --icon=assets/icon.ico ^
    --name=VisionMouse ^
    --add-data "assets;assets" ^
    --hidden-import=mediapipe ^
    --hidden-import=cv2 ^
    --hidden-import=pynput ^
    --hidden-import=customtkinter ^
    --collect-all mediapipe ^
    --collect-all customtkinter ^
    src/vision_mouse/main.py
echo Done! Check dist/VisionMouse.exe
pause
```

**Notes:**
- `--windowed` suppresses the console window (important for a background app)
- `--collect-all mediapipe` is required — MediaPipe has data files and the `.task` model that must be bundled
- `--collect-all customtkinter` is required — CustomTkinter has theme JSON files
- Output: `dist/VisionMouse.exe` (~100–130MB bundled)
- No Python installation required on end user machine

---

### Option B: cx_Freeze (Faster startup)

**Best for:** Faster startup time with a folder-based distribution. Startup is ~3–8x faster than PyInstaller because there's no temp-extraction step.

```bash
uv add cx_freeze --dev
```

**`setup_cxfreeze.py`:**
```python
from cx_Freeze import setup, Executable
import sys

build_options = {
    "packages": ["mediapipe", "cv2", "pynput", "keyboard", "customtkinter", "pystray"],
    "include_files": [("assets/", "assets/")],
    "excludes": ["tkinter.test", "unittest"],
}

setup(
    name="VisionMouse",
    version="1.0.0",
    description="Offline hand gesture mouse controller",
    options={"build_exe": build_options},
    executables=[
        Executable(
            "src/vision_mouse/main.py",
            base="Win32GUI",   # suppresses console window
            target_name="VisionMouse.exe",
            icon="assets/icon.ico",
        )
    ],
)
```

**Build command:**
```bat
uv run python setup_cxfreeze.py build
```

Output is a `build/` folder (not a single `.exe`). Zip the folder for distribution.

---

### Option C: Nuitka (Best performance — compiled binary)

**Best for:** Fastest startup, best runtime performance, most AV-trusted output. Compiles Python to native C code.

**Trade-offs:** Requires a C compiler (MSVC or MinGW), build takes 5–15 minutes.

```bash
uv add nuitka --dev
# Also requires: pip install zstandard ordered-set --break-system-packages
```

**`build_nuitka.bat`:**
```bat
@echo off
echo Building Vision Mouse with Nuitka...
uv run python -m nuitka ^
    --standalone ^
    --onefile ^
    --windows-disable-console ^
    --windows-icon-from-ico=assets/icon.ico ^
    --output-filename=VisionMouse.exe ^
    --include-data-dir=assets=assets ^
    --include-package=mediapipe ^
    --include-package=cv2 ^
    --include-package=customtkinter ^
    --include-package=pystray ^
    --include-package=pynput ^
    --include-package=keyboard ^
    src/vision_mouse/main.py
echo Done! Check VisionMouse.exe
pause
```

---

### Packaging Comparison

| | PyInstaller | cx_Freeze | Nuitka |
|---|---|---|---|
| Startup time | Slow (~5–15s) | Fast (~1–3s) | Fastest (<1s) |
| Build time | ~1–3 min | ~1–3 min | ~5–15 min |
| Output type | Single `.exe` | Folder | Single `.exe` |
| MediaPipe support | Excellent | Good | Good (test required) |
| Complexity | Low | Low | Medium |
| Recommended for | Development/quick builds | Production (folder dist) | Production (single exe, best perf) |

---

## 12. Error Handling Rules

| Scenario | Behavior |
|---|---|
| Camera not found / disconnected | Log warning, show tray notification, stop tracking gracefully |
| No hand detected for 3+ seconds | Do nothing — cursor stays in place. Do NOT error. |
| MediaPipe model file missing | Show error dialog at startup: "hand_landmarker.task not found in assets/models/". Disable tracking. |
| MediaPipe init fails | Show error dialog, disable tracking, keep app alive |
| Settings JSON corrupted | Silently fall back to defaults, overwrite with clean defaults |
| Hotkey already registered by another app | Catch `keyboard` exception, show warning in settings UI |
| PyInstaller / Nuitka can't find model file | Resolve path via `sys._MEIPASS` in bundled builds (see `_get_model_path()` in Section 6.4) |

**General rule:** The app must NEVER crash silently. All exceptions in the tracking thread must be caught and logged to `%APPDATA%/VisionMouse/error.log`.

**Log format:**
```python
import logging, os

log_path = os.path.join(os.environ["APPDATA"], "VisionMouse", "error.log")
logging.basicConfig(
    filename=log_path,
    level=logging.ERROR,
    format="%(asctime)s %(levelname)s %(message)s"
)
```

---

## 13. Performance Constraints

| Metric | Target |
|---|---|
| Tracking frame rate | ≥ 30 FPS on mid-range CPU |
| End-to-end latency | ≤ 30ms (frame capture → cursor move) |
| RAM usage (idle) | < 80MB |
| RAM usage (tracking active) | < 250MB |
| CPU usage (tracking active) | < 25% on a 4-core CPU |
| Startup time | < 3 seconds to tray icon |

**Optimization rules:**
- Use `num_hands=1` in HandLandmarkerOptions (track only one hand)
- Use the `float16` variant of `hand_landmarker.task` — smallest and fastest model
- Use `VisionTaskRunningMode.VIDEO` — NOT `LIVE_STREAM` — for synchronous per-frame calls with no callback overhead
- Capture at `640x480`, not higher
- Process every frame — do NOT skip frames (causes jitter)
- Use `cv2.CAP_DSHOW` on Windows for minimal camera init overhead
- Run tracking loop in a daemon thread — never block main thread
- Do not render/display video frames unless `show_camera_preview` is enabled
- Increment `frame_timestamp_ms` by a fixed `33ms` per frame — do not use `time.time()` directly (avoids timestamp drift issues with the Tasks API)

---

## 14. Known Edge Cases

### Poor Lighting
- MediaPipe degrades in very dark environments
- **Mitigation:** Apply `cv2.equalizeHist()` on the grayscale channel before processing, or adjust `cv2.convertScaleAbs(frame, alpha=1.5, beta=30)` to brighten frames

### Jitter at Screen Edges
- Normalized coordinates near 0.0 or 1.0 cause cursor to snap to edges
- **Mitigation:** Clamp output to `[10, screen_w - 10]` and `[10, screen_h - 10]`

### Accidental Clicks
- Hand micro-tremors can trigger pinch threshold momentarily
- **Mitigation:** `click_hold_frames` — the pinch must persist for N consecutive frames

### Fast Hand Movement
- EMA smoothing introduces lag on fast movements
- **Mitigation:** Implement velocity-aware smoothing — reduce alpha dynamically when movement delta is large:
```python
delta = abs(x - self._prev_x) + abs(y - self._prev_y)
dynamic_alpha = min(1.0, self.alpha + delta * 5)  # faster movement = less smoothing
```

### App Already Running
- Prevent two instances with a named Windows mutex:
```python
import ctypes
mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "VisionMouseSingleInstance")
if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
    sys.exit(0)
```

### MediaPipe Model File Not Found at Runtime
- In a PyInstaller bundle, `__file__` is not the right path — use `sys._MEIPASS`
- Always use `_get_model_path()` (defined in Section 6.4) to resolve the model path
- Test the bundled `.exe` explicitly; model path issues only surface in the packaged build

### Tasks API Timestamp Issues
- `VisionTaskRunningMode.VIDEO` requires timestamps to be **strictly monotonically increasing**
- Do not reuse the same timestamp or pass `0` every frame — the landmarker will silently return empty results
- Use a simple counter incremented by `33` each frame (not wall clock time)

---

## Appendix: File Creation Checklist for Copilot

Build files in this order to minimize dependency issues:

- [ ] `pyproject.toml`
- [ ] `assets/icon.ico` (placeholder or real icon)
- [ ] `assets/models/hand_landmarker.task` (download — see Section 4)
- [ ] `src/vision_mouse/__init__.py`
- [ ] `src/vision_mouse/settings_store.py`
- [ ] `src/vision_mouse/camera.py`
- [ ] `src/vision_mouse/mouse_controller.py`
- [ ] `src/vision_mouse/hotkey.py`
- [ ] `src/vision_mouse/tracker.py`
- [ ] `src/vision_mouse/ui/__init__.py`
- [ ] `src/vision_mouse/ui/settings_window.py`
- [ ] `src/vision_mouse/ui/tray.py`
- [ ] `src/vision_mouse/main.py`
- [ ] `build.bat`
- [ ] `README.md`

---

*Documentation version: 2.0 | Target Python: 3.11+ | Target OS: Windows 10/11*
