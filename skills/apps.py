# ============================================================
# skills/apps.py — Generic App Launcher
# Open common Windows apps by name
# ============================================================

import subprocess
import os
import logging
from pathlib import Path

logger = logging.getLogger("freya.skills.apps")

APP_MAP = {
    "notepad": "notepad.exe",
    "calculator": "calc.exe",
    "paint": "mspaint.exe",
    "explorer": "explorer.exe",
    "task manager": "taskmgr.exe",
    "cmd": "cmd.exe",
    "command prompt": "cmd.exe",
    "powershell": "powershell.exe",
    "control panel": "control.exe",
    "settings": "ms-settings:",
    "spotify": "spotify.exe",
    "vlc": r"C:\Program Files\VideoLAN\VLC\vlc.exe",
    "discord": os.path.expandvars(r"%LOCALAPPDATA%\Discord\Update.exe"),
    "steam": r"C:\Program Files (x86)\Steam\Steam.exe",
    "file explorer": "explorer.exe",
    "edge": r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    "word": r"C:\Program Files\Microsoft Office\root\Office16\WINWORD.EXE",
    "excel": r"C:\Program Files\Microsoft Office\root\Office16\EXCEL.EXE",
    "powerpoint": r"C:\Program Files\Microsoft Office\root\Office16\POWERPNT.EXE",
}

STORE_APPS = {
    "settings": "ms-settings:",
    "photos": "ms-photos:",
    "mail": "outlookmail:",
    "calendar": "outlookcal:",
    "maps": "bingmaps:",
    "store": "ms-windows-store:",
}


def open_app(name: str) -> str:
    name_lower = name.lower().strip()

    import re
    # ── Drive letters (e.g. "open E drive", "open file explorer c drive")
    drive_match = re.search(r"(?:file\s+explorer\s+)?([a-z])\s+drive\b", name_lower)
    if drive_match:
        drive_letter = drive_match.group(1).upper()
        drive_path = f"{drive_letter}:\\"
        if os.path.exists(drive_path):
            os.startfile(drive_path)
            return f"Opened {drive_letter} Drive."
        else:
            return f"Drive {drive_letter} does not exist on this computer."

    # ── Common Windows Folders
    folders = {
        "downloads": os.path.expanduser("~/Downloads"),
        "documents": os.path.expanduser("~/Documents"),
        "desktop": os.path.expanduser("~/Desktop"),
        "pictures": os.path.expanduser("~/Pictures"),
        "videos": os.path.expanduser("~/Videos"),
        "music": os.path.expanduser("~/Music")
    }
    for folder_name, folder_path in folders.items():
        if folder_name in name_lower:
            if os.path.exists(folder_path):
                os.startfile(folder_path)
                return f"Opened {folder_name.title()} folder."

    # Direct map lookup
    for key, cmd in APP_MAP.items():
        if key in name_lower or name_lower in key:
            try:
                if cmd.startswith("ms-"):
                    os.startfile(cmd)
                elif Path(cmd).exists():
                    subprocess.Popen([cmd])
                else:
                    subprocess.Popen(cmd, shell=True)
                return f"Opening {name}."
            except Exception as e:
                logger.warning("App launch failed for %s: %s", name, e)

    # Store apps
    for key, proto in STORE_APPS.items():
        if key in name_lower:
            try:
                os.startfile(proto)
                return f"Opening {name}."
            except Exception:
                pass

    # Try direct shell execution
    try:
        subprocess.Popen(name, shell=True)
        return f"Trying to open '{name}'."
    except Exception as e:
        return f"Couldn't find or open '{name}': {e}"


def close_app(name: str) -> str:
    """Close a running application by process name."""
    import psutil
    closed = []
    name_lower = name.lower().replace(".exe", "")
    for proc in psutil.process_iter(["name", "pid"]):
        if name_lower in proc.info["name"].lower():
            try:
                proc.terminate()
                closed.append(proc.info["name"])
            except Exception:
                pass
    if closed:
        return f"Closed: {', '.join(set(closed))}"
    return f"No running process found for '{name}'."


def open_notepad() -> str:
    return open_app("notepad")
