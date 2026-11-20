# Offline Voice Assistant on NVIDIA Jetson Orin Nano

A fully local, low-latency, and privacy-preserving voice assistant running entirely on-device without cloud services or internet access. Designed specifically for embedded edge AI systems such as the NVIDIA Jetson Orin Nano, this project delivers an interactive conversational voice loop featuring wake-word activation, multi-turn follow-up dialogue, local Large Language Model (LLM) reasoning, and neural text-to-speech synthesis.

---

## Table of Contents
- [Project Overview](#project-overview)
- [Key Features](#key-features)
- [System Architecture](#system-architecture)
- [Hardware Requirements](#hardware-requirements)
- [Software Requirements](#software-requirements)
- [Tutorial Guides & Videos](#tutorial-guides--videos)
- [Installation & Setup](#installation--setup)
  - [1. System Performance & Audio Packages](#1-system-performance--audio-packages)
  - [2. Local LLM Runtime (Ollama)](#2-local-llm-runtime-ollama)
  - [3. Python Virtual Environment & Piper TTS](#3-python-virtual-environment--piper-tts)
  - [4. Main Application Code](#4-main-application-code)
- [Running the Voice Assistant](#running-the-voice-assistant)
- [Microphone Auto-Detection & Custom Config](#microphone-auto-detection--custom-config)
- [Thermal & Power Telemetry](#thermal--power-telemetry)
- [Troubleshooting](#troubleshooting)
- [License](#license)

---

## Project Overview

Running conversational AI on edge hardware typically encounters three hurdles: memory limitations, thermal throttling, and hardware-specific compilation conflicts (such as cuDNN/CTranslate2 mismatches). 

This project solves those challenges on the **NVIDIA Jetson Orin Nano (8GB)** by orchestrating a balanced compute workload:
* **LLM Engine:** GPU-accelerated quantized local inference (`llama3.2:3b` via Ollama) with active memory pooling.
* **Speech-to-Text (STT):** Fast CPU-side quantized transcription (`faster-whisper` on INT8) to conserve GPU VRAM and maintain stability.
* **Text-to-Speech (TTS):** Low-overhead, real-time neural voice generation using Piper TTS.
* **Audio Layer:** Direct ALSA subsystem integration with universal hardware auto-detection.

---

## Key Features

* **100% Offline & Private:** Zero telemetry, no external network requests, and no third-party cloud API keys required.
* **State-Machine Conversational Loop:**
  * *Passive Standby:* Continuously samples ambient noise in short intervals without running heavy inference.
  * *Wake Trigger:* Responds to `"Hey Joy"` (and related phonetic variants).
  * *Follow-Up Window:* Maintains an active conversational session for subsequent questions without requiring the wake word every time.
  * *Auto-Sleep:* Automatically returns to passive listening after 3 consecutive silent turns.
* **Universal Hardware Audio Resolver:** Scans ALSA interfaces at startup to automatically discover USB microphones, headsets, and webcams, eliminating hardcoded hardware indices.
* **Optimized Thermal/Power Envelope:** Operates reliably under the Jetson 25W power profile, hovering around ~50°C under active load.

---

## System Architecture

```text
       +-----------------------+
       |   Ambient Listening   | <---+
       |    (3-second loop)    |     |
       +-----------+-----------+     |
                   |                 |
            [ "Hey Joy" ? ]          |
                   | Yes             | Silence Timeout
                   v                 | (3 empty turns)
       +-----------------------+     |
       |    Cue Tone (880Hz)   |     |
       +-----------+-----------+     |
                   |                 |
                   v                 |
       +-----------------------+     |
       | Capture Command (10s) |     |
       +-----------+-----------+     |
                   |                 |
                   v                 |
       +-----------------------+     |
       | faster-whisper (INT8) |     |
       +-----------+-----------+     |
                   |                 |
                   v                 |
       +-----------------------+     |
       | Ollama (llama3.2:3b)  |     |
       +-----------+-----------+     |
                   |                 |
                   v                 |
       +-----------------------+     |
       |   Piper Neural TTS    |     |
       +-----------+-----------+     |
                   |                 |
                   v                 |
       +-----------------------+     |
       |    Audio Playback     | ----+
       +-----------------------+
```

---

## Hardware Requirements

| Component | Specification |
| :--- | :--- |
| **SBC** | NVIDIA Jetson Orin Nano Developer Kit (8GB) |
| **Storage** | 128GB+ NVMe PCIe M.2 SSD (high speed recommended) |
| **Power Supply** | Standard Jetson 19V DC power supply |
| **Microphone** | Standard USB Microphone, USB Headset, or USB Webcam (e.g., Logitech C270) |
| **Speaker** | 3.5mm AUX Speaker, USB Audio Output, or Monitor Audio via DisplayPort/HDMI |
| **Cooling** | Active PWM cooling fan |

---

## Software Requirements

* **Operating System:** Ubuntu 22.04 LTS (JetPack 6.x)
* **Python Runtime:** Python 3.10+ with `venv`
* **Audio Drivers:** `alsa-utils`, `sox`, `libsox-fmt-all`
* **Model Engines:** 
  * Ollama (`llama3.2:3b`)
  * `faster-whisper`
  * Piper TTS (`en_US-lessac-medium`)

---

## Tutorial Guides & Videos

* **Official NVIDIA Getting Started Guide:** [NVIDIA Jetson Orin Nano DevKit Documentation](https://developer.nvidia.com/embedded/learn/get-started-jetson-orin-nano-devkit)
* **Jetson Orin Nano Unboxing & Specs:** [Watch](https://youtu.be/QPcrAhREJjQ)  
* **Jetson Orin Nano Super Developer Kit Setup Guide (2026):** [Watch](https://youtu.be/KXQEhidMDfc)  
* **Complete Step-by-Step Project Walkthrough:** [Watch](https://www.youtube.com/@make2explore)  

---

## Installation & Setup

### 1. System Performance & Audio Packages

Set the Jetson power mode to 25W for maximum operating headroom and install required audio manipulation libraries:

```bash
# Enable 25W Power Mode and lock clock profiles
sudo nvpmodel -m 0
sudo jetson_clocks

# Install system dependencies
sudo apt update && sudo apt install -y \
    alsa-utils \
    sox \
    libsox-fmt-all \
    curl \
    git \
    python3-pip \
    python3-venv
```

---

### 2. Local LLM Runtime (Ollama)

Install Ollama to host the conversational language model locally:

```bash
# Install Ollama binary
curl -fsSL https://ollama.com/install.sh | sh

# Pull the lightweight conversational model
ollama run llama3.2:3b "Hello!"
```

---

### 3. Python Virtual Environment & Piper TTS

Set up an isolated Python environment and download the lightweight Piper TTS binary and voice checkpoints:

```bash
# Create working directories
mkdir -p ~/voice-bot/voices && cd ~/voice-bot

# Set up Python virtual environment
python3 -m venv venv
source venv/bin/activate

# Install required Python packages
pip install --upgrade pip
pip install faster-whisper requests

# Download and extract Piper TTS (ARM64 release)
wget https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_linux_aarch64.tar.gz
tar -xf piper_linux_aarch64.tar.gz
sudo ln -sf ~/voice-bot/piper/piper /usr/local/bin/piper

# Download Piper voice checkpoint and configuration
cd ~/voice-bot/voices
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json
cd ~/voice-bot
```

---

### 4. Main Application Code

Save the following source as `~/voice-bot/assistant.py`:

```python
import os
import re
import subprocess
import requests
from faster_whisper import WhisperModel

MODEL_NAME = "llama3.2:3b"
PIPER_MODEL = os.path.expanduser("~/voice-bot/voices/en_US-lessac-medium.onnx")
AUDIO_WAKE = "/tmp/wake_input.wav"
AUDIO_CMD = "/tmp/cmd_input.wav"
AUDIO_OUT = "/tmp/reply.wav"
SYSTEM_PROMPT = "You are a helpful offline voice assistant. Reply in 1 to 2 short, direct sentences."

WAKE_VARIANTS = {"hey joy", "hey joi", "he joy", "a joy", "hi joy", "enjoy", "joy"}
NOISE_WORDS = {"you", "thank you", "thanks", "bye", "goodbye", "hmm", "uh", "um"}


def resolve_mic_device():
    """Dynamically detects active USB or external microphone devices from ALSA."""
    env_override = os.environ.get("MIC_DEV")
    if env_override:
        print(f"[Audio] Using manual MIC_DEV override: {env_override}", flush=True)
        return env_override

    try:
        result = subprocess.run(
            ["arecord", "-l"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            check=True
        )
    except Exception:
        print("[Audio] 'arecord' check failed. Defaulting to 'default'", flush=True)
        return "default"

    card_pattern = re.compile(r"^card\s+(\d+):\s+([^,]+),\s+device\s+(\d+):", re.MULTILINE)
    devices = []

    for match in card_pattern.finditer(result.stdout):
        card_id = match.group(1)
        name = match.group(2).strip()
        device_id = match.group(3)
        dev_str = f"plughw:{card_id},{device_id}"
        devices.append((dev_str, name))

    if not devices:
        print("[Audio] No audio input devices detected via arecord. Using 'default'", flush=True)
        return "default"

    # Prioritize external USB microphones and webcams
    for dev_str, name in devices:
        lower_name = name.lower()
        if any(keyword in lower_name for keyword in ["usb", "mic", "webcam", "camera", "headset"]):
            print(f"[Audio] Auto-detected microphone: '{name}' -> {dev_str}", flush=True)
            return dev_str

    fallback_dev, fallback_name = devices[0]
    print(f"[Audio] Using primary capture device: '{fallback_name}' -> {fallback_dev}", flush=True)
    return fallback_dev


# Resolve microphone device
MIC_DEV = resolve_mic_device()

# Initialize Faster-Whisper on CPU (INT8) to preserve GPU RAM
whisper = WhisperModel("base.en", device="cpu", compute_type="int8")
print("Offline voice assistant ready. Say 'Hey Joy' to start talking, or 'stop' to quit.", flush=True)


def play_beep():
    subprocess.run(
        ["play", "-nq", "-n", "synth", "0.12", "sin", "880", "vol", "0.2"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def speak(text):
    if not text:
        return
    subprocess.run(
        ["piper", "--model", PIPER_MODEL, "--output_file", AUDIO_OUT],
        input=text,
        text=True,
        check=True,
    )
    subprocess.run(["play", AUDIO_OUT], check=True)


in_conversation = False
consecutive_silence = 0

try:
    while True:
        if not in_conversation:
            # Standby phase: 3-second ambient monitoring
            subprocess.run(
                ["arecord", "-D", MIC_DEV, "-f", "S16_LE", "-r", "16000", "-c", "1", "-d", "3", AUDIO_WAKE],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True,
            )
            segments, _ = whisper.transcribe(AUDIO_WAKE)
            text = " ".join(s.text.strip() for s in segments).strip()
            clean = "".join(c for c in text if c.isalnum() or c.isspace()).strip().lower()

            if clean in {"stop", "exit", "quit"}:
                goodbye = "Stopping voice assistant."
                print("AI:", goodbye, flush=True)
                speak(goodbye)
                break

            if any(v in clean for v in WAKE_VARIANTS):
                print(f"\n[Awake: heard '{text}']", flush=True)
                play_beep()
                in_conversation = True
                consecutive_silence = 0
            continue

        # Active conversation phase: 10-second command capture
        print("Listening (10 seconds)...", flush=True)
        subprocess.run(
            ["arecord", "-D", MIC_DEV, "-f", "S16_LE", "-r", "16000", "-c", "1", "-d", "10", AUDIO_CMD],
            check=True,
        )

        segments, _ = whisper.transcribe(AUDIO_CMD)
        user_text = " ".join(s.text.strip() for s in segments).strip()
        print("You:", user_text if user_text else "[silence]", flush=True)

        clean_cmd = "".join(c for c in user_text if c.isalnum() or c.isspace()).strip().lower()

        # Handle explicit dismiss commands
        if clean_cmd in {"stop", "exit", "quit", "bye", "goodbye"}:
            print("AI: Going to sleep.", flush=True)
            speak("Goodbye.")
            in_conversation = False
            consecutive_silence = 0
            continue

        # Filter empty captures or background noise
        if len(clean_cmd) < 2 or clean_cmd in NOISE_WORDS:
            consecutive_silence += 1
            if consecutive_silence >= 3:
                print("[No reply detected. Returning to standby...]", flush=True)
                in_conversation = False
                consecutive_silence = 0
            continue

        # Reset silence counter
        consecutive_silence = 0

        # Query local LLM through Ollama
        res = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": MODEL_NAME,
                "system": SYSTEM_PROMPT,
                "keep_alive": "30m",
                "options": {"num_predict": 90},
                "prompt": user_text,
                "stream": False,
            },
            timeout=120,
        )
        res.raise_for_status()
        reply = res.json().get("response", "").strip()
        print("AI:", reply, flush=True)
        speak(reply)

except KeyboardInterrupt:
    print("\nExited.")
```

---

## Running the Voice Assistant

Start the application inside your virtual environment:

```bash
cd ~/voice-bot
source venv/bin/activate
python3 assistant.py
```

### Conversational Flow
1. **Wake Trigger:** Say **"Hey Joy"**.
2. **Audio Cue:** The device emits a single short beep (880 Hz) acknowledging activation.
3. **Command Capture:** Speak your query within the 10-second capture window.
4. **Spoken Response:** The assistant synthesizes a short response and reads it aloud.
5. **Continuous Conversation:** Continue asking follow-up questions directly without repeating the wake phrase.
6. **Sleep Mode:** Say **"Bye"** or remain silent for 3 consecutive capture turns (~30 seconds) to return to standby.

---

## Microphone Auto-Detection & Custom Config

The script automatically detects USB microphones and headsets. If your system features multiple microphones or non-standard routing, you can inspect and explicitly designate your hardware target without editing the code:

1. List active ALSA capture devices:
   ```bash
   arecord -l
   ```
2. Note the card and device number (e.g., `card 2: Device [USB Mic], device 0:`).
3. Launch with the `MIC_DEV` environment variable:
   ```bash
   MIC_DEV=plughw:2,0 python3 assistant.py
   ```

---

## Thermal & Power Telemetry

To ensure system stability, inspect your power draw and rail temperatures using the Jetson diagnostic utility:

```bash
timeout 5 tegrastats
```

**Expected Operational Values (25W Profile):**
* **VDD_IN (System Power):** 4.9W – 5.5W during passive listening; brief peaks up to 10W–14W during LLM generation.
* **Temperatures:** CPU, GPU, and SoC rails remain balanced between 48°C and 52°C.
* **Memory Usage:** Approximately 6.1 GB – 6.3 GB of 7.48 GB RAM utilized with LLM weights pooled in memory.

---

## Troubleshooting

* **Wake word not triggering:** Ensure you speak clearly within the 3-second ambient window. If using an omnidirectional mic in a noisy environment, adjust microphone gain using `alsamixer`.
* **Audio output silent:** Ensure SoX can route to your default output (`play /tmp/reply.wav`). Check volume levels in `alsamixer` under the playback tab.
* **Out of Memory (OOM) Errors:** Confirm that swap memory is enabled (at least 4GB to 8GB swapfile) and ensure large background applications (e.g., web browsers) are closed.

---

## License

This project is released under the [MIT License](LICENSE).