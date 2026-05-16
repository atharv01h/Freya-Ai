# ============================================================
# voice/listener.py — Freya AI STT Engine
# Primary: faster-whisper (base.en, CPU int8)
# Fallback: SpeechRecognition
# ============================================================

import logging
import json
import time
import threading
from pathlib import Path
from typing import Optional

logger = logging.getLogger("freya.listener")

_CONFIG_PATH = Path(__file__).parent.parent / "config.json"
_config = {}
try:
    with open(_CONFIG_PATH) as f:
        _config = json.load(f)
except Exception:
    pass

_VOICE_CFG = _config.get("voice", {})
_WHISPER_MODEL = _VOICE_CFG.get("whisper_model", "base.en")
_WHISPER_DEVICE = _VOICE_CFG.get("whisper_device", "cpu")
_WHISPER_COMPUTE = _VOICE_CFG.get("whisper_compute_type", "int8")
_PREFERRED_STT = _config.get("user", {}).get("preferred_stt", "faster_whisper")
_SILENCE_DUR = _VOICE_CFG.get("silence_duration", 1.5)

_whisper_model = None
_whisper_available = False
_sr_recognizer = None
_listening_active = False
_listen_thread: Optional[threading.Thread] = None


# ─── Faster-Whisper ──────────────────────────────────────────

def _init_whisper():
    global _whisper_model, _whisper_available
    try:
        from faster_whisper import WhisperModel
        logger.info("Loading Whisper model '%s' on %s (%s)...", _WHISPER_MODEL, _WHISPER_DEVICE, _WHISPER_COMPUTE)
        _whisper_model = WhisperModel(_WHISPER_MODEL, device=_WHISPER_DEVICE, compute_type=_WHISPER_COMPUTE)
        _whisper_available = True
        logger.info("Faster-Whisper ready OK")
    except ImportError:
        logger.warning("faster-whisper not installed - using SpeechRecognition")
        _whisper_available = False
    except Exception as e:
        logger.warning("Whisper init failed (%s) - using SpeechRecognition", e)
        _whisper_available = False


def _transcribe_whisper(audio_data: bytes, sample_rate: int = 16000) -> str:
    """Transcribe raw PCM audio bytes with Whisper."""
    import numpy as np
    try:
        audio_np = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0

        # Reject near-silent audio immediately (RMS < 0.002)
        rms = float(np.sqrt(np.mean(audio_np ** 2)))
        if rms < 0.002:
            return ""

        segments, info = _whisper_model.transcribe(
            audio_np,
            language="en",               # Force English — no auto-detect
            task="transcribe",           # transcribe, NOT translate
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": int(_SILENCE_DUR * 1000)},
            condition_on_previous_text=False,
            no_speech_threshold=0.75,    # Stricter: 0.6 was too lenient
            log_prob_threshold=-0.7,     # Reject low-confidence tokens
            compression_ratio_threshold=2.0,
            beam_size=5,
        )

        parts = []
        for seg in segments:
            # Skip segments where Whisper itself flags no_speech
            if seg.no_speech_prob > 0.75:
                continue
            parts.append(seg.text)

        text = " ".join(parts).strip()

        # Final sanity: reject suspiciously short results from long audio
        words = text.split()
        if len(words) == 1 and len(audio_np) / sample_rate > 2.5:
            # Single word from 2.5+ seconds of audio is almost always a hallucination
            logger.debug("Rejected likely hallucination: '%s'", text)
            return ""

        return text

    except Exception as e:
        logger.error("Whisper transcribe error: %s", e)
        return ""


# ─── SpeechRecognition Fallback ──────────────────────────────

def _init_sr():
    global _sr_recognizer
    try:
        import speech_recognition as sr
        _sr_recognizer = sr.Recognizer()
        _sr_recognizer.energy_threshold = 300
        _sr_recognizer.dynamic_energy_threshold = True
        logger.info("SpeechRecognition fallback ready OK")
    except Exception as e:
        logger.error("SpeechRecognition init failed: %s", e)


def _listen_sr() -> str:
    """Listen using SpeechRecognition + Google, with VAD interruption."""
    import speech_recognition as sr
    import pyaudio
    import struct
    import math
    from voice.speaker import is_speaking, stop_speaking
    from collections import deque
    
    CHUNK = 1024
    RATE = 16000
    SILENCE_THRESHOLD = 500  # Adjust as needed
    SILENCE_CHUNKS = int(RATE / CHUNK * _SILENCE_DUR)  # Use config duration
    MAX_CHUNKS = int(RATE / CHUNK * 15)       # 15 seconds max

    pa = pyaudio.PyAudio()
    try:
        stream = pa.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=RATE,
            input=True,
            frames_per_buffer=CHUNK,
        )
    except Exception as e:
        logger.error("PyAudio open failed: %s", e)
        return ""

    frames = []
    pre_buffer = deque(maxlen=int(RATE / CHUNK * 0.5))
    silent_chunks = 0
    speaking_started = False

    try:
        logger.debug("SR: listening (interruptible)…")
        for _ in range(MAX_CHUNKS * 2): # Wait longer for start of speech
            data = stream.read(CHUNK, exception_on_overflow=False)
            rms = math.sqrt(sum(x**2 for x in struct.unpack(f"{CHUNK}h", data)) / CHUNK)

            if rms > SILENCE_THRESHOLD:
                if not speaking_started:
                    # Speech just started! Check if Freya is speaking
                    if is_speaking():
                        logger.info("User interrupted Freya!")
                        stop_speaking()
                    speaking_started = True
                    frames.extend(pre_buffer)
                silent_chunks = 0
                frames.append(data)
            else:
                if speaking_started:
                    silent_chunks += 1
                    frames.append(data)
                    if silent_chunks >= SILENCE_CHUNKS:
                        break
                else:
                    pre_buffer.append(data)

        if not frames:
            return ""

        audio_bytes = b"".join(frames)
        # Create sr.AudioData (16kHz, 16-bit, 1 channel = 2 bytes per sample)
        audio_data = sr.AudioData(audio_bytes, RATE, 2)
        
        text = _sr_recognizer.recognize_google(audio_data, language="en-IN")
        return text.strip()
    except sr.UnknownValueError:
        return ""
    except Exception as e:
        logger.error("SR listen error: %s", e)
        return ""
    finally:
        stream.stop_stream()
        stream.close()
        pa.terminate()


# ─── Microphone Capture ──────────────────────────────────────

def _capture_audio_pyaudio(max_seconds: int = 10, sample_rate: int = 16000) -> bytes:
    """Capture audio via PyAudio until silence or max duration."""
    import pyaudio
    import struct
    import math

    CHUNK = 1024
    SILENCE_THRESHOLD = 700   # Higher = ignores more background noise
    SILENCE_CHUNKS = int(sample_rate / CHUNK * _SILENCE_DUR)

    pa = pyaudio.PyAudio()
    stream = pa.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=sample_rate,
        input=True,
        frames_per_buffer=CHUNK,
    )

    frames = []
    silent_chunks = 0
    speaking_started = False

    for _ in range(int(sample_rate / CHUNK * max_seconds)):
        data = stream.read(CHUNK, exception_on_overflow=False)
        frames.append(data)

        rms = math.sqrt(sum(x**2 for x in struct.unpack(f"{CHUNK}h", data)) / CHUNK)

        if rms > SILENCE_THRESHOLD:
            speaking_started = True
            silent_chunks = 0
        elif speaking_started:
            silent_chunks += 1
            if silent_chunks >= SILENCE_CHUNKS:
                break

    stream.stop_stream()
    stream.close()
    pa.terminate()
    return b"".join(frames)


# ─── Public API ──────────────────────────────────────────────

def init_listener():
    """Initialize STT engines."""
    if _PREFERRED_STT == "faster_whisper":
        _init_whisper()
    if not _whisper_available:
        _init_sr()
    logger.info("Listener initialized (whisper=%s)", _whisper_available)


def listen_once(timeout: int = 10) -> str:
    """
    Listen for one utterance and return transcribed text.
    Uses Whisper if available, else SpeechRecognition.
    """
    logger.debug("listen_once started")

    if _whisper_available:
        try:
            audio_bytes = _capture_audio_pyaudio(max_seconds=timeout)
            text = _transcribe_whisper(audio_bytes)
            if text:
                logger.info("You: %s", text)
            return text
        except Exception as e:
            logger.error("Whisper listen failed: %s - using SR", e)

    # Fallback
    if _sr_recognizer is None:
        _init_sr()
    return _listen_sr()


def is_available() -> bool:
    return _whisper_available or _sr_recognizer is not None
