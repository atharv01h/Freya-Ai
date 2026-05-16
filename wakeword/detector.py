# ============================================================
# wakeword/detector.py — Freya AI Wake Word Detection
# Hybrid: OpenWakeWord for broad detection
#         + Whisper confirmation for "Freya" / "Hey Freya"
# Also supports hotkey: Ctrl+Space
# ============================================================

import threading
import logging
import time
import queue
from typing import Callable, Optional

logger = logging.getLogger("freya.wakeword")

_WAKE_KEYWORDS = ["hey freya", "freya", "hi freya"]
_SENSITIVITY = 0.55
_openwakeword_available = False
_running = False
_callback: Optional[Callable] = None
_wake_queue: queue.Queue = queue.Queue()

# ─── OpenWakeWord ────────────────────────────────────────────

def _init_openwakeword():
    global _openwakeword_available
    try:
        import openwakeword
        from openwakeword.model import Model
        openwakeword.utils.download_models()
        _openwakeword_available = True
        logger.info("OpenWakeWord available ✓")
        return True
    except ImportError:
        logger.warning("openwakeword not installed")
        return False
    except Exception as e:
        logger.warning("OpenWakeWord init error: %s", e)
        return False


def _oww_listen_loop(on_wake: Callable):
    """Continuous microphone loop using OpenWakeWord."""
    try:
        import pyaudio
        import numpy as np
        from openwakeword.model import Model

        oww = Model(wakeword_models=["hey_jarvis"], inference_framework="onnx")
        CHUNK = 1280
        RATE = 16000

        pa = pyaudio.PyAudio()
        stream = pa.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=RATE,
            input=True,
            frames_per_buffer=CHUNK,
        )
        logger.info("OWW listening for wake word…")

        while _running:
            data = stream.read(CHUNK, exception_on_overflow=False)
            audio_np = np.frombuffer(data, dtype=np.int16)
            prediction = oww.predict(audio_np)

            for mdl, score in prediction.items():
                if score > _SENSITIVITY:
                    logger.info("Wake word triggered! (model=%s score=%.2f)", mdl, score)
                    stream.stop_stream()
                    on_wake()
                    time.sleep(2.0)  # debounce
                    stream.start_stream()
                    break

        stream.stop_stream()
        stream.close()
        pa.terminate()

    except Exception as e:
        logger.error("OWW listen loop crashed: %s", e)
        _fallback_keyword_loop(on_wake)


# ─── Fallback: keyword-in-whisper loop ───────────────────────

def _fallback_keyword_loop(on_wake: Callable):
    """
    Lightweight fallback: capture short audio chunks,
    transcribe with Whisper, check for wake keywords.
    """
    logger.info("Using Whisper keyword fallback for wake detection…")
    try:
        from faster_whisper import WhisperModel
        import pyaudio
        import numpy as np

        model = WhisperModel("tiny.en", device="cpu", compute_type="int8")
        CHUNK = 1024
        RATE = 16000
        RECORD_SECS = 2

        pa = pyaudio.PyAudio()
        stream = pa.open(
            format=pyaudio.paInt16, channels=1,
            rate=RATE, input=True, frames_per_buffer=CHUNK
        )

        frames_needed = int(RATE / CHUNK * RECORD_SECS)
        logger.info("Whisper wake-word fallback listening…")

        while _running:
            frames = [stream.read(CHUNK, exception_on_overflow=False) for _ in range(frames_needed)]
            audio_np = np.frombuffer(b"".join(frames), dtype=np.int16).astype(np.float32) / 32768.0

            segments, _ = model.transcribe(audio_np, language="en", vad_filter=True)
            text = " ".join(s.text for s in segments).lower().strip()

            if any(kw in text for kw in _WAKE_KEYWORDS):
                logger.info("Whisper wake keyword detected in: '%s'", text)
                stream.stop_stream()
                on_wake()
                time.sleep(2.0)
                stream.start_stream()

        stream.stop_stream()
        stream.close()
        pa.terminate()

    except Exception as e:
        logger.error("Whisper fallback crashed: %s — using hotkey only", e)


# ─── Hotkey Listener (Ctrl+Space) ────────────────────────────

def _hotkey_listener(on_wake: Callable):
    """Register Ctrl+Space as a wake hotkey using pynput."""
    try:
        from pynput import keyboard

        combo = {keyboard.Key.ctrl_l, keyboard.KeyCode(char=" ")}
        combo_r = {keyboard.Key.ctrl_r, keyboard.KeyCode(char=" ")}
        pressed = set()

        def on_press(key):
            pressed.add(key)
            if pressed >= combo or pressed >= combo_r:
                logger.info("Hotkey wake triggered (Ctrl+Space)")
                on_wake()

        def on_release(key):
            pressed.discard(key)

        with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
            while _running:
                time.sleep(0.1)

    except Exception as e:
        logger.error("Hotkey listener error: %s", e)


# ─── Public API ──────────────────────────────────────────────

def start(on_wake: Callable, use_hotkey: bool = True):
    """
    Start wake word detection in background threads.
    on_wake: called when wake word is detected.
    """
    global _running, _callback
    _running = True
    _callback = on_wake

    # Hotkey thread (always enabled)
    if use_hotkey:
        t_hotkey = threading.Thread(
            target=_hotkey_listener, args=(on_wake,),
            daemon=True, name="FreyaHotkey"
        )
        t_hotkey.start()
        logger.info("Hotkey wake (Ctrl+Space) active")

    # Wake word detection thread
    if _init_openwakeword():
        t_oww = threading.Thread(
            target=_oww_listen_loop, args=(on_wake,),
            daemon=True, name="FreyaWakeWord"
        )
        t_oww.start()
    else:
        t_fallback = threading.Thread(
            target=_fallback_keyword_loop, args=(on_wake,),
            daemon=True, name="FreyaWakeFallback"
        )
        t_fallback.start()


def stop():
    global _running
    _running = False
    logger.info("Wake word detector stopped")
