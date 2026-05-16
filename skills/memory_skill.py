# ============================================================
# skills/memory_skill.py — Memory Command Interface
# "Remember that...", "What do you know about...", "Forget..."
# ============================================================

import logging
import re
from memory.memory_manager import remember, recall, forget, search_memory, get_memory_summary

logger = logging.getLogger("freya.skills.memory")

CATEGORY_MAP = {
    "like": "preference",
    "prefer": "preference",
    "favorite": "preference",
    "enjoy": "preference",
    "project": "project",
    "working on": "project",
    "habit": "habit",
    "usually": "habit",
    "always": "habit",
    "note": "note",
    "reminder": "note",
    "name": "personal",
    "called": "personal",
}


def _detect_category(text: str) -> str:
    text_lower = text.lower()
    for keyword, category in CATEGORY_MAP.items():
        if keyword in text_lower:
            return category
    return "note"


def remember_fact(raw_text: str) -> str:
    """Parse and store a fact from user speech."""
    # "remember that I like lo-fi music" → fact = "I like lo-fi music"
    fact = re.sub(r"\b(remember that|remember|make a note|note that|don.t forget|keep in mind)\b", "", raw_text, flags=re.IGNORECASE).strip()
    if not fact:
        return "What should I remember? Tell me the fact."
    category = _detect_category(fact)
    # Use a short key derived from fact
    key = fact[:40].strip().rstrip(".,!?")
    remember(category, key, fact)
    return f"Got it, I'll remember that."


def recall_fact(query: str) -> str:
    """Search memory for a query."""
    results = search_memory(query)
    if not results:
        return f"I don't have anything stored about '{query}'. Want me to remember something?"
    lines = [f"• {r['value']}" for r in results[:5]]
    return "Here's what I remember:\n" + "\n".join(lines)


def forget_fact(query: str) -> str:
    """Remove a memory matching query."""
    results = search_memory(query)
    if not results:
        return f"I couldn't find anything about '{query}' to forget."
    r = results[0]
    forget(r["category"], r["key"])
    return f"Forgotten: {r['value']}"


def what_i_know() -> str:
    """Return a summary of everything Freya knows."""
    summary = get_memory_summary()
    if not summary:
        return "I don't have much stored yet. Tell me things and I'll remember them!"
    return f"Here's what I know about you:\n{summary}"


def save_project(name: str, detail: str = "") -> str:
    remember("project", name, detail or name)
    return f"Project '{name}' saved to memory."


def save_habit(habit: str) -> str:
    key = habit[:40]
    remember("habit", key, habit)
    return f"Habit noted: {habit}"


def save_preference(pref: str) -> str:
    key = pref[:40]
    remember("preference", key, pref)
    return f"Preference saved: {pref}"
