# Vision Mouse

**Offline hand-gesture mouse controller for Windows.**

Control your mouse cursor using hand gestures captured by your webcam.
All machine learning inference runs locally on your CPU — no internet connection required, no data leaves your machine.

---

## Table of Contents

- [Download and Run](#download-and-run)
- [Features](#features)
- [Gestures](#gestures)
- [Settings](#settings)
- [PiP Camera Preview](#pip-camera-preview)
- [Build from Source](#build-from-source)
- [Project Structure](#project-structure)
- [Tech Stack](#tech-stack)
- [Troubleshooting](#troubleshooting)
- [License](#license)

---

## Download and Run

**No Python or setup required.** Download the portable executable and run it.

1. Go to the [Releases](https://github.com/Ns81000/Vision-Mouse/releases) page.
2. Download `VisionMouse.exe` (approx. 92 MB).
3. Double-click to launch. The app starts in the **system tray** (bottom-right of
   your taskbar, near the clock).
4. Press **Ctrl + Shift + V** to toggle hand tracking on and off.

> **Note:** Windows SmartScreen may show a warning the first time you run it.
> Click "More info" then "Run anyway". The application is safe — the full source
> code is available in this repository.

---

## Features

- **Fully offline** — MediaPipe runs on-device, zero network calls, no telemetry.
- **Single-file portable executable** — one `.exe`, nothing to install.
- **Global hotkey toggle** — press `Ctrl+Shift+V` to enable or disable tracking
  at any time, even when another window is focused.
- **Five gesture actions** — move, left click, right click, scroll, and drag.
- **Floating PiP camera preview** — a resizable, draggable, always-on-top overlay
  that shows the live camera feed with hand skeleton and gesture annotations drawn
  in real-time.
- **Dark-themed settings panel** — configure camera, hotkey, smoothing, sensitivity,
  and click timing through a polished CustomTkinter interface.
- **System tray integration** — lives quietly in the tray with a right-click menu
  for toggling tracking, opening the preview, opening settings, and quitting.
- **EMA cursor smoothing** — velocity-aware exponential moving average filter
  eliminates jitter while keeping fast movements responsive.
- **Single-instance guard** — a Windows mutex prevents multiple copies from running
  simultaneously.

---

## Gestures

| Gesture | Hand Pose | Action |
|---|---|---|
| **Move** | Index finger extended, other fingers down | Moves the cursor |
| **Left Click** | Thumb tip touches index finger tip (pinch) | Left mouse click |
| **Right Click** | Thumb tip touches middle finger tip (pinch) | Right mouse click |
| **Scroll** | Index and middle fingers extended, ring and pinky down | Scroll up/down based on hand movement |
| **Drag** | Closed fist (all fingers curled) | Hold left click and move |

Pinch gestures require the fingertips to be within a normalised Euclidean distance
of 0.05. A configurable hold-frame threshold prevents accidental clicks.

---

## Settings

Right-click the tray icon and select **Settings** to open the configuration panel.
Settings persist to `%APPDATA%/VisionMouse/settings.json`.

| Setting | Default | Description |
|---|---|---|
| `camera_index` | `0` | Webcam device index (auto-detected list shown in dropdown) |
| `hotkey` | `ctrl+shift+v` | Global toggle hotkey (recordable via the Settings panel) |
| `smoothing` | `0.5` | Cursor smoothing factor. 0 = raw input, 1 = maximum smoothing |
| `sensitivity` | `1.5` | Cursor speed multiplier. Higher values cover more screen area |
| `click_hold_frames` | `8` | Number of consecutive pinch frames required to register a click |
| `show_camera_preview` | `false` | Automatically open the PiP overlay when tracking starts |

---

## PiP Camera Preview

Vision Mouse includes a floating Picture-in-Picture overlay that displays the
live camera feed with hand tracking annotations drawn on top.

**What it shows:**
- 21-point hand skeleton with colour-coded connections by finger group
- Detected gesture label with a colour-coded status indicator
- Index finger crosshair showing the active cursor control point
- Pinch distance line when a click gesture is detected
- Green status dot (hand detected) or grey dot (no hand)

**Controls:**
- Drag the title bar to reposition the window
- Click the S / M / L button to cycle through three size presets (320x240, 440x330, 640x480)
- Drag the bottom-right corner to resize freely (min 200x150, max 640x480)
- Click X to close the overlay
- Toggle from the tray menu: right-click the tray icon and select "Show Preview" or "Hide Preview"

To auto-open the preview every time tracking starts, enable "Auto-open PiP overlay"
in the Settings panel.

---

## Build from Source

### Prerequisites

- Windows 10 or 11
- Python 3.11 or newer
- A webcam (built-in or USB)
- [uv](https://docs.astral.sh/uv/) package manager

### Setup

```bash
git clone https://github.com/Ns81000/Vision-Mouse.git
cd Vision-Mouse

# Create virtual environment and install dependencies
uv venv
uv add mediapipe opencv-python pynput keyboard customtkinter pystray Pillow pyinstaller
```

### Download the MediaPipe model

The hand landmarker model (approx. 7.8 MB) must be placed at
`assets/models/hand_landmarker.task`:

```bash
mkdir assets\models
curl -o assets/models/hand_landmarker.task ^
  https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task
```

### Run from source

```bash
uv run python -m vision_mouse.main
```

### Build the executable

```bash
build.bat
```

The output is a single portable file at `dist/VisionMouse.exe` (approx. 90-100 MB).

---

## Project Structure

```
Vision-Mouse/
    pyproject.toml              Project metadata and dependencies
    build.bat                   PyInstaller build script
    README.md                   This file
    assets/
        icon.ico                Application icon (tray + exe)
        models/
            hand_landmarker.task    MediaPipe float16 hand landmarker model
    src/
        vision_mouse/
            __init__.py
            main.py             Entry point: mutex, logging, component bootstrap
            camera.py           Camera enumeration and frame capture (OpenCV)
            tracker.py          MediaPipe hand tracking, gesture detection, EMA filter
            mouse_controller.py Cursor movement, clicks, scroll (pynput)
            hotkey.py           Global hotkey registration (keyboard library)
            settings_store.py   JSON settings persistence (%APPDATA%)
            ui/
                __init__.py
                tray.py         System tray icon and menu (pystray)
                settings_window.py  Dark-themed settings panel (CustomTkinter)
                pip_overlay.py  Floating PiP camera preview with landmark overlay
```

---

## Tech Stack

| Component | Library | Purpose |
|---|---|---|
| Hand tracking | MediaPipe Tasks API | 21-point hand landmark detection via `HandLandmarker` (VIDEO mode) |
| Camera capture | OpenCV | DirectShow backend, 640x480, frame acquisition |
| Mouse control | pynput | Cursor positioning, click, press, release, scroll |
| Global hotkey | keyboard | System-wide hotkey registration and recording |
| Settings UI | CustomTkinter | Dark-themed settings panel and PiP overlay window |
| System tray | pystray | Tray icon with right-click context menu |
| Image processing | Pillow | Icon loading, frame conversion for Tk canvas display |
| Build | PyInstaller | Single-file Windows executable bundling |

---

## Troubleshooting

**The app does not appear after launching.**
It starts minimised in the system tray. Look for the Vision Mouse icon near the
clock in your taskbar. You may need to click the small arrow to expand hidden
tray icons.

**Windows SmartScreen blocks the exe.**
Click "More info" and then "Run anyway". This happens because the executable is
not digitally signed.

**Camera is not detected.**
Make sure no other application is using the camera. Open Settings and try a
different camera index from the dropdown.

**Cursor is jittery or too slow.**
Adjust the Smoothing and Sensitivity sliders in Settings. Higher smoothing
reduces jitter; higher sensitivity increases cursor speed.

**Pinch clicks fire too easily or not at all.**
Increase the Click Hold Frames value in Settings to require a longer pinch, or
decrease it to make clicks more responsive.

**"Another instance is already running" message.**
Only one copy of Vision Mouse can run at a time. Check the system tray for an
existing instance, or end the process via Task Manager.

**Error log location.**
Runtime errors are written to `%APPDATA%/VisionMouse/error.log`.

---

## License

MIT
