# ============================================================
# memory/memory_manager.py
# Freya AI — SQLite-backed Memory System
# Short-term (conversation), Long-term (habits/notes), Daily log
# ============================================================

import sqlite3
import json
import os
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "freya_memory.db"


def get_connection():
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create all tables if they don't exist."""
    conn = get_connection()
    c = conn.cursor()

    # Short-term: recent conversation turns
    c.execute("""
        CREATE TABLE IF NOT EXISTS short_term (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )
    """)

    # Long-term: user facts, habits, preferences
    c.execute("""
        CREATE TABLE IF NOT EXISTS long_term (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            UNIQUE(category, key)
        )
    """)

    # Daily activity log
    c.execute("""
        CREATE TABLE IF NOT EXISTS daily_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            action TEXT NOT NULL,
            detail TEXT,
            timestamp TEXT NOT NULL
        )
    """)

    # Session notes (temporary per-session)
    c.execute("""
        CREATE TABLE IF NOT EXISTS session_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            note TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


# ─── Short-Term Memory ────────────────────────────────────────

def add_turn(role: str, content: str):
    """Add a conversation turn (user or assistant)."""
    conn = get_connection()
    conn.execute(
        "INSERT INTO short_term (role, content, timestamp) VALUES (?, ?, ?)",
        (role, content, _now())
    )
    conn.commit()
    conn.close()


def get_recent_turns(limit: int = 10) -> list[dict]:
    """Get the N most recent conversation turns."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT role, content, timestamp FROM short_term ORDER BY id DESC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in reversed(rows)]


def clear_short_term():
    """Wipe conversation history."""
    conn = get_connection()
    conn.execute("DELETE FROM short_term")
    conn.commit()
    conn.close()


# ─── Long-Term Memory ─────────────────────────────────────────

def remember(category: str, key: str, value: str):
    """Store or update a long-term memory fact."""
    conn = get_connection()
    conn.execute(
        """INSERT INTO long_term (category, key, value, timestamp)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(category, key) DO UPDATE SET value=excluded.value, timestamp=excluded.timestamp""",
        (category, key, value, _now())
    )
    conn.commit()
    conn.close()


def recall(category: str = None, key: str = None) -> list[dict]:
    """Retrieve long-term memories, optionally filtered."""
    conn = get_connection()
    if category and key:
        rows = conn.execute(
            "SELECT * FROM long_term WHERE category=? AND key=?", (category, key)
        ).fetchall()
    elif category:
        rows = conn.execute(
            "SELECT * FROM long_term WHERE category=?", (category,)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM long_term ORDER BY timestamp DESC LIMIT 50").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def forget(category: str, key: str):
    """Remove a specific memory."""
    conn = get_connection()
    conn.execute("DELETE FROM long_term WHERE category=? AND key=?", (category, key))
    conn.commit()
    conn.close()


def search_memory(query: str) -> list[dict]:
    """Fuzzy search across all long-term memories."""
    conn = get_connection()
    q = f"%{query.lower()}%"
    rows = conn.execute(
        "SELECT * FROM long_term WHERE LOWER(key) LIKE ? OR LOWER(value) LIKE ? LIMIT 10",
        (q, q)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_memory_summary() -> str:
    """Build a compact summary of key memories for LLM injection."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT category, key, value FROM long_term ORDER BY timestamp DESC LIMIT 20"
    ).fetchall()
    conn.close()

    if not rows:
        return ""

    lines = []
    for r in rows:
        lines.append(f"[{r['category']}] {r['key']}: {r['value']}")
    return "\n".join(lines)


# ─── Daily Log ────────────────────────────────────────────────

def log_action(action: str, detail: str = ""):
    """Log an action taken today."""
    conn = get_connection()
    conn.execute(
        "INSERT INTO daily_log (date, action, detail, timestamp) VALUES (?, ?, ?, ?)",
        (datetime.now().strftime("%Y-%m-%d"), action, detail, _now())
    )
    conn.commit()
    conn.close()


def get_today_log() -> list[dict]:
    today = datetime.now().strftime("%Y-%m-%d")
    conn = get_connection()
    rows = conn.execute(
        "SELECT action, detail, timestamp FROM daily_log WHERE date=? ORDER BY id DESC LIMIT 30",
        (today,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─── Sync memory.json snapshot ────────────────────────────────

def sync_json_snapshot(json_path: str = "memory.json"):
    """Keep memory.json in sync as a human-readable snapshot."""
    data = {
        "name": "Atharv",
        "last_updated": _now(),
        "notes": [r["value"] for r in recall("note")],
        "habits": [r["value"] for r in recall("habit")],
        "projects": [r["value"] for r in recall("project")],
        "preferences": {r["key"]: r["value"] for r in recall("preference")},
    }
    with open(json_path, "w") as f:
        json.dump(data, f, indent=2)


# ─── Helpers ──────────────────────────────────────────────────

def _now() -> str:
    return datetime.now().isoformat()


# Initialize on import
init_db()
