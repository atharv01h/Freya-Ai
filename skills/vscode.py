# ============================================================
# skills/vscode.py — VS Code Control
# Launch, open folders/files, new file
# ============================================================

import subprocess
import logging
import json
from pathlib import Path

logger = logging.getLogger("freya.skills.vscode")

_CONFIG_PATH = Path(__file__).parent.parent / "config.json"
_config = {}
try:
    with open(_CONFIG_PATH) as f:
        _config = json.load(f)
except Exception:
    pass

VSCODE_EXE = _config.get("paths", {}).get(
    "vscode",
    r"C:\Users\athar\AppData\Local\Programs\Microsoft VS Code\Code.exe"
)


def open_vscode(path: str = "") -> str:
    try:
        cmd = [VSCODE_EXE]
        if path:
            cmd.append(path)
        subprocess.Popen(cmd)
        return f"VS Code opened{' at ' + path if path else ''}."
    except FileNotFoundError:
        # Try via PATH
        try:
            cmd = ["code"]
            if path:
                cmd.append(path)
            subprocess.Popen(cmd, shell=True)
            return f"VS Code opened{' at ' + path if path else ''}."
        except Exception as e:
            return f"Couldn't open VS Code: {e}"
    except Exception as e:
        return f"VS Code error: {e}"


def open_vscode_folder(folder: str) -> str:
    fpath = Path(folder)
    if not fpath.exists():
        # Try common locations
        for base in [Path.home() / "Projects", Path.home() / "Documents", Path("D:/")]:
            candidate = base / folder
            if candidate.exists():
                fpath = candidate
                break
    return open_vscode(str(fpath))


def new_file_in_vscode(filename: str, folder: str = "") -> str:
    target_dir = Path(folder) if folder else Path.home() / "Documents"
    target_dir.mkdir(parents=True, exist_ok=True)
    fpath = target_dir / filename
    fpath.touch(exist_ok=True)
    return open_vscode(str(fpath))


def install_vscode_extension(ext_id: str) -> str:
    try:
        subprocess.run(["code", "--install-extension", ext_id], shell=True, check=True)
        return f"Extension '{ext_id}' installed."
    except Exception as e:
        return f"Extension install failed: {e}"
