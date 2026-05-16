# ============================================================
# vision/screen_reader.py — Screen Capture, OCR, Vision
# Screenshot → NVIDIA NIM multimodal (Llama 4 Scout)
# OCR fallback via EasyOCR for fast text extraction
# No Ollama/Moondream needed — fully API-powered
# ============================================================

import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger("freya.vision")

_ocr_reader = None
_ocr_available = False


def _init_ocr():
    global _ocr_reader, _ocr_available
    try:
        import easyocr
        _ocr_reader = easyocr.Reader(["en"], gpu=False, verbose=False)
        _ocr_available = True
        logger.info("EasyOCR initialized OK")
    except ImportError:
        logger.warning("easyocr not installed — OCR unavailable")
    except Exception as e:
        logger.warning("EasyOCR init failed: %s", e)


def capture_screenshot(save_path: str = "") -> str:
    """Take a full-screen screenshot and return the saved file path."""
    try:
        import mss
        import mss.tools
        if not save_path:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            save_dir = Path("screenshots")
            save_dir.mkdir(exist_ok=True)
            save_path = str(save_dir / f"screen_{ts}.png")

        with mss.mss() as sct:
            monitor = sct.monitors[1]  # Primary monitor
            screenshot = sct.grab(monitor)
            mss.tools.to_png(screenshot.rgb, screenshot.size, output=save_path)

        logger.debug("Screenshot saved: %s", save_path)
        return save_path

    except Exception as e:
        logger.error("mss screenshot failed: %s", e)
        try:
            import pyautogui
            p = save_path or "screenshot.png"
            pyautogui.screenshot().save(p)
            return p
        except Exception as e2:
            logger.error("pyautogui screenshot also failed: %s", e2)
            return f"ERROR:{e2}"


def capture_screenshot_base64() -> str:
    """Take a screenshot and return it as a base64 PNG string directly (no disk write)."""
    import base64
    try:
        import mss
        import mss.tools
        with mss.mss() as sct:
            monitor = sct.monitors[1]
            shot = sct.grab(monitor)
            png_bytes = mss.tools.to_png(shot.rgb, shot.size)
        return base64.b64encode(png_bytes).decode()
    except Exception as e:
        logger.error("capture_screenshot_base64 failed: %s", e)
        # Fallback: save to file then encode
        path = capture_screenshot()
        if path.startswith("ERROR"):
            return ""
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()


def read_screen_text(region: dict = None) -> str:
    """
    Fast text extraction via EasyOCR — no AI needed.
    Best for reading specific text, code, error messages on screen.
    """
    global _ocr_reader, _ocr_available

    if not _ocr_available:
        _init_ocr()

    try:
        import mss
        import numpy as np

        with mss.mss() as sct:
            monitor = region or sct.monitors[1]
            screenshot = sct.grab(monitor)
            img_array = np.array(screenshot)

        if _ocr_available:
            results = _ocr_reader.readtext(img_array, detail=0)
            text = " ".join(results).strip()
            return text if text else "No text detected on screen."
        else:
            try:
                from PIL import Image
                import pytesseract
                img = Image.fromarray(img_array)
                return pytesseract.image_to_string(img).strip()
            except Exception:
                return "OCR not available. Install easyocr."

    except Exception as e:
        logger.error("Screen read error: %s", e)
        return f"Screen read failed: {e}"


def describe_screen(custom_prompt: str = "") -> str:
    """
    Take a screenshot and send it to NVIDIA NIM (Llama 4 Scout multimodal)
    for a full AI description. No Ollama needed.
    """
    try:
        img_b64 = capture_screenshot_base64()
        if not img_b64:
            return "Couldn't capture the screen."

        from brain.llm import vision_describe_base64
        active_window = get_active_window_title()
        prompt = custom_prompt or (
            f"You are Freya, an AI assistant with vision. "
            f"The user's currently focused window is: '{active_window}'. "
            f"Describe what you see on this screen in detail — the app open, any text, "
            f"buttons, or content visible. Be specific and helpful."
        )
        return vision_describe_base64(img_b64, prompt)

    except Exception as e:
        logger.error("Screen describe error: %s", e)
        return f"Vision analysis failed: {e}"


def describe_screen_for_context() -> str:
    """
    Lightweight screen snapshot for injecting into LLM context.
    Returns a compact summary instead of verbose description.
    """
    try:
        img_b64 = capture_screenshot_base64()
        if not img_b64:
            return ""

        from brain.llm import vision_describe_base64
        prompt = (
            "Briefly describe what's on this screen in 1-2 sentences. "
            "Focus on: what app is open, what content is visible, what the user might be doing."
        )
        return vision_describe_base64(img_b64, prompt)
    except Exception as e:
        logger.debug("Context screenshot failed: %s", e)
        return ""


def get_active_window_title() -> str:
    """Return the title of the currently focused window."""
    try:
        import ctypes
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
        return buf.value or "Unknown"
    except Exception:
        return "Unknown"


def identify_open_apps() -> str:
    """List currently visible window titles."""
    try:
        import ctypes

        titles = []

        def enum_handler(hwnd, _):
            if ctypes.windll.user32.IsWindowVisible(hwnd):
                length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buf = ctypes.create_unicode_buffer(length + 1)
                    ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
                    title = buf.value.strip()
                    if title and title not in titles:
                        titles.append(title)

        WNDENUMPROC = ctypes.WINFUNCTYPE(
            ctypes.c_bool, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int)
        )
        ctypes.windll.user32.EnumWindows(WNDENUMPROC(enum_handler), 0)

        if titles:
            return "Open windows:\n" + "\n".join(f"• {t}" for t in titles[:12])
        return "No visible windows found."
    except Exception as e:
        return f"Window enumeration failed: {e}"
