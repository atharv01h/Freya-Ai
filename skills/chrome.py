# ============================================================
# skills/chrome.py — Chrome Browser Control
# Profile detection, launching, profile switching
# ============================================================

import subprocess
import json
import os
import logging
from pathlib import Path

logger = logging.getLogger("freya.skills.chrome")

_CONFIG_PATH = Path(__file__).parent.parent / "config.json"
_config = {}
try:
    with open(_CONFIG_PATH) as f:
        _config = json.load(f)
except Exception:
    pass

CHROME_EXE = _config.get("paths", {}).get(
    "chrome", r"C:\Program Files\Google\Chrome\Application\chrome.exe"
)
CHROME_USER_DATA = _config.get("paths", {}).get(
    "chrome_user_data",
    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data")
)

# Friendly name aliases
PROFILE_ALIASES = {
    "default": "Default",
    "personal": "Default",
    "work": "Profile 1",
    "school": "Profile 2",
    "gaming": "Profile 3",
}


def get_chrome_profiles() -> list[dict]:
    """Scan Chrome User Data for all profiles."""
    profiles = []
    user_data = Path(CHROME_USER_DATA)
    if not user_data.exists():
        return profiles

    for entry in user_data.iterdir():
        if entry.is_dir() and (entry.name == "Default" or entry.name.startswith("Profile")):
            prefs_file = entry / "Preferences"
            display_name = entry.name
            if prefs_file.exists():
                try:
                    with open(prefs_file, "r", encoding="utf-8", errors="ignore") as f:
                        prefs = json.load(f)
                    display_name = (
                        prefs.get("profile", {}).get("name")
                        or prefs.get("account_info", [{}])[0].get("full_name")
                        or entry.name
                    )
                except Exception:
                    pass
            profiles.append({"dir": entry.name, "name": display_name})

    profiles.sort(key=lambda p: p["dir"])
    return profiles


def open_chrome(profile_dir: str = "Default", url: str = "") -> str:
    """Launch Chrome with a specific profile directory."""
    if not Path(CHROME_EXE).exists():
        return f"Chrome not found at {CHROME_EXE}. Check config.json."
    cmd = [CHROME_EXE, f"--profile-directory={profile_dir}"]
    if url:
        cmd.append(url)
    subprocess.Popen(cmd)
    return f"Chrome opened with profile '{profile_dir}'."


def open_chrome_by_name(name: str) -> str:
    """Open Chrome by friendly profile name (work, personal, etc.)."""
    name_lower = name.lower().strip()
    # Check aliases
    if name_lower in PROFILE_ALIASES:
        return open_chrome(PROFILE_ALIASES[name_lower])
    # Search detected profiles
    profiles = get_chrome_profiles()
    for p in profiles:
        if name_lower in p["name"].lower() or name_lower in p["dir"].lower():
            return open_chrome(p["dir"])
    return f"Couldn't find a profile named '{name}'. Available: {[p['name'] for p in profiles]}"


def open_chrome_by_ordinal(ordinal: int) -> str:
    """Open Chrome by profile index (1=first, 2=second, etc.)."""
    profiles = get_chrome_profiles()
    if not profiles:
        return "No Chrome profiles found."
    idx = max(0, ordinal - 1)
    if idx >= len(profiles):
        return f"Only {len(profiles)} profile(s) found."
    p = profiles[idx]
    return open_chrome(p["dir"])


def list_profiles_text() -> str:
    """Return a human-readable list of profiles."""
    profiles = get_chrome_profiles()
    if not profiles:
        return "No Chrome profiles found."
    lines = [f"{i+1}. {p['name']} ({p['dir']})" for i, p in enumerate(profiles)]
    return "Chrome profiles:\n" + "\n".join(lines)


def open_chrome_to_url(url: str) -> str:
    """Open Chrome and navigate to a URL directly."""
    if not Path(CHROME_EXE).exists():
        # Fallback: try default shell open
        import webbrowser
        webbrowser.open(url)
        return f"Opened {url} in your default browser."
    import subprocess
    subprocess.Popen([CHROME_EXE, url])
    return f"Opened {url} in Chrome."