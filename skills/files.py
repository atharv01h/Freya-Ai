# ============================================================
# skills/files.py — File & Folder Operations
# Create, open, search, delete (with confirmation gate)
# ============================================================

import os
import subprocess
import logging
import shutil
from pathlib import Path
from datetime import datetime

logger = logging.getLogger("freya.skills.files")

DEFAULT_BASE = Path.home() / "Documents"


def create_file(name: str, base_dir: str = "") -> str:
    base = Path(base_dir) if base_dir else DEFAULT_BASE
    base.mkdir(parents=True, exist_ok=True)
    filepath = base / name
    if not filepath.suffix:
        filepath = filepath.with_suffix(".txt")
    filepath.touch(exist_ok=True)
    return f"File created: {filepath}"


def create_folder(name: str, base_dir: str = "") -> str:
    base = Path(base_dir) if base_dir else DEFAULT_BASE
    folder = base / name
    folder.mkdir(parents=True, exist_ok=True)
    return f"Folder created: {folder}"


def create_project_folder(name: str, base_dir: str = "") -> str:
    base = Path(base_dir) if base_dir else Path.home() / "Projects"
    project = base / name
    project.mkdir(parents=True, exist_ok=True)
    # Create common subfolders
    for sub in ["src", "docs", "tests"]:
        (project / sub).mkdir(exist_ok=True)
    return f"Project folder '{name}' created at {project}"


def open_file(path: str) -> str:
    fpath = Path(path)
    if not fpath.exists():
        # Try searching
        results = search_files(fpath.name)
        if results:
            fpath = Path(results[0])
        else:
            return f"File not found: {path}"
    os.startfile(str(fpath))
    return f"Opened {fpath.name}"


def open_folder(path: str) -> str:
    fpath = Path(path)
    if fpath.exists():
        subprocess.Popen(f'explorer "{fpath}"')
        return f"Opened folder: {fpath}"
    return f"Folder not found: {path}"


def search_files(name: str, search_dir: str = "") -> list[str]:
    """Search for files matching name pattern."""
    base = Path(search_dir) if search_dir else Path.home()
    results = []
    try:
        for match in base.rglob(f"*{name}*"):
            results.append(str(match))
            if len(results) >= 10:
                break
    except PermissionError:
        pass
    return results


def search_files_text(name: str) -> str:
    results = search_files(name)
    if not results:
        return f"No files found matching '{name}'."
    lines = [f"{i+1}. {r}" for i, r in enumerate(results[:5])]
    return "Found these files:\n" + "\n".join(lines)


def delete_file(path: str) -> str:
    """Delete a file — caller must ensure confirmation was given."""
    fpath = Path(path)
    if not fpath.exists():
        return f"File not found: {path}"
    if fpath.is_dir():
        shutil.rmtree(fpath)
        return f"Folder deleted: {fpath}"
    fpath.unlink()
    return f"File deleted: {fpath}"


def list_directory(path: str = "") -> str:
    target = Path(path) if path else Path.home() / "Documents"
    if not target.exists():
        return f"Directory not found: {path}"
    items = list(target.iterdir())
    dirs = [f"📁 {i.name}" for i in items if i.is_dir()]
    files = [f"📄 {i.name}" for i in items if i.is_file()]
    result = dirs[:5] + files[:10]
    return f"Contents of {target.name}:\n" + "\n".join(result)


def get_downloads_folder() -> str:
    downloads = Path.home() / "Downloads"
    if downloads.exists():
        items = sorted(downloads.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True)
        recent = [f.name for f in items[:5]]
        return "Recent downloads:\n" + "\n".join(recent)
    return "Downloads folder not found."
