# ============================================================
# voice/speaker.py — Freya AI TTS Engine
# Primary:  edge-tts (Microsoft Neural TTS — cloud, zero RAM)
#           → en-US-AriaNeural — very natural, expressive female
# Fallback: pyttsx3 (offline, Windows SAPI)
# Kokoro removed — too slow on CPU, too much RAM (500MB)
# ============================================================

import threading
import queue
import logging
import json
import re
import asyncio
import tempfile
import os
from pathlib import Path

logger = logging.getLogger("freya.speaker")

_CONFIG_PATH = Path(__file__).parent.parent / "config.json"
_config = {}
try:
    with open(_CONFIG_PATH) as f:
        _config = json.load(f)
except Exception:
    pass

_VOICE_CFG    = _config.get("voice", {})
_EDGE_VOICE   = _VOICE_CFG.get("edge_voice", "en-US-AriaNeural")
_EDGE_RATE    = _VOICE_CFG.get("edge_rate",  "+8%")    # slightly faster than default
_EDGE_PITCH   = _VOICE_CFG.get("edge_pitch", "+0Hz")

_speech_queue: queue.Queue = queue.Queue()
_speaking = False
_speaker_thread = None
_pygame_ready = False
_pyttsx3_engine = None


# ── pygame audio backend ──────────────────────────────────────

def _init_pygame() -> bool:
    global _pygame_ready
    try:
        import pygame
        pygame.mixer.pre_init(frequency=24000, size=-16, channels=1, buffer=512)
        pygame.mixer.init()
        _pygame_ready = True
        logger.info("pygame mixer ready OK")
        return True
    except Exception as e:
        logger.warning("pygame init failed: %s", e)
        return False


# ── edge-tts (Microsoft Neural TTS) ──────────────────────────

async def _edge_generate(text: str, output_path: str):
    import edge_tts
    communicate = edge_tts.Communicate(
        text,
        voice=_EDGE_VOICE,
        rate=_EDGE_RATE,
        pitch=_EDGE_PITCH,
    )
    await communicate.save(output_path)


def _speak_edge(text: str):
    global _pygame_ready
    tmp_path = None
    try:
        # Generate MP3 via edge-tts (streams from Microsoft servers — tiny latency)
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            tmp_path = f.name

        # Run async generation synchronously in this thread
        asyncio.run(_edge_generate(text, tmp_path))

        # Play via pygame (built-in MP3 decoder, no ffmpeg needed)
        if _pygame_ready:
            import pygame
            import time
            pygame.mixer.music.load(tmp_path)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                time.sleep(0.05)
        else:
            _speak_pyttsx3(text)

    except Exception as e:
        logger.error("edge-tts error: %s — falling back to pyttsx3", e)
        _speak_pyttsx3(text)
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass


# ── pyttsx3 fallback ──────────────────────────────────────────

def _init_pyttsx3():
    global _pyttsx3_engine
    try:
        import pyttsx3
        _pyttsx3_engine = pyttsx3.init()
        voices = _pyttsx3_engine.getProperty("voices")
        # Prefer Aria (Neural, Win11) > Zira > Hazel > any female > second voice
        preferred = ["aria", "zira", "hazel", "female", "woman"]
        picked = False
        for v in voices:
            vn = v.name.lower()
            if any(k in vn for k in preferred):
                _pyttsx3_engine.setProperty("voice", v.id)
                picked = True
                logger.info("pyttsx3 voice: %s", v.name)
                break
        if not picked and len(voices) > 1:
            _pyttsx3_engine.setProperty("voice", voices[1].id)
        _pyttsx3_engine.setProperty("rate", 185)
        _pyttsx3_engine.setProperty("volume", 1.0)
        logger.info("pyttsx3 fallback ready OK")
    except Exception as e:
        logger.error("pyttsx3 init failed: %s", e)


def _speak_pyttsx3(text: str):
    global _pyttsx3_engine
    try:
        if _pyttsx3_engine is None:
            _init_pyttsx3()
        _pyttsx3_engine.say(text)
        _pyttsx3_engine.runAndWait()
    except Exception as e:
        logger.error("pyttsx3 speak error: %s", e)


# ── Text cleaner ──────────────────────────────────────────────

def _clean(text: str) -> str:
    """Strip markdown, emojis, and junk before sending to TTS."""
    # Remove markdown
    text = re.sub(r"\*+", "", text)
    text = re.sub(r"#+\s?", "", text)
    text = re.sub(r"`[^`]*`", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
    # Remove emojis (non-ASCII that aren't Hindi/Marathi letters)
    text = re.sub(r"[^\x00-\x7F\u0900-\u097F]+", " ", text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


# ── Speaker worker thread ─────────────────────────────────────

def _worker():
    global _speaking
    while True:
        text = _speech_queue.get()
        if text is None:
            break
        _speaking = True
        try:
            _speak_edge(text)
        except Exception as e:
            logger.error("Speaker worker error: %s", e)
        finally:
            _speaking = False
        _speech_queue.task_done()


# ── Public API ────────────────────────────────────────────────

def init_speaker():
    global _speaker_thread
    _init_pygame()
    # Also init pyttsx3 as fallback (very fast, no download)
    _init_pyttsx3()
    _speaker_thread = threading.Thread(target=_worker, daemon=True, name="FreyaSpeaker")
    _speaker_thread.start()
    logger.info("Speaker ready — TTS: edge-tts (%s) via pygame", _EDGE_VOICE)


def speak(text: str, priority: bool = False):
    clean = _clean(text)
    if not clean:
        return
    if priority:
        # Clear queue on priority speak
        while not _speech_queue.empty():
            try:
                _speech_queue.get_nowait()
                _speech_queue.task_done()
            except queue.Empty:
                break
    _speech_queue.put(clean)


def is_speaking() -> bool:
    return _speaking or not _speech_queue.empty()


def stop_speaking():
    while not _speech_queue.empty():
        try:
            _speech_queue.get_nowait()
            _speech_queue.task_done()
        except queue.Empty:
            break
    try:
        import pygame
        if pygame.mixer.get_init():
            pygame.mixer.music.stop()
    except Exception:
        pass


def shutdown_speaker():
    _speech_queue.put(None)
    if _speaker_thread:
        _speaker_thread.join(timeout=3)
    try:
        import pygame
        pygame.mixer.quit()
    except Exception:
        pass
