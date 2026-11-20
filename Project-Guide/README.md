# Offline Voice Assistant on NVIDIA Jetson Orin Nano

A fully local, low-latency, and privacy-preserving voice assistant running entirely on-device without cloud services or external API calls. Built for embedded edge hardware like the NVIDIA Jetson Orin Nano (8GB), this project creates an interactive conversational loop featuring wake-word detection, multi-turn follow-up dialogue, local Large Language Model (LLM) inference, and neural text-to-speech synthesis.

## Table of Contents

* [Project Overview](#project-overview)
* [Key Features](#key-features)
* [System Architecture](#system-architecture)
* [Hardware Requirements](#hardware-requirements)
* [Software Requirements](#software-requirements)
* [Tutorial Guides & Videos](#tutorial-guides--videos)
* [Step-by-Step Build Guide](#step-by-step-build-guide)
  * [1. System Performance, Audio Dependencies & Permissions](#1-system-performance-audio-dependencies--permissions)
  * [2. Local LLM Runtime (Ollama)](#2-local-llm-runtime-ollama)
  * [3. Python Environment & Piper TTS Setup](#3-python-environment--piper-tts-setup)
  * [4. Audio Hardware Verification](#4-audio-hardware-verification)
  * [5. Create the Assistant Script (assistant.py)](#5-create-the-assistant-script-assistantpy)
* [Running the Assistant](#running-the-assistant)
* [Microphone Auto-Detection & Custom Override](#microphone-auto-detection--custom-override)
* [Thermal & Power Telemetry](#thermal--power-telemetry)
* [Troubleshooting](#troubleshooting)
* [License](#license)

---

## Project Overview

Running voice assistants on edge hardware typically encounters three hurdles: memory saturation, thermal throttling, and hardware-specific compilation conflicts (such as cuDNN/CTranslate2 compatibility quirks on JetPack).

This project resolves those constraints on the **NVIDIA Jetson Orin Nano (8GB)** by orchestrating an efficient hybrid compute workflow:

* **LLM Engine:** Local GPU-accelerated inference (`llama3.2:3b` hosted via Ollama) with a memory keep-alive pool.
* **Speech-to-Text (STT):** Quantized CPU-side transcription (`faster-whisper` on `base.en`, INT8) that avoids CUDA library conflicts and keeps GPU memory open for the language model.
* **Text-to-Speech (TTS):** Low-overhead, real-time neural speech synthesis using Piper TTS.
* **Audio Layer:** Direct ALSA subsystem integration featuring dynamic capture device auto-detection and fallback overrides.

---

## Key Features

* **100% Offline & Private:** Zero cloud telemetry, no internet dependency once installed, and no subscription fees or API tokens.
* **Two-State Conversational State Machine:**
  * *Passive Standby:* Passively captures 3-second ambient audio slices looking for the wake word without triggering heavy LLM inference.
  * *Wake Activation:* Responds to `"Hey Joy"` (and common phonetic variants like `"Enjoy"` or `"Hi Joy"`) with an immediate 880 Hz confirmation beep.
  * *Active Follow-Up Window:* Opens a 10-second command capture window and retains active conversational state so you can ask multi-turn questions without repeating the wake word.
  * *Auto-Sleep:* Automatically returns to passive standby after 3 consecutive silent or ambient-noise turns.
* **Universal Audio Hardware Auto-Detection:** Dynamically scans active ALSA cards on startup to prioritize connected USB microphones, webcams (e.g., Logitech C270), or headsets without manual card indexing.
* **Stable Thermal & Power Budget:** Runs reliably within the Jetson 25W power profile at approximately ~50°C under load.

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

| Component | Recommendation / Tested Spec |
| :--- | :--- |
| **SBC** | NVIDIA Jetson Orin Nano Developer Kit (8GB) |
| **Storage** | 128GB+ NVMe PCIe M.2 SSD |
| **Power Supply** | Standard Jetson 19V DC power barrel adapter |
| **Microphone** | Standard USB Microphone, USB Headset, or USB Webcam (e.g., Logitech C270) |
| **Speaker** | 3.5mm AUX Speaker, USB Audio Out, or Monitor Audio via DisplayPort |
| **Cooling** | Active PWM cooling fan |

---

## Software Requirements

* **Operating System:** Ubuntu 22.04 LTS (JetPack 6.x)
* **Python Runtime:** Python 3.10+
* **System Utilities:** `alsa-utils`, `sox`, `libsox-fmt-all`, `curl`, `git`
* **Local Inference Engines:**
  * Ollama (`llama3.2:3b`)
  * `faster-whisper`
  * Piper TTS (`en_US-lessac-medium`)

---

## Tutorial Guides & Videos

* **Official NVIDIA Getting Started Guide:** [NVIDIA Jetson Orin Nano DevKit Documentation](https://developer.nvidia.com/embedded/learn/get-started-jetson-orin-nano-devkit)
* **Jetson Orin Nano Setup & Unboxing:** `[INSERT_YOUTUBE_VIDEO_LINK_HERE]`
* **Complete Step-by-Step Project Walkthrough:** `[INSERT_VOICE_ASSISTANT_VIDEO_LINK_HERE]`

---

## Step-by-Step Build Guide

### 1. System Performance, Audio Dependencies & Permissions

Maximize system performance via `nvpmodel`, install audio packages, and grant your user account access to ALSA audio devices:

```bash
# 1. Set Jetson to 25W mode and lock clocks
sudo nvpmodel -m 0
sudo jetson_clocks

# 2. Update package index and install required audio/system tools
sudo apt update && sudo apt install -y \
    alsa-utils \
    sox \
    libsox-fmt-all \
    curl \
    git \
    python3-pip \
    python3-venv

# 3. Add your user to the audio group (ensures permission to capture/play audio)
sudo usermod -aG audio $USER
newgrp audio
```

---

### 2. Local LLM Runtime (Ollama)

Install Ollama to run the conversational model locally on the Jetson:

```bash
# 1. Install Ollama binary & system service
curl -fsSL https://ollama.com/install.sh | sh

# 2. Pull and test the lightweight 3B model (runs locally on GPU/CPU)
ollama run llama3.2:3b "Hello!"
```

---

### 3. Python Environment & Piper TTS Setup

Create a dedicated workspace, configure a virtual environment, and download the pre-compiled ARM64 Piper TTS binary and voice model:

```bash
# 1. Create directory structure
mkdir -p ~/voice-bot/voices
cd ~/voice-bot

# 2. Set up Python virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install required Python dependencies
pip install --upgrade pip
pip install faster-whisper requests

# 4. Download and install Piper TTS (ARM64 release)
wget https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_linux_aarch64.tar.gz
tar -xf piper_linux_aarch64.tar.gz
chmod +x ~/voice-bot/piper/piper
sudo ln -sf ~/voice-bot/piper/piper /usr/local/bin/piper

# 5. Download Piper voice model (Lessac Medium) and JSON config
cd ~/voice-bot/voices
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json

# Return to base directory
cd ~/voice-bot
```

---

### 4. Audio Hardware Verification

Before creating the main script, verify your speaker and microphone channels:

```bash
# 1. Verify playback (plays a short 880Hz test beep)
play -nq -n synth 0.2 sin 880 vol 0.2

# 2. Check capture devices recognized by ALSA
arecord -l
```

---

### 5. Create the Assistant Script (assistant.py)

Generate the complete voice assistant script into `~/voice-bot/assistant.py` with a single terminal command:

```bash
cat << 'EOF' > ~/voice-bot/assistant.py
import os
import re
import subprocess
import requests
from faster_whisper import WhisperModel

MODEL_NAME = "llama3.2:3b"
HOME_DIR = os.path.expanduser("~")
PIPER_MODEL = os.path.join(HOME_DIR, "voice-bot/voices/en_US-lessac-medium.onnx")
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
        print(f"[Audio] Using MIC_DEV override: {env_override}", flush=True)
        return env_override

    try:
        res = subprocess.run(
            ["arecord", "-l"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            check=True,
        )
    except Exception:
        print("[Audio] 'arecord' check failed. Defaulting to 'default'", flush=True)
        return "default"

    card_pattern = re.compile(r"^card\s+(\d+):\s+([^,]+),\s+device\s+(\d+):", re.MULTILINE)
    devices = []
    for match in card_pattern.finditer(res.stdout):
        card_id = match.group(1)
        name = match.group(2).strip()
        device_id = match.group(3)
        devices.append((f"plughw:{card_id},{device_id}", name))

    if not devices:
        print("[Audio] No hardware capture cards detected. Using 'default'", flush=True)
        return "default"

    # Prioritize external USB mics, webcams, or headsets
    for dev_str, name in devices:
        lower_name = name.lower()
        if any(kw in lower_name for kw in ["usb", "mic", "webcam", "camera", "headset", "c270"]):
            print(f"[Audio] Auto-detected microphone: '{name}' -> {dev_str}", flush=True)
            return dev_str

    fallback_dev, fallback_name = devices[0]
    print(f"[Audio] Defaulting to capture device: '{fallback_name}' -> {fallback_dev}", flush=True)
    return fallback_dev


# Automatically configure microphone
MIC_DEV = resolve_mic_device()

# Initialize Faster-Whisper on CPU (INT8) to avoid CUDA conflicts and preserve GPU memory
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
            # Standby: 3-second ambient monitoring
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

        # Active conversation window: 10-second command capture
        print("Listening (10 seconds)...", flush=True)
        subprocess.run(
            ["arecord", "-D", MIC_DEV, "-f", "S16_LE", "-r", "16000", "-c", "1", "-d", "10", AUDIO_CMD],
            check=True,
        )

        segments, _ = whisper.transcribe(AUDIO_CMD)
        user_text = " ".join(s.text.strip() for s in segments).strip()
        print("You:", user_text if user_text else "[silence]", flush=True)

        clean_cmd = "".join(c for c in user_text if c.isalnum() or c.isspace()).strip().lower()

        # Handle explicit termination commands
        if clean_cmd in {"stop", "exit", "quit", "bye", "goodbye"}:
            print("AI: Going to sleep.", flush=True)
            speak("Goodbye.")
            in_conversation = False
            consecutive_silence = 0
            continue

        # Silence or ambient noise handling
        if len(clean_cmd) < 2 or clean_cmd in NOISE_WORDS:
            consecutive_silence += 1
            if consecutive_silence >= 3:
                print("[No reply detected. Returning to standby...]", flush=True)
                in_conversation = False
                consecutive_silence = 0
            continue

        # Reset silence counter upon receiving valid input
        consecutive_silence = 0

        # Query local LLM via Ollama
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
EOF
```

---

## Running the Assistant

Activate the environment and start the assistant:

```bash
cd ~/voice-bot
source venv/bin/activate
python3 assistant.py
```

> **Note on First Run:** During the initial run, `faster-whisper` will automatically download the `base.en` model weights (~140MB) into `~/.cache/huggingface/`. Subsequent runs will load instantly from disk.

### Conversational Lifecycle

1. **Wake Trigger:** Say **"Hey Joy"**.
2. **Audio Cue:** The device sounds a single short beep (880 Hz).
3. **Command Capture:** Speak your command or question during the 10-second capture window.
4. **Spoken Response:** The assistant synthesizes a short response and reads it aloud through your speaker.
5. **Continuous Conversation:** Ask follow-up questions directly without repeating `"Hey Joy"`.
6. **Sleep Mode:** Say **"Goodbye"** or remain silent for 3 consecutive capture turns (~30 seconds) to return to passive standby.

---

## Microphone Auto-Detection & Custom Override

The script dynamically detects USB microphones and webcams upon launch. If you have multiple microphones connected and want to force a specific ALSA hardware card:

1. List available capture cards:
   ```bash
   arecord -l
   ```
2. Launch `assistant.py` with the `MIC_DEV` environment variable:
   ```bash
   # Example: forcing Card 1, Device 0
   MIC_DEV=plughw:1,0 python3 assistant.py
   ```

---

## Thermal & Power Telemetry

Monitor hardware statistics in real time using the Jetson diagnostic utility:

```bash
timeout 5 tegrastats
```

**Typical Profile Under 25W Operation:**
* **VDD_IN (System Power):** 4.9W – 5.5W during standby monitoring; brief peaks up to 10W–14W during active LLM inference.
* **Temperatures:** CPU, GPU, and SoC rails remain balanced between 48°C and 52°C.
* **RAM Utilization:** Approximately 6.1 GB – 6.3 GB used (comfortably within the 7.48 GB available).

---

## Troubleshooting

* **Wake word not detected:** Ensure microphone volume is adequate. Launch `alsamixer`, press `F6` to select your USB sound card, press `F4` to view capture levels, and raise the input gain.
* **No audio playback:** Test playback manually with `play /tmp/reply.wav` or check speaker routing in `alsamixer` under playback devices (`F3`).
* **Piper command not found:** Ensure the symlink was created correctly:
  ```bash
  sudo ln -sf ~/voice-bot/piper/piper /usr/local/bin/piper
  ```

---

## License

This project is licensed under the [MIT License](LICENSE).