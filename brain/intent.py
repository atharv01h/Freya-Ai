# ============================================================
# brain/intent.py
# Freya AI — Intent Classifier & Command Router
# Maps user utterances → (intent, entities, skill_handler)
# No extra ML model — fast keyword+regex matching
# ============================================================

import re
import logging
from dataclasses import dataclass, field
from typing import Optional, Callable

logger = logging.getLogger("freya.intent")


@dataclass
class Intent:
    name: str
    entities: dict = field(default_factory=dict)
    confidence: float = 1.0
    raw: str = ""
    requires_confirmation: bool = False


# ─── Intent Patterns ──────────────────────────────────────────
# Each entry: (intent_name, patterns_list, entity_extractors, requires_confirm)

INTENT_PATTERNS = [
    # ── FILES & FOLDERS ───────────────────────────────────────
    ("create_file", [
        r"\bcreate.{0,10}file\b",
        r"\bmake.{0,10}file\b",
        r"\bnew file\b",
    ], {}, False),

    ("create_folder", [
        r"\bcreate.{0,10}(folder|directory)\b",
        r"\bmake.{0,10}(folder|directory)\b",
        r"\bnew folder\b",
        r"\bcreate.{0,30}project\b",
    ], {}, False),

    ("open_file", [
        r"\b(?:open|on).{0,30}\.(txt|pdf|docx|xlsx|py|java|cpp|html|css|js)\b",
        r"\b(?:open|on)\s+file\b(?!\s+explorer)",
    ], {}, False),

    ("delete_file", [
        r"\bdelete.{0,20}(file|folder)\b",
        r"\bremove.{0,20}(file|folder)\b",
    ], {}, True),

    ("search_files", [
        r"\bsearch.{0,20}files\b",
        r"\bfind.{0,10}file\b",
        r"\blook for\b.{0,20}file\b",
    ], {}, False),

    # --- DESKTOP AUTOMATION ---
    ("type_text", [
        r"\b(type|write|enter the text|input)\s+(.+)"
    ], {}, False),
    ("press_enter", [
        r"\b(press enter|hit enter|submit)\b"
    ], {}, False),
    ("switch_window", [
        r"\b(switch window|switch tab|next window|change window)\b"
    ], {}, False),
    ("close_tab", [
        r"\bclose.{0,30}(tab|tap)\b",
        r"\b(close tab|close this tab)\b"
    ], {}, False),
    ("close_window", [
        r"\b(close window|close this window|close app|close this)\b",
        r"^close$"
    ], {}, False),


    # ── CHROME / BROWSER ──────────────────────────────────────
    ("open_chrome", [
        r"\bopen chrome\b",
        r"\blaunch chrome\b",
        r"\bstart chrome\b",
    ], {}, False),

    ("open_chrome_profile", [
        r"\bopen\b.{0,15}\bprofile\b",
        r"\bswitch.{0,10}profile\b",
        r"\buse\b.{0,10}profile\b",
        r"\bchoose.{0,10}profile\b",
        r"\b(work|personal|default|school|gaming)\s+profile\b",
        r"\bthird profile\b",
        r"\bfirst profile\b",
        r"\bsecond profile\b",
    ], {}, False),

    # ── YOUTUBE ───────────────────────────────────────────────
    ("youtube_search", [
        r"\bsearch.{0,20}youtube\b",
        r"\byoutube.{0,10}search\b",
        r"\bplay.{0,30}on youtube\b",
        r"\bwatch.{0,30}on youtube\b",
        r"\bopen youtube\b",
    ], {}, False),

    # ── GOOGLE ────────────────────────────────────────────────
    ("google_search", [
        r"\bsearch google\b",
        r"\bgoogle.{0,10}search\b",
        r"\bsearch the web\b",
        r"\bgoogle for\b",
        r"\blook up\b",
    ], {}, False),

    # ── WHATSAPP ──────────────────────────────────────────────
    ("open_whatsapp", [
        r"\b(?:open|on)\s+whatsapp\b(?!\s+and\s+send)",
        r"\b(?:open|on)\s+wa\b(?!\s+and\s+send)",
    ], {}, False),

    ("send_whatsapp_message", [
        r"\bopen\s+whatsapp\s+and\s+send\b",
        r"\bsend.{0,30}(message|msg|text).{0,30}(to|on) whatsapp\b",
        r"\bmessage\b.{0,30}on whatsapp\b",
        r"\btext\b.{0,30}(on|via) whatsapp\b",
        r"\bwhatsapp.{0,20}(send|message)\b",
        # Direct: "send hi to Sneha" / "send good morning to Atharv" / "send hi to"
        r"\bsend\s+(?!a message|a msg|whatsapp|file|photo|pdf|image).{1,50}\s+to\b",
    ], {}, False),

    ("whatsapp_auto_chat", [
        r"\b(chat|start chatting|talk) with (.+) on whatsapp\b",
        r"\b(chat|start chatting|talk) with (.+)\b",
    ], {}, False),

    ("stop_whatsapp_chat", [
        r"\b(stop chatting|stop whatsapp chat|exit chat mode|leave chat)\b"
    ], {}, False),

    ("send_whatsapp_file", [
        r"\bsend.{0,30}(pdf|file|image|photo|document)\b",
        r"\bupload.{0,20}(to|on) whatsapp\b",
        r"\bshare.{0,20}(pdf|file|image)\b",
    ], {}, True),

    # ── VSCODE ────────────────────────────────────────────────
    ("open_vscode", [
        r"\bopen vscode\b",
        r"\bopen visual studio code\b",
        r"\blaunch vscode\b",
        r"\bopen vs code\b",
        r"\bstart vscode\b",
    ], {}, False),

    ("open_vscode_folder", [
        r"\bopen.{0,30}(folder|project|directory).{0,20}(in|with|on) (vscode|vs code)\b",
        r"\bopen (vscode|vs code).{0,20}(folder|project)\b",
        r"\bvscode.{0,20}open\b",
    ], {}, False),

    # ── NOTEPAD / TEXT EDITOR ─────────────────────────────────
    ("open_notepad", [
        r"\bopen notepad\b",
        r"\blaunch notepad\b",
    ], {}, False),



    ("open_app", [
        r"\b(?:open|launch|start|on|show)\s+(?!chrome)([a-zA-Z0-9\s]+)\b",
    ], {}, False),

    # ── SYSTEM ────────────────────────────────────────────────
    ("cpu_usage", [
        r"\bcpu\b",
        r"\bprocessor\b",
        r"\bhow (busy|loaded) is\b",
    ], {}, False),

    ("ram_usage", [
        r"\bram\b",
        r"\bmemory usage\b",
        r"\bhow much memory\b",
    ], {}, False),

    ("system_stats", [
        r"\bsystem (stats|status|info)\b",
        r"\bhow is (the|my) (laptop|computer|system)\b",
        r"\bperformance\b",
    ], {}, False),

    ("volume_up", [
        r"\b(volume|sound).{0,10}(up|increase|louder|raise)\b",
        r"\bturn (up|louder)\b",
    ], {}, False),

    ("volume_down", [
        r"\b(volume|sound).{0,10}(down|decrease|quieter|lower)\b",
        r"\bturn (down|quieter)\b",
    ], {}, False),

    ("mute", [
        r"\bmute\b",
        r"\bsilence\b",
        r"\bturn off (sound|volume|audio)\b",
    ], {}, False),

    ("take_screenshot", [
        r"\btake (a )?screenshot\b",
        r"\bcapture (the )?screen\b",
        r"\bscreenshot\b",
    ], {}, False),

    ("shutdown", [
        r"\bshutdown\b",
        r"\bshut down\b",
        r"\bturn off (the |the laptop|computer|pc)\b",
        r"\bpower off\b",
    ], {}, True),

    ("restart", [
        r"\brestart\b",
        r"\breboot\b",
    ], {}, True),

    ("sleep", [
        r"\b(sleep|hibernate|suspend)\b.{0,15}(laptop|computer|pc)?\b",
        r"\bput.{0,10}(to sleep|into sleep)\b",
    ], {}, False),

    # ── MUSIC ─────────────────────────────────────────────────
    ("play_music", [
        r"\bplay (music|songs?|lo-?fi|playlist)\b",
        r"\bopen spotify\b",
        r"\bopen youtube music\b",
    ], {}, False),

    ("pause_music", [
        r"\b(pause|stop) (music|playing|song)\b",
        r"\bpause\b",
    ], {}, False),

    # ── MEMORY ────────────────────────────────────────────────
    ("remember_fact", [
        r"\bremember that\b",
        r"\bmake a note\b",
        r"\bnote that\b",
        r"\bdon.t forget\b",
        r"\bkeep in mind\b",
    ], {}, False),

    ("recall_memory", [
        r"\bwhat did (i|you) (say|tell you|mention)\b",
        r"\bdo you remember\b",
        r"\bwhat do you know about\b",
        r"\bwhat.s my\b",
    ], {}, False),

    ("forget_memory", [
        r"\bforget (that|about|it)\b",
        r"\bdelete (that|the note)\b",
    ], {}, False),

    # ── SCREEN / VISION ───────────────────────────────────────
    ("read_screen", [
        r"\bwhat.{0,15}(see|on screen|on the screen|screen say)\b",
        r"\bread (the )?screen\b",
        r"\bwhat.{0,10}open\b",
        r"\banalyze (the )?screen\b",
        r"\bcheck (the )?screen\b",
        r"\blook at (the )?screen\b",
        r"\bwhat.{0,10}(app|program|window)\b",
    ], {}, False),

    # ── GREETINGS / CHIT-CHAT ─────────────────────────────────
    ("greeting", [
        r"\b(hi|hello|hey|good morning|good evening|good afternoon|howdy)\b",
    ], {}, False),

    ("status_check", [
        r"\bhow are you\b",
        r"\bare you (there|awake|okay|ok)\b",
        r"\bwhat.{0,10}(doing|up to)\b",
    ], {}, False),

    ("exit", [
        r"\b(exit|quit|stop|goodbye|bye|shut up freya|sleep freya)\b",
    ], {}, False),
]


def classify(text: str) -> Intent:
    """
    Classify user input into an Intent.
    Returns Intent with name="chat" if no pattern matches.
    """
    text_lower = text.lower().strip()

    for intent_name, patterns, _, requires_confirm in INTENT_PATTERNS:
        for pattern in patterns:
            if re.search(pattern, text_lower):
                entities = _extract_entities(intent_name, text_lower)
                logger.debug("Intent matched: %s (pattern: %s)", intent_name, pattern)
                return Intent(
                    name=intent_name,
                    entities=entities,
                    confidence=0.9,
                    raw=text,
                    requires_confirmation=requires_confirm,
                )

    # No match → fall through to LLM chat
    return Intent(name="chat", entities={}, confidence=0.5, raw=text)


def _extract_entities(intent: str, text: str) -> dict:
    """Extract relevant entities from text based on intent."""
    entities = {}

    if intent == "type_text":
        m = re.search(r"\b(?:type|write|input)\s+(.+)", text)
        if m:
            entities["text"] = m.group(1).strip()
            

    if intent == "open_app":
        m = re.search(r"\b(?:open|launch|start|on|show)\s+(.+)", text)
        if m:
            entities["app_name"] = m.group(1).strip()
            
    if intent == "youtube_search":
        # "search radha krishna on youtube" → query = "radha krishna"
        q = re.sub(r"\b(search|play|watch|on youtube|youtube)\b", "", text).strip()
        entities["query"] = q.strip()

    elif intent == "google_search":
        q = re.sub(r"\b(search google|google|search the web|google for|look up|for)\b", "", text).strip()
        entities["query"] = q.strip()

    elif intent == "open_chrome_profile":
        # Extract profile name or ordinal
        ordinal_map = {"first": "1", "second": "2", "third": "3", "fourth": "4", "fifth": "5"}
        for word, num in ordinal_map.items():
            if word in text:
                entities["profile_ordinal"] = num
                break
        for name in ["work", "personal", "default", "school", "gaming"]:
            if name in text:
                entities["profile_name"] = name
                break

    elif intent == "send_whatsapp_message":
        # Format 1: send <message> to <contact>
        m1 = re.search(r"\bsend\s+(.+?)\s+to\s+([a-zA-Z0-9\s]+)$", text, re.IGNORECASE)
        # Format 2: send a message to <contact> saying <message>
        m2 = re.search(r"(?:to|message|text)\s+([a-zA-Z0-9\s]+?)(?:\s+(?:saying|message|that|:)\s+(.+))?$", text, re.IGNORECASE)
        
        if m1 and not re.search(r"\b(message|msg|text)\b", m1.group(1)):
            entities["message"] = m1.group(1).strip()
            entities["contact"] = m1.group(2).strip()
        elif m2:
            entities["contact"] = m2.group(1).strip() if m2.group(1) else ""
            entities["message"] = m2.group(2).strip() if m2.group(2) else ""

    elif intent == "send_whatsapp_file":
        # Try to extract file path mention
        m = re.search(r"(send|upload|share)\s+(.+?)\s+(to|on|via)", text)
        if m:
            entities["file_mention"] = m.group(2).strip()

    elif intent in ("create_file", "create_folder"):
        # Extract name after "create file/folder"
        m = re.search(r"(?:create|make|new)\s+(?:file|folder|directory|project)?\s*(?:called|named?)?\s*([a-zA-Z0-9_\-\s\.]+)", text)
        if m:
            entities["name"] = m.group(1).strip()

    elif intent == "remember_fact":
        # "remember that I like lo-fi music" → fact = "I like lo-fi music"
        m = re.sub(r"\b(remember that|make a note|note that|don.t forget|keep in mind)\b", "", text).strip()
        entities["fact"] = m

    elif intent == "recall_memory":
        m = re.sub(r"\b(what did i say|what did you|do you remember|what do you know about|what.s my)\b", "", text).strip()
        entities["query"] = m

    elif intent == "volume_up":
        m = re.search(r"(\d+)\s*(?:percent|%)?", text)
        entities["amount"] = int(m.group(1)) if m else 10

    elif intent == "volume_down":
        m = re.search(r"(\d+)\s*(?:percent|%)?", text)
        entities["amount"] = int(m.group(1)) if m else 10

    return entities
