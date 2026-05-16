# ============================================================
# brain/context.py
# Freya AI — Session State & Context Manager
# Tracks: last_action, active_task, mode, conversation history
# ============================================================

from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


@dataclass
class FreyaContext:
    """Central session state for one Freya session."""

    # User identity
    user_name: str = "Atharv"

    # Conversation continuity
    conversation_history: list = field(default_factory=list)
    last_user_input: str = ""
    last_freya_response: str = ""

    # Task tracking
    last_action: str = ""
    active_task: str = ""
    last_skill: str = ""
    pending_confirmation: Optional[dict] = None

    # Operating mode
    mode: str = "ASSIST"   # SAFE | ASSIST | ROOT

    # Chrome session
    last_chrome_profile: str = "Default"

    # Browser / App session tracking
    browser_active: bool = False
    current_url: str = ""
    last_open_app: str = ""   # Track most recently opened app for context continuity

    # Emotional tone
    mood: str = "neutral"  # neutral | happy | focused | concerned

    # Timing
    session_start: str = field(default_factory=lambda: datetime.now().isoformat())
    last_interaction: str = field(default_factory=lambda: datetime.now().isoformat())

    def update_interaction(self):
        self.last_interaction = datetime.now().isoformat()

    def add_turn(self, role: str, content: str):
        """Add a message to in-memory conversation history (max 12 turns)."""
        self.conversation_history.append({"role": role, "content": content})
        if len(self.conversation_history) > 12:
            self.conversation_history = self.conversation_history[-12:]
        self.update_interaction()

    def set_action(self, action: str, skill: str = ""):
        self.last_action = action
        self.last_skill = skill
        self.update_interaction()

    def set_task(self, task: str):
        self.active_task = task
        self.update_interaction()

    def clear_task(self):
        self.active_task = ""

    def require_confirmation(self, action: str, callback_data: dict):
        """Flag a dangerous action that needs user confirmation."""
        self.pending_confirmation = {"action": action, "data": callback_data}

    def confirm(self) -> Optional[dict]:
        """Pop and return the pending confirmation."""
        c = self.pending_confirmation
        self.pending_confirmation = None
        return c

    def get_mode_label(self) -> str:
        return {"SAFE": "🛡 Safe", "ASSIST": "🤝 Assist", "ROOT": "⚡ Root"}.get(self.mode, self.mode)

    def is_allowed(self, action_category: str, config: dict) -> bool:
        """Check if an action is allowed in the current mode."""
        mode_map = {
            "SAFE": config.get("modes", {}).get("safe_actions", []),
            "ASSIST": config.get("modes", {}).get("safe_actions", []) + config.get("modes", {}).get("assist_actions", []),
            "ROOT": ["*"],
        }
        allowed = mode_map.get(self.mode, [])
        return "*" in allowed or action_category in allowed


# Global singleton context
_ctx: Optional[FreyaContext] = None


def get_context() -> FreyaContext:
    global _ctx
    if _ctx is None:
        _ctx = FreyaContext()
    return _ctx


def reset_context():
    global _ctx
    _ctx = FreyaContext()
