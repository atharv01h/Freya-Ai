# ============================================================
# brain/llm.py
# Freya AI — Multi-Provider LLM Engine
# Default: NVIDIA NIM (DeepSeek R1 via OpenAI-compatible API)
# Fallback: Ollama (local)
# Switch provider in config.json → "llm_provider": "nvidia_nim" | "ollama"
# ============================================================

import json
import logging
import httpx
import re
from typing import Generator
from pathlib import Path

logger = logging.getLogger("freya.llm")

# ── Load config ───────────────────────────────────────────────
_CONFIG_PATH = Path(__file__).parent.parent / "config.json"
_config = {}
try:
    with open(_CONFIG_PATH, "r") as f:
        _config = json.load(f)
except Exception:
    pass

# ── Provider selection ────────────────────────────────────────
_PROVIDER = _config.get("llm_provider", "nvidia_nim")

# ── NVIDIA NIM settings ───────────────────────────────────────
_NIM_CFG        = _config.get("nvidia_nim", {})
NIM_API_KEY     = _NIM_CFG.get("api_key", "")
NIM_BASE_URL    = _NIM_CFG.get("base_url", "https://integrate.api.nvidia.com/v1")
NIM_MODEL       = _NIM_CFG.get("model", "meta/llama-4-scout-17b-16e-instruct")
NIM_VISION_MODEL = _NIM_CFG.get("vision_model", "meta/llama-3.2-11b-vision-instruct")
NIM_TIMEOUT     = _NIM_CFG.get("timeout", 60)
NIM_MAX_TOKENS  = _NIM_CFG.get("max_tokens", 800)

# ── Ollama settings (fallback) ────────────────────────────────
_OLL_CFG      = _config.get("ollama", {})
OLLAMA_BASE   = _OLL_CFG.get("base_url", "http://localhost:11434")
OLLAMA_MODEL  = _OLL_CFG.get("model", "qwen2.5:3b")
VISION_MODEL  = _OLL_CFG.get("vision_model", "moondream")
OLLAMA_TIMEOUT = _OLL_CFG.get("timeout", 30)

MAX_TOKENS = _config.get("performance", {}).get("max_response_tokens", 300)

_NIM_HEADERS = {
    "Authorization": f"Bearer {NIM_API_KEY}",
    "Content-Type":  "application/json",
    "Accept":        "application/json",
}

_NIM_STREAM_HEADERS = {
    "Authorization": f"Bearer {NIM_API_KEY}",
    "Content-Type":  "application/json",
    "Accept":        "text/event-stream",
}


def _strip_thinking(text: str) -> str:
    """Remove <think>...</think> blocks from DeepSeek R1 responses."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    return text.strip()


# ══════════════════════════════════════════════════════════════
# NVIDIA NIM  (OpenAI-compatible endpoint)
# ══════════════════════════════════════════════════════════════

def _nim_chat(user_message: str, system_prompt: str, history: list[dict]) -> str:
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    payload = {
        "model": NIM_MODEL,
        "messages": messages,
        "max_tokens": NIM_MAX_TOKENS,
        "temperature": 0.7,
        "top_p": 0.9,
        "stream": False,
    }
    try:
        with httpx.Client(timeout=NIM_TIMEOUT) as client:
            resp = client.post(
                f"{NIM_BASE_URL}/chat/completions",
                headers=_NIM_HEADERS,
                json=payload,
            )
            resp.raise_for_status()
            raw = resp.json()["choices"][0]["message"]["content"]
            return _strip_thinking(raw)

    except httpx.HTTPStatusError as e:
        logger.error("NVIDIA NIM HTTP error %s: %s", e.response.status_code, e.response.text)
        return _ollama_chat(user_message, system_prompt, history)   # auto-fallback
    except httpx.ConnectError:
        logger.error("NVIDIA NIM unreachable — falling back to Ollama")
        return _ollama_chat(user_message, system_prompt, history)
    except httpx.TimeoutException:
        logger.error("NVIDIA NIM timed out after %ds", NIM_TIMEOUT)
        return "That took a bit too long. Try again?"
    except Exception as e:
        logger.error("NIM chat error: %s", e)
        return "Something went wrong on my end."


def _nim_chat_stream(user_message: str, system_prompt: str, history: list[dict]) -> Generator[str, None, None]:
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    payload = {
        "model": NIM_MODEL,
        "messages": messages,
        "max_tokens": NIM_MAX_TOKENS,
        "temperature": 0.7,
        "top_p": 0.9,
        "stream": True,
    }
    try:
        in_think_block = False
        buffer = ""
        with httpx.Client(timeout=NIM_TIMEOUT) as client:
            with client.stream(
                "POST",
                f"{NIM_BASE_URL}/chat/completions",
                headers=_NIM_STREAM_HEADERS,
                json=payload,
            ) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                        token = chunk["choices"][0].get("delta", {}).get("content", "")
                        if not token:
                            continue

                        # Strip <think> blocks in-stream so TTS skips reasoning text
                        buffer += token
                        while True:
                            if in_think_block:
                                end = buffer.find("</think>")
                                if end != -1:
                                    buffer = buffer[end + 8:]
                                    in_think_block = False
                                else:
                                    buffer = ""
                                    break
                            else:
                                start = buffer.find("<think>")
                                if start != -1:
                                    yield buffer[:start]
                                    buffer = buffer[start + 7:]
                                    in_think_block = True
                                else:
                                    yield buffer
                                    buffer = ""
                                    break
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue

    except (httpx.ConnectError, httpx.HTTPStatusError):
        logger.warning("NIM stream failed — falling back to Ollama stream")
        yield from _ollama_chat_stream(user_message, system_prompt, history)
    except Exception as e:
        logger.error("NIM stream error: %s", e)
        yield "Something went wrong."


# ══════════════════════════════════════════════════════════════
# OLLAMA (local fallback)
# ══════════════════════════════════════════════════════════════

def _ollama_chat(user_message: str, system_prompt: str, history: list[dict]) -> str:
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    payload = {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": False,
        "options": {
            "num_predict": MAX_TOKENS,
            "temperature": 0.85,
            "top_p": 0.9,
        }
    }
    try:
        with httpx.Client(timeout=OLLAMA_TIMEOUT) as client:
            resp = client.post(f"{OLLAMA_BASE}/api/chat", json=payload)
            resp.raise_for_status()
            return resp.json().get("message", {}).get("content", "").strip()
    except httpx.ConnectError:
        logger.error("Ollama not running — cannot reach %s", OLLAMA_BASE)
        return "I can't reach the AI right now. Check if Ollama is running."
    except httpx.TimeoutException:
        return "That took too long — timed out."
    except Exception as e:
        logger.error("Ollama chat error: %s", e)
        return "Something went wrong on my end."


def _ollama_chat_stream(user_message: str, system_prompt: str, history: list[dict]) -> Generator[str, None, None]:
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    payload = {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": True,
        "options": {
            "num_predict": MAX_TOKENS,
            "temperature": 0.85,
            "top_p": 0.9,
        }
    }
    try:
        with httpx.Client(timeout=OLLAMA_TIMEOUT) as client:
            with client.stream("POST", f"{OLLAMA_BASE}/api/chat", json=payload) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if line:
                        try:
                            chunk = json.loads(line)
                            token = chunk.get("message", {}).get("content", "")
                            if token:
                                yield token
                            if chunk.get("done"):
                                break
                        except json.JSONDecodeError:
                            continue
    except httpx.ConnectError:
        yield "Ollama isn't running either."
    except Exception as e:
        logger.error("Ollama stream error: %s", e)
        yield "Something went wrong."


# ══════════════════════════════════════════════════════════════
# PUBLIC API  — used by freya.py
# ══════════════════════════════════════════════════════════════

def chat(user_message: str, system_prompt: str, history: list[dict], stream: bool = False) -> str:
    """Send a chat request to the active provider. Returns full response text."""
    if _PROVIDER == "nvidia_nim":
        return _nim_chat(user_message, system_prompt, history)
    return _ollama_chat(user_message, system_prompt, history)


def chat_stream(user_message: str, system_prompt: str, history: list[dict]) -> Generator[str, None, None]:
    """Streaming chat — yields text chunks. Used for real-time sentence-by-sentence TTS."""
    if _PROVIDER == "nvidia_nim":
        yield from _nim_chat_stream(user_message, system_prompt, history)
    else:
        yield from _ollama_chat_stream(user_message, system_prompt, history)


def vision_describe(image_path: str, prompt: str = "What do you see on this screen? Describe in detail.") -> str:
    """
    Send a screenshot to NVIDIA NIM multimodal model and get a description.
    Falls back to Ollama Moondream if NIM is unavailable.
    """
    import base64
    try:
        with open(image_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode()

        # NIM vision — image sent as base64 data URL in content array
        payload = {
            "model": NIM_VISION_MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{img_b64}"
                            }
                        }
                    ]
                }
            ],
            "max_tokens": 600,
            "temperature": 0.3,
        }

        with httpx.Client(timeout=NIM_TIMEOUT) as client:
            resp = client.post(
                f"{NIM_BASE_URL}/chat/completions",
                headers=_NIM_HEADERS,
                json=payload,
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip()

    except httpx.HTTPStatusError as e:
        logger.error("NIM vision HTTP error %s: %s", e.response.status_code, e.response.text[:300])
        # Fallback to Ollama Moondream
        return _ollama_vision_describe(image_path, prompt)
    except Exception as e:
        logger.error("NIM vision error: %s", e)
        return _ollama_vision_describe(image_path, prompt)


def _ollama_vision_describe(image_path: str, prompt: str) -> str:
    """Ollama Moondream fallback for vision."""
    import base64
    try:
        with open(image_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode()
        payload = {
            "model": VISION_MODEL,
            "messages": [{"role": "user", "content": prompt, "images": [img_b64]}],
            "stream": False,
        }
        with httpx.Client(timeout=45) as client:
            resp = client.post(f"{OLLAMA_BASE}/api/chat", json=payload)
            resp.raise_for_status()
            return resp.json().get("message", {}).get("content", "").strip()
    except Exception as e:
        logger.error("Ollama vision fallback error: %s", e)
        return "I couldn't see the screen right now."


def vision_describe_base64(img_b64: str, prompt: str = "What do you see on this screen?") -> str:
    """
    Send a base64-encoded screenshot to NIM vision model.
    Called by vision/screen_reader.py — no file path needed.
    """
    payload = {
        "model": NIM_VISION_MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{img_b64}"}
                    }
                ]
            }
        ],
        "max_tokens": 600,
        "temperature": 0.3,
    }
    try:
        with httpx.Client(timeout=NIM_TIMEOUT) as client:
            resp = client.post(
                f"{NIM_BASE_URL}/chat/completions",
                headers=_NIM_HEADERS,
                json=payload,
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip()
    except httpx.HTTPStatusError as e:
        logger.error("NIM vision_base64 HTTP %s: %s", e.response.status_code, e.response.text[:200])
        return "I had trouble seeing the screen. Try again?"
    except Exception as e:
        logger.error("vision_describe_base64 error: %s", e)
        return "Vision failed."


def is_ollama_running() -> bool:
    """Health-check for Ollama. If offline, attempts to auto-start it."""
    try:
        with httpx.Client(timeout=3) as client:
            r = client.get(f"{OLLAMA_BASE}/api/tags")
            return r.status_code == 200
    except Exception:
        try:
            import subprocess
            subprocess.Popen(["ollama", "serve"], creationflags=subprocess.CREATE_NO_WINDOW)
        except Exception:
            pass
        return False


def is_nim_reachable() -> bool:
    """Quick check that NVIDIA NIM API key is set and endpoint responds."""
    if not NIM_API_KEY:
        return False
    try:
        with httpx.Client(timeout=5) as client:
            r = client.get(f"{NIM_BASE_URL}/models", headers=_NIM_HEADERS)
            return r.status_code == 200
    except Exception:
        return False
