# ============================================================
# automation/desktop.py — Desktop Automation
# pyautogui wrappers for click, type, hotkeys, app control
# ============================================================

import subprocess
import logging
import time
import os

logger = logging.getLogger("freya.automation")


def _gui():
    import pyautogui
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.05
    return pyautogui


def click(x: int, y: int) -> str:
    _gui().click(x, y)
    return f"Clicked at ({x}, {y})"


def double_click(x: int, y: int) -> str:
    _gui().doubleClick(x, y)
    return f"Double-clicked at ({x}, {y})"


def right_click(x: int, y: int) -> str:
    _gui().rightClick(x, y)
    return f"Right-clicked at ({x}, {y})"


def type_text(text: str, interval: float = 0.03) -> str:
    _gui().write(text, interval=interval)
    return f"Typed: {text[:30]}..."


def press_key(key: str) -> str:
    _gui().press(key)
    return f"Pressed: {key}"


def hotkey(*keys) -> str:
    _gui().hotkey(*keys)
    return f"Hotkey: {'+'.join(keys)}"


def scroll(direction: str = "down", amount: int = 3) -> str:
    pg = _gui()
    clicks = amount if direction == "up" else -amount
    pg.scroll(clicks)
    return f"Scrolled {direction} {amount} times."


def move_to(x: int, y: int) -> str:
    _gui().moveTo(x, y, duration=0.2)
    return f"Moved mouse to ({x}, {y})"


def minimize_window() -> str:
    hotkey("win", "down")
    return "Window minimized."


def maximize_window() -> str:
    hotkey("win", "up")
    return "Window maximized."


def switch_window() -> str:
    hotkey("alt", "tab")
    return "Switched window."


def open_run_dialog() -> str:
    hotkey("win", "r")
    time.sleep(0.3)
    return "Run dialog opened."


def lock_screen() -> str:
    hotkey("win", "l")
    return "Screen locked."


def show_desktop() -> str:
    hotkey("win", "d")
    return "Desktop shown."


def open_app_via_run(command: str) -> str:
    open_run_dialog()
    time.sleep(0.3)
    type_text(command)
    press_key("enter")
    return f"Ran: {command}"


def copy_selected() -> str:
    hotkey("ctrl", "c")
    time.sleep(0.1)
    try:
        import pyperclip
        return pyperclip.paste()
    except Exception:
        return "Copied to clipboard."


def paste() -> str:
    hotkey("ctrl", "v")
    return "Pasted from clipboard."


def select_all() -> str:
    hotkey("ctrl", "a")
    return "All selected."


def close_active_window() -> str:
    hotkey("alt", "f4")
    return "Active window closed."


def get_screen_size() -> tuple:
    import pyautogui
    return pyautogui.size()


def find_and_click_image(image_path: str, confidence: float = 0.8) -> str:
    """Find an image on screen and click it."""
    try:
        import pyautogui
        loc = pyautogui.locateOnScreen(image_path, confidence=confidence)
        if loc:
            center = pyautogui.center(loc)
            pyautogui.click(center)
            return f"Found and clicked image at {center}"
        return "Image not found on screen."
    except Exception as e:
        return f"Image search error: {e}"
