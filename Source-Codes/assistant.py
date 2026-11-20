# ---------------------------------- make2explore.com -------------------------------------------------------#
# Project           - Offline Voice Assistant on NVIDIA Jetson Orin Nano
# Created By        - info@make2explore.com
# Last Modified     - 20/11/2026 14:36:00 @admin
# Software          - Python
# Hardware          - NVIDIA Jetson Orin Nano   
# Sensors Used      - External USB Mic
# Source Repo       - github.com/make2explore
# ===========================================================================================================#

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