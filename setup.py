# ============================================================
# setup.py -- Freya AI One-Click Setup
# ============================================================

import subprocess
import sys
import os
import json
import shutil
from pathlib import Path

ROOT   = Path(__file__).parent
VENV   = ROOT / "venv"
PYTHON = VENV / "Scripts" / "python.exe"
PYTHONW= VENV / "Scripts" / "pythonw.exe"
PIP    = VENV / "Scripts" / "pip.exe"

def say(msg):
    print(msg, flush=True)

def run(cmd, check=True, capture=False):
    say("  >> " + " ".join(str(c) for c in cmd))
    if capture:
        return subprocess.run(cmd, capture_output=True, text=True)
    return subprocess.run(cmd, check=check)

def create_venv():
    say("\n[1/6] Creating virtual environment...")
    if VENV.exists():
        say("  OK  venv already exists")
        return
    run([sys.executable, "-m", "venv", str(VENV)])
    say("  OK  venv created")

def install_requirements():
    say("\n[2/6] Installing Python packages (may take 5-10 min)...")
    run([str(PIP), "install", "--upgrade", "pip", "-q"])
    run([str(PIP), "install", "-r", "requirements.txt"])
    say("  OK  Packages installed")

def install_playwright():
    say("\n[3/6] Installing Playwright Chromium...")
    run([str(PYTHON), "-m", "playwright", "install", "chromium"])
    say("  OK  Playwright ready")

def download_wakeword_models():
    say("\n[4/6] Downloading OpenWakeWord models...")
    result = run(
        [str(PYTHON), "-c",
         "import openwakeword; openwakeword.utils.download_models(); print('done')"],
        check=False, capture=True
    )
    if result and "done" in (result.stdout or ""):
        say("  OK  OpenWakeWord models downloaded")
    else:
        say("  NOTE: OpenWakeWord download skipped (install manually if needed)")

def create_directories():
    say("\n[5/6] Creating directory structure...")
    dirs = ["logs", "screenshots", "memory", "brain", "voice", "wakeword",
            "automation", "browser", "vision", "skills", "personality"]
    for d in dirs:
        Path(d).mkdir(exist_ok=True)
        init_file = Path(d) / "__init__.py"
        if not init_file.exists():
            init_file.touch()
    say("  OK  Directories ready")

def register_startup():
    say("\n[6/6] Registering Windows auto-start...")
    script_path = ROOT / "freya.py"
    pythonw_exe = PYTHONW if PYTHONW.exists() else PYTHON

    # Registry method
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_SET_VALUE
        )
        cmd = f'"{pythonw_exe}" "{script_path}"'
        winreg.SetValueEx(key, "FreyaAI", 0, winreg.REG_SZ, cmd)
        winreg.CloseKey(key)
        say("  OK  Registry startup entry added")
    except Exception as e:
        say(f"  WARN Registry: {e}")

    # Startup folder method
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders"
        )
        startup_folder = winreg.QueryValueEx(key, "Startup")[0]
        winreg.CloseKey(key)
        bat_path = Path(startup_folder) / "FreyaAI.bat"
        bat_path.write_text(
            f"@echo off\r\n"
            f"cd /d \"{ROOT}\"\r\n"
            f"start \"\" \"{pythonw_exe}\" \"{script_path}\"\r\n"
        )
        say(f"  OK  Startup folder: {bat_path}")
    except Exception as e:
        say(f"  WARN Startup folder: {e}")

    # Local launcher .bat
    launcher = ROOT / "START_FREYA.bat"
    launcher.write_text(
        f"@echo off\r\n"
        f"cd /d \"{ROOT}\"\r\n"
        f"\"{pythonw_exe}\" \"{script_path}\"\r\n"
    )
    say(f"  OK  Launcher: START_FREYA.bat")

def check_ollama():
    say("\n[Checking Ollama...]")
    if shutil.which("ollama"):
        say("  OK  Ollama found")
        result = subprocess.run(["ollama", "list"], capture_output=True, text=True)
        if "qwen2.5:3b" in result.stdout:
            say("  OK  qwen2.5:3b model present")
        else:
            say("  Pulling qwen2.5:3b model (this downloads ~2GB)...")
            subprocess.run(["ollama", "pull", "qwen2.5:3b"])
    else:
        say("  ERROR: Ollama not found!")
        say("  Download from: https://ollama.com/download")
        say("  Then run:  ollama pull qwen2.5:3b")

def done():
    say("\n" + "=" * 50)
    say("  Freya AI Setup Complete!")
    say("=" * 50)
    say("")
    say("  Freya will now start automatically every time")
    say("  Windows boots. No need to do anything else.")
    say("")
    say("  To start RIGHT NOW:  double-click START_FREYA.bat")
    say("  OR run:  venv\\Scripts\\pythonw.exe freya.py")
    say("")

if __name__ == "__main__":
    say("=" * 50)
    say("  Freya AI - Setup Wizard")
    say("=" * 50)
    create_venv()
    install_requirements()
    install_playwright()
    download_wakeword_models()
    create_directories()
    register_startup()
    check_ollama()
    done()
