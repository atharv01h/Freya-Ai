# ============================================================
# browser/chrome_profiles.py — Chrome Profile Manager
# Detect, list, launch by name or ordinal
# ============================================================

import json
import os
import subprocess
import logging
from pathlib import Path

logger = logging.getLogger("freya.browser.chrome_profiles")

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

ORDINAL_WORDS = {
    "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5,
    "1st": 1, "2nd": 2, "3rd": 3, "4th": 4, "5th": 5,
    "1": 1, "2": 2, "3": 3, "4": 4, "5": 5,
}

PROFILE_ALIASES = {
    "default": "Default",
    "personal": "Default",
    "first": None,   # resolved by ordinal
}


def get_profiles() -> list[dict]:
    """Return sorted list of Chrome profiles with display names."""
    profiles = []
    base = Path(CHROME_USER_DATA)
    if not base.exists():
        logger.warning("Chrome user data not found at %s", CHROME_USER_DATA)
        return profiles

    for entry in sorted(base.iterdir()):
        if not entry.is_dir():
            continue
        if entry.name != "Default" and not entry.name.startswith("Profile"):
            continue
        name = entry.name
        prefs = entry / "Preferences"
        if prefs.exists():
            try:
                data = json.loads(prefs.read_text(encoding="utf-8", errors="ignore"))
                name = (
                    data.get("profile", {}).get("name")
                    or (data.get("account_info") or [{}])[0].get("full_name")
                    or entry.name
                )
            except Exception:
                pass
        profiles.append({"dir": entry.name, "name": name, "index": len(profiles) + 1})

    return profiles


def launch_profile(profile_dir: str, url: str = "") -> str:
    if not Path(CHROME_EXE).exists():
        return f"Chrome not found at: {CHROME_EXE}"
    cmd = [CHROME_EXE, f"--profile-directory={profile_dir}"]
    if url:
        cmd.append(url)
    subprocess.Popen(cmd)
    return f"Opened Chrome — profile: {profile_dir}"


def open_by_name(name: str) -> str:
    """Open profile by friendly name."""
    name_l = name.lower().strip()

    # Check ordinals first
    if name_l in ORDINAL_WORDS:
        return open_by_ordinal(ORDINAL_WORDS[name_l])

    # Static aliases
    if name_l in PROFILE_ALIASES and PROFILE_ALIASES[name_l]:
        return launch_profile(PROFILE_ALIASES[name_l])

    # Scan profiles
    for p in get_profiles():
        if name_l in p["name"].lower() or name_l in p["dir"].lower():
            return launch_profile(p["dir"])

    return f"Profile '{name}' not found. Say 'list Chrome profiles' to see available ones."


def open_by_ordinal(n: int) -> str:
    """Open profile by position (1=first)."""
    profiles = get_profiles()
    if not profiles:
        return "No Chrome profiles found."
    idx = n - 1
    if idx < 0 or idx >= len(profiles):
        return f"Only {len(profiles)} profile(s) found. Choose between 1 and {len(profiles)}."
    return launch_profile(profiles[idx]["dir"])


def list_profiles() -> str:
    profiles = get_profiles()
    if not profiles:
        return "No Chrome profiles detected."
    lines = [f"{p['index']}. {p['name']} ({p['dir']})" for p in profiles]
    return "Chrome profiles:\n" + "\n".join(lines)


def resolve_profile_from_intent(entities: dict) -> str:
    """Main resolver used by intent router."""
    if "profile_ordinal" in entities:
        return open_by_ordinal(int(entities["profile_ordinal"]))
    if "profile_name" in entities:
        return open_by_name(entities["profile_name"])
    return open_by_name("Default")
