# ============================================================
# skills/music.py — Music Control
# Open Spotify / YouTube Music, media keys
# ============================================================

import subprocess
import logging
import os
from pathlib import Path

logger = logging.getLogger("freya.skills.music")


def play_pause() -> str:
    try:
        import pyautogui
        pyautogui.press("playpause")
        return "Play/Pause toggled."
    except Exception as e:
        return f"Media key error: {e}"


def next_track() -> str:
    try:
        import pyautogui
        pyautogui.press("nexttrack")
        return "Skipped to next track."
    except Exception as e:
        return f"Media key error: {e}"


def prev_track() -> str:
    try:
        import pyautogui
        pyautogui.press("prevtrack")
        return "Going to previous track."
    except Exception as e:
        return f"Media key error: {e}"


def open_spotify() -> str:
    candidates = [
        os.path.expandvars(r"%APPDATA%\Spotify\Spotify.exe"),
        r"C:\Program Files\WindowsApps\SpotifyAB.SpotifyMusic_*\Spotify.exe",
    ]
    for c in candidates:
        import glob
        matches = glob.glob(c)
        if matches and Path(matches[0]).exists():
            subprocess.Popen([matches[0]])
            return "Spotify opened."
    # Try shell
    try:
        subprocess.Popen("spotify", shell=True)
        return "Spotify opened."
    except Exception:
        pass
    return "Spotify not found. Try installing it from the Microsoft Store."


def open_youtube_music() -> str:
    try:
        from browser.browser_engine import get_browser_page
        import asyncio
        async def _open():
            page = await get_browser_page()
            await page.goto("https://music.youtube.com", wait_until="domcontentloaded")
            return "YouTube Music opened."
        return asyncio.run(_open())
    except Exception:
        import webbrowser
        webbrowser.open("https://music.youtube.com")
        return "YouTube Music opened in browser."


def play_lofi() -> str:
    try:
        import webbrowser
        webbrowser.open("https://www.youtube.com/results?search_query=lofi+hip+hop+radio")
        return "Opening lo-fi music on YouTube."
    except Exception as e:
        return f"Couldn't open lo-fi: {e}"


def search_spotify(query: str) -> str:
    import webbrowser
    import urllib.parse
    webbrowser.open(f"https://open.spotify.com/search/{urllib.parse.quote(query)}")
    return f"Searching Spotify for '{query}'."
