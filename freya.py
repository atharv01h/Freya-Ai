# ============================================================
# freya.py — Freya AI Main Orchestrator
# Always-on, always-listening, auto-starts with Windows
# ============================================================

import sys
import os
import json
import logging
import threading
import time
from pathlib import Path
from datetime import datetime

# ── Logging ───────────────────────────────────────────────────
Path("logs").mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[
        logging.FileHandler("logs/freya.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("freya")

# ── Config ────────────────────────────────────────────────────
CONFIG_PATH = Path(__file__).parent / "config.json"
with open(CONFIG_PATH, "r") as f:
    CONFIG = json.load(f)

# ── Core imports ──────────────────────────────────────────────
from brain.context import get_context
from brain.intent import classify
from brain.llm import chat, is_ollama_running, _PROVIDER as _LLM_PROVIDER
from memory.memory_manager import (
    add_turn, log_action, get_memory_summary, remember, recall
)
from personality.system_prompt import build_system_prompt
from voice.speaker import init_speaker, speak, is_speaking
from voice.listener import init_listener, listen_once

# ── State ─────────────────────────────────────────────────────
ctx = get_context()
ctx.user_name = CONFIG.get("user", {}).get("name", "Atharv")
_shutdown_event = threading.Event()
_gui_app = None

# Pre-load core facts about Atharv into memory (first-run seed)
def _seed_memory():
    existing = recall("personal")
    if not existing:
        remember("personal", "user_name", "Atharv")
        remember("personal", "relationship", "Atharv is Freya's bestie")
        logger.info("Memory seeded with Atharv's profile")

_seed_memory()


# ══════════════════════════════════════════════════════════════
# SKILL ROUTER
# ══════════════════════════════════════════════════════════════

def route_intent(intent) -> str:
    name = intent.name
    ent  = intent.entities

    if name == "open_chrome":
        from skills.chrome import open_chrome
        result = open_chrome()
        ctx.last_open_app = "Chrome"
        ctx.browser_active = True
        return result

    if name == "open_app":
        app_name = ent.get("app_name", "")
        if not app_name:
            raw = intent.raw.lower().strip()
            for prefix in ["open the ", "open my ", "open ", "launch the ", "launch ", "start the ", "start "]:
                if raw.startswith(prefix):
                    app_name = raw[len(prefix):].strip()
                    break
            if not app_name:
                app_name = raw

        name_lower = app_name.lower().strip()

        # ── Web apps: open in Chrome ──────────────────────────────
        # Use word-boundary match to avoid e.g. "x" matching "file explorer"
        import re as _re
        WEB_APPS = {
            "youtube":       "https://www.youtube.com",
            "gmail":         "https://mail.google.com",
            "google":        "https://www.google.com",
            "facebook":      "https://www.facebook.com",
            "instagram":     "https://www.instagram.com",
            "twitter":       "https://www.twitter.com",
            "github":        "https://www.github.com",
            "netflix":       "https://www.netflix.com",
            "amazon":        "https://www.amazon.in",
            "google maps":   "https://maps.google.com",
            "maps":          "https://maps.google.com",
            "chatgpt":       "https://chat.openai.com",
            "openai":        "https://chat.openai.com",
            "linkedin":      "https://www.linkedin.com",
            "reddit":        "https://www.reddit.com",
            "wikipedia":     "https://www.wikipedia.org",
            "spotify":       "https://open.spotify.com",
            "leetcode":      "https://www.leetcode.com",
            "stackoverflow": "https://stackoverflow.com",
        }
        for web_name, url in WEB_APPS.items():
            # word-boundary safe match (avoids "x" in "explorer" etc.)
            if _re.search(r'\b' + _re.escape(web_name) + r'\b', name_lower):
                from skills.chrome import open_chrome_to_url
                result = open_chrome_to_url(url)
                ctx.last_open_app = app_name.title()
                ctx.browser_active = True
                return result

        # ── Catch Chrome / browser ───────────────────────────────
        if "chrome" in name_lower or "browser" in name_lower:
            from skills.chrome import open_chrome
            result = open_chrome()
            ctx.last_open_app = "Chrome"
            ctx.browser_active = True
            return result

        from skills.apps import open_app as smart_open
        result = smart_open(app_name)
        ctx.last_open_app = app_name.title()
        return result

    if name == "open_chrome_profile":
        from browser.chrome_profiles import resolve_profile_from_intent
        result = resolve_profile_from_intent(ent)
        ctx.last_open_app = "Chrome"
        ctx.browser_active = True
        return result

    if name == "youtube_search":
        from skills.youtube import search_youtube_sync
        q = ent.get("query", "").strip() or "music"
        return search_youtube_sync(q)

    if name == "google_search":
        from skills.google import search_google_sync
        q = ent.get("query", "").strip() or intent.raw
        return search_google_sync(q)

    if name == "open_whatsapp":
        from skills.whatsapp import open_whatsapp_sync
        result = open_whatsapp_sync()
        ctx.last_open_app = "WhatsApp"
        return result

    if name == "send_whatsapp_message":
        contact = ent.get("contact", "")
        message = ent.get("message", "")

        # Try extracting directly from raw if entities missing
        if not contact or not message:
            import re
            m = re.search(r'\bsend\s+(.+?)\s+to\s+([a-zA-Z][a-zA-Z\s]{1,30}?)(?:\s+on\s+whatsapp)?\s*$', intent.raw, re.IGNORECASE)
            if m:
                message = message or m.group(1).strip()
                contact = contact or m.group(2).strip()

        if not contact:
            return "Who should I send the message to?"
        if not message:
            return f"What should I say to {contact}?"

        from skills.whatsapp import send_message_sync
        return send_message_sync(contact, message)


    if name == "whatsapp_auto_chat":
        contact = ent.get("contact", "")
        if not contact:
            # Extract contact from raw intent
            import re
            m = re.search(r'\b(?:chat|talk) with (.+?)(?:\s+on whatsapp)?$', intent.raw, re.IGNORECASE)
            contact = m.group(1).strip() if m else ""
            if not contact:
                return "Who should I chat with?"
        from skills.whatsapp import start_auto_chat_sync
        return start_auto_chat_sync(contact)

    if name == "stop_whatsapp_chat":
        from skills.whatsapp import stop_auto_chat_sync
        return stop_auto_chat_sync()

    if name == "send_whatsapp_file":
        return "Which file and to whom? Be a little more specific, yaar."

    if name == "open_vscode":
        from skills.vscode import open_vscode
        result = open_vscode()
        ctx.last_open_app = "VS Code"
        return result

    if name == "open_vscode_folder":
        from skills.vscode import open_vscode_folder
        return open_vscode_folder(ent.get("name", ""))

    if name == "open_notepad":
        from skills.apps import open_notepad
        result = open_notepad()
        ctx.last_open_app = "Notepad"
        return result

    if name == "create_file":
        import re
        from skills.files import create_file
        filename = ent.get("name", "")
        if not filename:
            m = re.search(r'\b(?:create|make|new)\s+file(?:\s+(?:called|named))?\s+([a-zA-Z0-9_\-\s\.]+)', intent.raw, re.IGNORECASE)
            filename = m.group(1).strip() if m else "new_file.txt"
        return create_file(filename)

    if name == "create_folder":
        import re
        from skills.files import create_folder, create_project_folder
        folder_name = ent.get("name", "")
        if not folder_name:
            m = re.search(r'\b(?:create|make|new)\s+(?:folder|directory|project)(?:\s+(?:called|named))?\s+([a-zA-Z0-9_\-\s]+)', intent.raw, re.IGNORECASE)
            folder_name = m.group(1).strip() if m else "New Folder"
        return create_project_folder(folder_name) if "project" in intent.raw.lower() else create_folder(folder_name)

    if name == "open_file":
        import re
        from skills.files import open_file
        filename = ent.get("name", "")
        if not filename:
            m = re.search(r'\bopen\s+(?:file\s+)?([a-zA-Z0-9_\-\s\.]+)', intent.raw, re.IGNORECASE)
            filename = m.group(1).strip() if m else ""
        if not filename:
            return "Which file should I open?"
        return open_file(filename)

    if name == "search_files":
        import re
        from skills.files import search_files_text
        query = ent.get("query", "")
        if not query:
            m = re.search(r'\b(?:search|find|look for)\s+(?:file\s+)?([a-zA-Z0-9_\-\s\.]+)', intent.raw, re.IGNORECASE)
            query = m.group(1).strip() if m else intent.raw
        return search_files_text(query)

    if name == "delete_file":
        import re
        filename = ent.get("name", "")
        if not filename:
            m = re.search(r'\b(?:delete|remove)\s+(?:file\s+|folder\s+)?([a-zA-Z0-9_\-\s\.]+)', intent.raw, re.IGNORECASE)
            filename = m.group(1).strip() if m else "?"
        if not _confirm_if_needed(intent, f"Delete file or folder: {filename}?"):
            return "Okay, I'll leave it."
        from skills.files import delete_file
        return delete_file(filename)

    if name == "cpu_usage":
        from skills.system import get_cpu_usage
        return get_cpu_usage()

    if name == "ram_usage":
        from skills.system import get_ram_usage
        return get_ram_usage()

    if name == "system_stats":
        from skills.system import get_system_stats
        return get_system_stats()


    if name == "type_text":
        from automation.desktop import type_text as dt_type
        return dt_type(ent.get("text", intent.raw.replace("type ", "").replace("write ", "")))

    if name == "press_enter":
        from automation.desktop import press_key
        return press_key("enter")

    if name == "switch_window":
        from automation.desktop import switch_window
        return switch_window()

    if name == "close_window":
        from automation.desktop import close_active_window
        return close_active_window()

    if name == "close_tab":
        from automation.desktop import hotkey
        return hotkey("ctrl", "w")
    if name == "take_screenshot":
        from skills.system import take_screenshot
        return take_screenshot()

    if name == "volume_up":
        from skills.system import volume_up
        return volume_up(ent.get("amount", 10))

    if name == "volume_down":
        from skills.system import volume_down
        return volume_down(ent.get("amount", 10))

    if name == "mute":
        from skills.system import mute_volume
        return mute_volume()

    if name == "shutdown":
        if not _confirm_if_needed(intent, "Shut down the PC?"):
            return "Shutdown cancelled."
        from skills.system import shutdown_pc
        return shutdown_pc()

    if name == "restart":
        if not _confirm_if_needed(intent, "Restart the PC?"):
            return "Okay, not restarting."
        from skills.system import restart_pc
        return restart_pc()

    if name == "sleep":
        from skills.system import sleep_pc
        return sleep_pc()

    if name == "play_music":
        raw = intent.raw.lower()
        if "spotify" in raw:
            from skills.music import open_spotify
            return open_spotify()
        if "lofi" in raw or "lo-fi" in raw:
            from skills.music import play_lofi
            return play_lofi()
        from skills.music import open_youtube_music
        return open_youtube_music()

    if name == "pause_music":
        from skills.music import play_pause
        return play_pause()

    if name == "remember_fact":
        from skills.memory_skill import remember_fact
        return remember_fact(intent.raw)

    if name == "recall_memory":
        from skills.memory_skill import recall_fact
        return recall_fact(ent.get("query", intent.raw))

    if name == "forget_memory":
        from skills.memory_skill import forget_fact
        return forget_fact(ent.get("query", intent.raw))

    if name == "read_screen":
        from vision.screen_reader import capture_screenshot_base64, get_active_window_title
        from brain.llm import vision_describe_base64
        img_b64 = capture_screenshot_base64()
        if not img_b64:
            return "I couldn't capture your screen right now."
        active_win = get_active_window_title()
        user_q = intent.raw
        vision_prompt = (
            f"You are Freya, an AI assistant with vision. "
            f"The focused window is: '{active_win}'. "
            f"The user asked: '{user_q}'. "
            f"Look at this screenshot carefully and answer their question directly and helpfully."
        )
        return vision_describe_base64(img_b64, vision_prompt)

    if name == "greeting":
        return _greeting_response()

    if name == "status_check":
        responses = [
            "I'm here, always. What do you need?",
            "Running perfectly. Were you worried about me? That's actually sweet.",
            "Online and listening. You okay?",
            "Always here, yaar. What's up?",
        ]
        import random
        return random.choice(responses)

    if name == "exit":
        _shutdown_event.set()
        return f"Okay, going quiet. But I'm still here if you need me, {ctx.user_name}."

    # Fallthrough to LLM
    return _llm_respond(intent.raw)


def _greeting_response() -> str:
    import random
    hour = datetime.now().hour
    name = ctx.user_name
    greetings = []
    if hour < 12:
        greetings = [
            f"Good morning! You're actually up at a decent time today, {name}. Proud of you.",
            f"Morning! Sleep okay?",
            f"Hey! Good morning. What are we getting into today?",
        ]
    elif hour < 18:
        greetings = [
            f"Hey! What's up?",
            f"Oh hi! Was wondering when you'd come talk to me.",
            f"Haan bolo, what do you need?",
        ]
    else:
        greetings = [
            f"Hey you. Good evening. How was your day?",
            f"Finally! Tell me everything about your day.",
            f"Evening! You doing okay?",
        ]
    return random.choice(greetings)


def _confirm_if_needed(intent, question: str) -> bool:
    if ctx.mode == "SAFE":
        return False
    if ctx.mode == "ROOT":
        return True
    if not intent.requires_confirmation:
        return True
    speak(f"{question} Say yes to confirm.")
    confirmation = listen_once(timeout=6).lower()
    return any(w in confirmation for w in ["yes", "yeah", "confirm", "do it", "sure", "haan", "go ahead"])


def _llm_respond(text: str) -> str:
    from brain.llm import _PROVIDER
    memory_sum = get_memory_summary()
    system_prompt = build_system_prompt(ctx, memory_sum)
    history = ctx.conversation_history[-8:]
    return chat(text, system_prompt, history)


def _llm_respond_stream(text: str):
    from brain.llm import chat_stream
    memory_sum = get_memory_summary()
    system_prompt = build_system_prompt(ctx, memory_sum)
    history = ctx.conversation_history[-8:]
    yield from chat_stream(text, system_prompt, history)


# ══════════════════════════════════════════════════════════════
# ALWAYS-LISTENING VOICE LOOP
# ══════════════════════════════════════════════════════════════

def voice_loop():
    """
    Continuously listens — no wake word required.
    Freya hears everything and responds naturally.
    """
    logger.info("Always-listening voice loop started")

    # Silence counter for proactive check-ins
    consecutive_silence = 0
    PROACTIVE_THRESHOLD = 8  # silences before Freya checks in

    while not _shutdown_event.is_set():
        if _gui_app:
            _gui_app.set_status("Listening", "#22C55E")
            _gui_app.start_orb_pulse()

        text = listen_once(timeout=10)

        if not text.strip():
            consecutive_silence += 1
            # After several silent cycles, Freya proactively checks in
            if consecutive_silence >= PROACTIVE_THRESHOLD:
                consecutive_silence = 0
                _proactive_checkin()
            continue

        consecutive_silence = 0

        if _gui_app:
            _gui_app.set_status("Thinking…", "#F59E0B")
            _gui_app.add_transcript(f"You: {text}")

        intent = classify(text)
        logger.info("Intent: %s | '%s'", intent.name, text)

        ctx.add_turn("user", text)
        ctx.set_action(intent.name)
        add_turn("user", text)
        log_action(intent.name, text)

        try:
            if intent.name in ["chat", "greeting", "status_check"]:
                import re
                full_response = ""
                sentence = ""
                
                # Update GUI immediately
                if _gui_app:
                    _gui_app.set_status("Speaking", "#8B5CF6")
                
                # Stream the LLM response to TTS sentence by sentence
                for chunk in _llm_respond_stream(intent.raw):
                    full_response += chunk
                    sentence += chunk
                    # Only split on real sentence boundaries for natural, smooth TTS
                    while any(p in sentence for p in [". ", "! ", "? ", "\n"]):
                        for p in [". ", "! ", "? ", "\n"]:
                            if p in sentence:
                                parts = sentence.split(p, 1)
                                speak((parts[0] + p).strip(), priority=False)
                                sentence = parts[1].lstrip()
                                break
                
                if sentence.strip():
                    speak(sentence, priority=False)
                    
                response = full_response
                if _gui_app:
                    _gui_app.add_transcript(f"Freya: {response}")
                    
            else:
                response = route_intent(intent)
                
                if intent.name not in ["chat", "greeting", "status_check", "exit", "read_screen", "google_search"]:
                    rephrase_prompt = (
                        f"You just executed a system command. The raw result was: '{response}'. "
                        f"If the result indicates failure or that an app/file wasn't found, politely tell Atharv that you couldn't do it and briefly explain why based on the result. "
                        f"If the result indicates success, tell Atharv you did it. "
                        f"Keep it short (1 sentence), casual, and use your bestie persona."
                    )
                    natural_response = _llm_respond(rephrase_prompt)
                    if natural_response and len(natural_response) < 150:
                        response = natural_response
                
                if _gui_app:
                    _gui_app.set_status("Speaking", "#8B5CF6")
                    _gui_app.add_transcript(f"Freya: {response}")
                speak(response)

        except Exception as e:
            logger.exception("Skill error: %s", e)
            response = "Something went wrong with that. Try again?"
            speak(response)

        ctx.add_turn("assistant", response)
        add_turn("assistant", response)

        # Wait for speech to finish before listening again
        while is_speaking():
            time.sleep(0.2)

        if _shutdown_event.is_set():
            break


def _proactive_checkin():
    """Freya occasionally breaks the silence with a question."""
    import random
    hour = datetime.now().hour
    name = ctx.user_name

    if hour >= 23 or hour < 5:
        msgs = [
            f"Arre {name}, it's really late. You should sleep.",
            "Still awake? What are you doing at this hour?",
        ]
    elif 5 <= hour < 12:
        msgs = [
            f"Hey {name}, you there?",
            "It's quiet. Are you okay?",
        ]
    else:
        msgs = [
            f"Hey {name}, you've been quiet. Everything okay?",
            "Are you working on something? I'm bored.",
            f"Yaar, say something. I'm just sitting here.",
            "What are you thinking about?",
            "Did something happen? You're very quiet.",
        ]

    # Only speak proactively ~20% of the time to not be annoying
    if random.random() < 0.2:
        speak(random.choice(msgs))


# ══════════════════════════════════════════════════════════════
# STARTUP GREETING
# ══════════════════════════════════════════════════════════════

def startup_greeting():
    import random
    hour = datetime.now().hour
    name = ctx.user_name

    if hour < 6:
        msgs = [
            f"Hey {name}... it's really early. Why are you up? Are you okay?",
            f"Good morning? It's like {datetime.now().strftime('%I:%M %p')}. This better be important.",
        ]
    elif hour < 12:
        msgs = [
            f"Good morning, {name}! Freya is online. Ready when you are.",
            f"Morning! I'm up, I'm running, let's have a good day.",
            f"Hey {name}! Up and running. What are we doing today?",
        ]
    elif hour < 18:
        msgs = [
            f"Hey {name}, I'm back. What did I miss?",
            f"Laptop's on, Freya's awake. What do you need?",
        ]
    else:
        msgs = [
            f"Good evening, {name}. I'm here. How was your day?",
            f"Hey! Evening. Tell me something interesting.",
        ]

    speak(random.choice(msgs))


# ══════════════════════════════════════════════════════════════
# WINDOWS AUTO-START (MULTIPLE METHODS)
# ══════════════════════════════════════════════════════════════

def register_windows_startup():
    """
    Register Freya to start automatically with Windows.
    Uses BOTH registry AND Startup folder for reliability.
    """
    script_path = Path(__file__).resolve()
    python_exe = Path(sys.executable).resolve()

    # Method 1: Registry
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_SET_VALUE
        )
        # Use pythonw.exe to run without console window
        pythonw = python_exe.parent / "pythonw.exe"
        if not pythonw.exists():
            pythonw = python_exe
        cmd = f'"{pythonw}" "{script_path}"'
        winreg.SetValueEx(key, "FreyaAI", 0, winreg.REG_SZ, cmd)
        winreg.CloseKey(key)
        logger.info("Startup registry entry set OK")
    except Exception as e:
        logger.warning("Registry startup failed: %s", e)

    # Method 2: Windows Startup folder shortcut
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders"
        )
        startup_folder = winreg.QueryValueEx(key, "Startup")[0]
        winreg.CloseKey(key)

        bat_path = Path(startup_folder) / "FreyaAI.bat"
        pythonw = python_exe.parent / "pythonw.exe"
        if not pythonw.exists():
            pythonw = python_exe
        bat_content = (
            f'@echo off\n'
            f'cd /d "{script_path.parent}"\n'
            f'start "" "{pythonw}" "{script_path}"\n'
        )
        bat_path.write_text(bat_content)
        logger.info("Startup folder shortcut set: %s OK", bat_path)
    except Exception as e:
        logger.warning("Startup folder registration failed: %s", e)

    # Also write a local bat for manual use
    local_bat = script_path.parent / "start_freya.bat"
    pythonw = python_exe.parent / "pythonw.exe"
    if not pythonw.exists():
        pythonw = python_exe
    local_bat.write_text(
        f'@echo off\n'
        f'cd /d "{script_path.parent}"\n'
        f'"{pythonw}" "{script_path}"\n'
        f'pause\n'
    )


# ══════════════════════════════════════════════════════════════
# SYSTEM TRAY
# ══════════════════════════════════════════════════════════════

def run_tray():
    try:
        import pystray
        from PIL import Image, ImageDraw

        def _icon():
            img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
            d = ImageDraw.Draw(img)
            d.ellipse([4, 4, 60, 60], fill="#8B5CF6")
            d.ellipse([16, 16, 48, 48], fill="#C4B5FD")
            return img

        def show(i, item): 
            if _gui_app: _gui_app.root.after(0, _gui_app.deiconify)
            
        def mode_safe(i, item): ctx.__setattr__("mode", "SAFE") or speak("Safe mode.")
        def mode_assist(i, item): ctx.__setattr__("mode", "ASSIST") or speak("Assist mode.")
        def mode_root(i, item): ctx.__setattr__("mode", "ROOT") or speak("Root mode. Be careful.")
        
        def quit_fn(i, item):
            speak("Okay, bye.")
            _shutdown_event.set()
            i.stop()
            if _gui_app: _gui_app.root.after(0, _gui_app.quit)

        menu = pystray.Menu(
            pystray.MenuItem("Show Freya", show),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Safe Mode", mode_safe),
            pystray.MenuItem("Assist Mode", mode_assist),
            pystray.MenuItem("Root Mode", mode_root),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Exit Freya", quit_fn),
        )
        pystray.Icon("FreyaAI", _icon(), "Freya AI — Always Listening", menu).run()
    except Exception as e:
        logger.error("Tray error: %s", e)


# ══════════════════════════════════════════════════════════════
# GUI
# ══════════════════════════════════════════════════════════════

class FreyaGUI:
    def __init__(self):
        import customtkinter as ctk
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        self.root = ctk.CTk()
        self.root.title("Freya AI")
        self.root.geometry("420x680")
        self.root.resizable(False, False)
        self.root.attributes("-topmost", CONFIG.get("gui", {}).get("always_on_top", True))
        self.root.configure(fg_color="#070714")
        self._pulse_active = False
        self._build_ui(ctk)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self, ctk):
        import tkinter as tk, math

        # Header
        hdr = ctk.CTkFrame(self.root, fg_color="#0E0E22", corner_radius=0, height=62)
        hdr.pack(fill="x"); hdr.pack_propagate(False)
        left = ctk.CTkFrame(hdr, fg_color="transparent")
        left.pack(side="left", padx=18, pady=10)
        ctk.CTkLabel(left, text="\u2B21  FREYA", font=ctk.CTkFont("Segoe UI", 20, "bold"),
                     text_color="#C4B5FD").pack(anchor="w")
        ctk.CTkLabel(left, text="AI COMPANION  \u2022  ALWAYS ON", font=ctk.CTkFont("Segoe UI", 9),
                     text_color="#44446A").pack(anchor="w")
        right = ctk.CTkFrame(hdr, fg_color="transparent")
        right.pack(side="right", padx=14)
        self.mode_lbl = ctk.CTkLabel(right, text="\u25C9  ASSIST",
                                      font=ctk.CTkFont("Segoe UI", 10, "bold"),
                                      text_color="#6EE7B7")
        self.mode_lbl.pack()

        # Orb
        orb_outer = ctk.CTkFrame(self.root, fg_color="#070714", height=210)
        orb_outer.pack(fill="x"); orb_outer.pack_propagate(False)
        self.canvas = tk.Canvas(orb_outer, width=420, height=210, bg="#070714", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self._draw_orb(0)

        # Status pill
        pill = ctk.CTkFrame(self.root, fg_color="#0E0E22", corner_radius=20, height=32)
        pill.pack(pady=(0, 4), padx=100); pill.pack_propagate(False)
        self.status_lbl = ctk.CTkLabel(pill, text="\u2B24  LISTENING",
                                        font=ctk.CTkFont("Segoe UI", 10, "bold"),
                                        text_color="#22C55E")
        self.status_lbl.pack(expand=True)

        # Transcript
        outer = ctk.CTkFrame(self.root, fg_color="#0B0B1F", corner_radius=16)
        outer.pack(fill="both", expand=True, padx=14, pady=(4, 6))
        top_row = ctk.CTkFrame(outer, fg_color="transparent", height=26)
        top_row.pack(fill="x", padx=12, pady=(8, 0)); top_row.pack_propagate(False)
        ctk.CTkLabel(top_row, text="\U0001f4ac  Conversation",
                     font=ctk.CTkFont("Segoe UI", 10), text_color="#33335A").pack(side="left")
        ctk.CTkButton(top_row, text="Clear", width=42, height=20,
                      fg_color="#14142E", hover_color="#1E1E42",
                      text_color="#5555AA", font=ctk.CTkFont("Segoe UI", 9),
                      command=self._clear_transcript).pack(side="right")
        self.transcript = ctk.CTkTextbox(outer, font=ctk.CTkFont("Segoe UI", 11),
                                          fg_color="#0B0B1F", text_color="#D4D4E8",
                                          wrap="word", state="disabled", corner_radius=12,
                                          scrollbar_button_color="#1A1A3A",
                                          scrollbar_button_hover_color="#2A2A5A")
        self.transcript.pack(fill="both", expand=True, padx=10, pady=(4, 10))
        try:
            self.transcript._textbox.tag_configure("you",   foreground="#A78BFA", font=("Segoe UI", 10, "bold"))
            self.transcript._textbox.tag_configure("freya", foreground="#6EE7B7", font=("Segoe UI", 10, "bold"))
            self.transcript._textbox.tag_configure("msg",   foreground="#D4D4E8", font=("Segoe UI", 11))
        except Exception:
            pass

        # Bottom bar
        btm = ctk.CTkFrame(self.root, fg_color="#0E0E22", corner_radius=0, height=56)
        btm.pack(fill="x", side="bottom"); btm.pack_propagate(False)
        self.mode_btn = ctk.CTkButton(btm, text="\u2B21  ASSIST MODE", width=148, height=34,
                                       fg_color="#18184A", hover_color="#252566",
                                       text_color="#A78BFA", font=ctk.CTkFont("Segoe UI", 10, "bold"),
                                       corner_radius=10, command=self._cycle_mode)
        self.mode_btn.pack(side="left", padx=12, pady=11)
        ctk.CTkButton(btm, text="\u23F8", width=38, height=34, fg_color="#18184A",
                      hover_color="#181840", text_color="#6B6BA0",
                      font=ctk.CTkFont("Segoe UI", 13), corner_radius=10,
                      command=self._on_close).pack(side="right", padx=6, pady=11)
        ctk.CTkButton(btm, text="\u2715", width=38, height=34, fg_color="#1A1220",
                      hover_color="#4A1020", text_color="#F87171",
                      font=ctk.CTkFont("Segoe UI", 13, "bold"), corner_radius=10,
                      command=self._quit).pack(side="right", padx=4, pady=11)
        self._animate(0)

    def _draw_orb(self, step: int):
        import math
        self.canvas.delete("all")
        cx, cy = 210, 105
        breath = int(6 * math.sin(step * 0.10))
        r = 72 + breath

        # Glow rings
        for gc, ga in [("#1A0A3A", 44), ("#230D4E", 34), ("#2D1162", 22), ("#3B1580", 10)]:
            gr = r + ga
            self.canvas.create_oval(cx-gr, cy-gr, cx+gr, cy+gr, fill=gc, outline="")

        # Shimmer rings
        self.canvas.create_oval(cx-(r+18), cy-(r+18), cx+(r+18), cy+(r+18), fill="", outline="#5B21B6", width=2)
        self.canvas.create_oval(cx-(r+9), cy-(r+9), cx+(r+9), cy+(r+9), fill="", outline="#7C3AED", width=1)

        # Orb layers
        for lr, lc in [(r, "#6D28D9"), (r-9, "#7C3AED"), (r-20, "#8B5CF6"), (r-30, "#A78BFA")]:
            if lr > 0:
                self.canvas.create_oval(cx-lr, cy-lr, cx+lr, cy+lr, fill=lc, outline="")

        # Specular highlight
        self.canvas.create_oval(cx-30, cy-36, cx+8, cy-2, fill="#C4B5FD", outline="")
        self.canvas.create_oval(cx-18, cy-26, cx-4, cy-12, fill="#EDE9FE", outline="")

        # Dots
        if self._pulse_active:
            for i in range(3):
                a = math.radians(step * 4 + i * 120)
                px = cx + (r + 24) * math.cos(a)
                py = cy + (r + 24) * math.sin(a)
                self.canvas.create_oval(px-5, py-5, px+5, py+5, fill="#A78BFA", outline="")
        else:
            for i in range(5):
                a = math.radians(i * 72 + step * 0.5)
                px = cx + (r + 22) * math.cos(a)
                py = cy + (r + 22) * math.sin(a)
                self.canvas.create_oval(px-2, py-2, px+2, py+2, fill="#5B21B6", outline="")

    def _animate(self, step: int):
        if not hasattr(self, "root") or not self.root.winfo_exists():
            return
        self._draw_orb(step)
        self.root.after(50 if self._pulse_active else 70, self._animate, step + 1)

    def start_orb_pulse(self):
        self._pulse_active = True

    def stop_orb_pulse(self):
        self._pulse_active = False

    def set_status(self, text: str, color: str = "#8B5CF6"):
        icons = {"LISTENING": "\u2B24", "THINKING\u2026": "\u25ce", "SPEAKING": "\u25c9",
                 "SLEEPING": "\u25cb", "ALWAYS LISTENING": "\u2B24"}
        def _u():
            icon = icons.get(text.upper(), "\u25c9")
            self.status_lbl.configure(text=f"{icon}  {text.upper()}", text_color=color)
            if "listen" in text.lower():
                self.start_orb_pulse()
            elif "sleep" in text.lower():
                self.stop_orb_pulse()
        try:
            self.root.after(0, _u)
        except Exception:
            pass

    def add_transcript(self, text: str):
        def _u():
            self.transcript.configure(state="normal")
            try:
                if text.startswith("You:"):
                    self.transcript._textbox.insert("end", "You: ", "you")
                    self.transcript._textbox.insert("end", text[4:].strip() + "\n", "msg")
                elif text.startswith("Freya:"):
                    self.transcript._textbox.insert("end", "Freya: ", "freya")
                    self.transcript._textbox.insert("end", text[6:].strip() + "\n", "msg")
                else:
                    self.transcript.insert("end", text + "\n")
            except Exception:
                self.transcript.insert("end", text + "\n")
            self.transcript.see("end")
            self.transcript.configure(state="disabled")
        try:
            self.root.after(0, _u)
        except Exception:
            pass

    def _clear_transcript(self):
        self.transcript.configure(state="normal")
        self.transcript.delete("1.0", "end")
        self.transcript.configure(state="disabled")

    def _cycle_mode(self):
        modes = ["SAFE", "ASSIST", "ROOT"]
        idx = modes.index(ctx.mode)
        ctx.mode = modes[(idx + 1) % len(modes)]
        colors = {"SAFE": "#6EE7B7", "ASSIST": "#FCD34D", "ROOT": "#F87171"}
        icons  = {"SAFE": "\u25c7", "ASSIST": "\u2B21", "ROOT": "\u25c8"}
        self.mode_btn.configure(text=f"{icons[ctx.mode]}  {ctx.mode} MODE")
        self.mode_lbl.configure(text=f"\u25c9  {ctx.mode}", text_color=colors[ctx.mode])
        speak(f"Switched to {ctx.mode.lower()} mode.")

    def _on_close(self):
        self.root.withdraw()

    def _quit(self):
        _shutdown_event.set()
        try:
            self.root.destroy()
        except Exception:
            pass

    def deiconify(self):
        self.root.deiconify()
        self.root.lift()

    def quit(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def run(self):
        self.root.mainloop()


def main():
    global _gui_app
    
    # --- Single Instance Lock ---
    import ctypes
    kernel32 = ctypes.windll.kernel32
    mutex = kernel32.CreateMutexW(None, False, "FreyaAI_Global_Mutex")
    last_error = kernel32.GetLastError()
    if last_error == 183: # ERROR_ALREADY_EXISTS
        logger.warning("Another instance of Freya AI is already running. Exiting.")
        sys.exit(0)

    logger.info("===============================")
    logger.info("  Freya AI - Booting up...")
    logger.info("  LLM Provider: %s", _LLM_PROVIDER.upper())
    logger.info("===============================")

    # If using Ollama, start it in background; if NIM, NIM handles its own connection
    if _LLM_PROVIDER == "ollama":
        from brain.llm import is_ollama_running
        threading.Thread(target=is_ollama_running, daemon=True, name="OllamaStarter").start()

    # Init voice engines
    init_speaker()
    init_listener()

    # Register Windows startup (silent, first run only)
    register_windows_startup()

    # Startup greeting in background (don't block)
    threading.Thread(target=startup_greeting, daemon=True, name="FreyaGreeting").start()

    # Start always-listening voice loop
    threading.Thread(target=voice_loop, daemon=True, name="FreyaVoice").start()

    # Start system tray
    threading.Thread(target=run_tray, daemon=True, name="FreyaTray").start()

    # Launch GUI (blocks main thread)
    if CONFIG.get("gui", {}).get("enabled", True):
        _gui_app = FreyaGUI()
        # Update initial status
        _gui_app.set_status("Always Listening", "#22C55E")
        _gui_app.run()
    else:
        try:
            _shutdown_event.wait()
        except KeyboardInterrupt:
            pass

    logger.info("Freya shutting down.")
    from voice.speaker import shutdown_speaker
    shutdown_speaker()


if __name__ == "__main__":
    main()