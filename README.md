<div align="center">
  <img src="https://img.shields.io/badge/Status-In%20Development-orange?style=for-the-badge" alt="Status Badge"/>
  <img src="https://img.shields.io/badge/Python-3.11%2B-blue?style=for-the-badge&logo=python" alt="Python Badge"/>
  <img src="https://img.shields.io/badge/Platform-Windows-0078D6?style=for-the-badge&logo=windows" alt="Windows Badge"/>
  <img src="https://img.shields.io/badge/AI-Llama_4_%7C_DeepSeek_%7C_Ollama-7C3AED?style=for-the-badge&logo=openai" alt="AI Badge"/>
</div>

<br>

<div align="center">
  <h1 align="center">⬡ Freya AI Companion</h1>
  <p align="center">
    <strong>A next-generation, voice-first desktop AI assistant with deep system automation, real WhatsApp integration, and a stunning animated UI.</strong>
  </p>
</div>

<p align="center">
  <a href="#sparkles-features">Features</a> •
  <a href="#rocket-quick-start">Quick Start</a> •
  <a href="#brain-how-she-works">How She Works</a> •
  <a href="#warning-known-issues">Known Issues</a> •
  <a href="#heart-creator">Creator</a>
</p>

---

## :sparkles: Features

Freya is not just a chatbot. She is a fully autonomous desktop entity that can see, listen, and physically interact with your computer. 

* **🎙️ Always-On Voice Engine:** Ultra-fast offline STT (Faster-Whisper/SpeechRecognition) combined with Microsoft Edge TTS for zero-latency, natural, human-like voice streaming.
* **🌐 True WhatsApp Automation:** Freya uses a persistent Playwright browser profile. Just say *"Send hi to Atharv"*, and she will autonomously open WhatsApp, find the contact, and send the message—no repeated QR scans required!
* **💻 Deep Desktop Control:** She can launch apps, create specific project folders, search for files, open VS Code, read your CPU/RAM usage, and natively interact with Windows File Explorer. 
* **🧠 Multi-Model Intelligence:** Powered by **NVIDIA NIM** (Llama 4 / DeepSeek R1) for hyper-fast logical reasoning, with a seamless fallback to local **Ollama** models if the internet goes down.
* **🎨 Premium Glassmorphism UI:** A sleek, always-on-top deep space GUI featuring a dynamic, math-driven animated breathing orb that reacts to listening, thinking, and speaking states.
* **💾 Persistent Memory:** She remembers facts, preferences, and daily logs using an internal SQLite database.

---

## :rocket: Quick Start

### Prerequisites
* Windows 10/11
* Python 3.11 or higher
* Chrome Browser (for WhatsApp automation)

### Installation

**1. Clone the repository**
```bash
git clone https://github.com/atharv01h/Freya-Ai
cd Freya-Ai
```

**2. Install dependencies**
```bash
pip install -r requirements.txt
python -m playwright install chromium
```

**3. Configure your API Keys**
Open `config.json` and add your **NVIDIA NIM** API key under `"nvidia_nim"`.

**4. Run Freya!**
```bash
python freya.py
```
*Note: On her first WhatsApp interaction, she will open a browser window and ask you to scan the WhatsApp Web QR code. She will securely remember this login forever!*

---

## :brain: How She Works

Freya uses a hyper-optimized **Intent Classifier & Command Router** rather than relying purely on slow LLM function calling. 

1. **Listen:** Audio is caught via `PyAudio` and parsed locally.
2. **Classify:** A strict Regex-based engine extracts intents and entities (e.g., *"Open file report.pdf"* → `open_file(report.pdf)`).
3. **Execute or Chat:** If it's a system command, Python executes it natively in milliseconds. If it's conversational, she streams the text to an LLM, strips `<think>` tokens, and pipes the output to the TTS engine *sentence by sentence* for zero-latency talking.

---

## :warning: Known Issues & Disclaimer

> [!WARNING]  
> **Freya is still actively in development!** 🛠️

Because she is constantly evolving, you may encounter:
- Random STT (Speech-to-Text) misinterpretations in noisy environments.
- Edge-case bugs when asking her to parse extremely complex nested folder structures.
- UI scaling quirks on monitors with non-standard DPI scaling.

If she breaks, just restart the Python script!

---

## :heart: Creator

<div align="center">
  <b>Designed and Engineered by Atharv Hatwar</b><br>
  <i>Pushing the boundaries of personalized AI companions.</i>
</div>

<br>

<div align="center">
  If you love Freya, please consider giving the repo a ⭐ !
</div>
