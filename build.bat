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
