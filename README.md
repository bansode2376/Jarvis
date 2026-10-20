# Jarvis - Personal AI Assistant

Jarvis is a personal AI assistant built with Python, featuring a HUD interface and voice functionality.

## Features

- AI chat using Ollama and the Llama 3.2 3B model.
- Voice input and text-to-speech functionality.
- Browser and media-related integrations.
- Optional system CPU and RAM information in the HUD.

## Project Files

- `jarvis.py` - Main AI assistant.
- `jarvis_hud.py` - HUD and local HTTP server.
- `jarvis_voice.py` - Voice-enabled assistant.
- `hud.html` - HUD interface.

## Requirements

- Windows
- Python 3
- Ollama
- A microphone and audio support for voice features.

## Setup

1. Install Python 3 from https://www.python.org/downloads/
2. Install Ollama from https://ollama.com/download
3. Open Command Prompt and download the required model:

   `ollama pull llama3.2:3b`

4. Install the Python packages:

   `py -m pip install ollama psutil SpeechRecognition pyttsx3 sounddevice numpy yt-dlp pywin32`

5. Run the script you want to use:

   `py jarvis.py`

   `py jarvis_voice.py`

Review the source code for any additional configuration or launch requirements before running.

## Privacy

Personal memory and local text files are intentionally excluded from this public repository. Never commit API keys, passwords, or private data.

## Author

Vansh Bansode

GitHub: https://github.com/bansode2376
