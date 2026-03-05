"""Translate (x, y) coordinates and gesture signals into OS mouse events."""

from __future__ import annotations

from pynput.mouse import Button, Controller


class MouseController:
    """Thin wrapper around pynput.mouse.Controller for cursor manipulation."""

    def __init__(self) -> None:
        self._mouse = Controller()

    def move_to(self, x: int, y: int) -> None:
        """Move cursor to absolute screen position."""
        self._mouse.position = (x, y)

    def click(self, button: str = "left") -> None:
        """Perform a single click ('left' or 'right')."""
        btn = Button.left if button == "left" else Button.right
        self._mouse.click(btn)

    def press(self, button: str = "left") -> None:
        """Mouse button down (for drag)."""
        btn = Button.left if button == "left" else Button.right
        self._mouse.press(btn)

    def release(self, button: str = "left") -> None:
        """Mouse button up."""
        btn = Button.left if button == "left" else Button.right
        self._mouse.release(btn)

    def scroll(self, direction: int = 1) -> None:
        """Scroll up (+1) or down (-1). Multiplied by 3 for perceptible scroll."""
        self._mouse.scroll(0, direction * 3)
