import ollama
import json
import os
import re
import time
import datetime
import difflib
import webbrowser
import subprocess
import urllib.parse
import threading
from collections import deque
import speech_recognition as sr
import pyttsx3
import sounddevice as sd
import numpy as np
import yt_dlp
import jarvis_hud as hud

MODEL = "llama3.2:3b"
MIC_FLOOR = 300      # if Jarvis can't hear you, try 150. If he reacts to noise, try 500.

# Jarvis also reacts to common mishearings of his name
WAKE_VARIANTS = ["jarvis", "jarves", "jar vis", "jarvish", "travis", "garvis"]

def find_wake(text):
    """Returns the words after the wake word, or None if it wasn't said."""
    for w in WAKE_VARIANTS:
        if w in text:
            return text.split(w, 1)[1].strip()
    return None

# ---------- YOU + MEMORY ----------
with open("you.txt", "r", encoding="utf-8") as f:
    about_me = f.read()

MEMORY_FILE = "memory.json"
if os.path.exists(MEMORY_FILE):
    with open(MEMORY_FILE, "r", encoding="utf-8") as f:
        memory = json.load(f)
else:
    memory = []

def save_memory():
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(memory, f, indent=2)

system_prompt = f"""You are Jarvis, a polite, witty personal AI assistant.
Your replies are spoken aloud, so keep them to 1-2 short sentences.
You can ONLY answer questions and chat. You cannot open apps, play music, control
Spotify, browse the internet, or do anything on the computer yourself. Another
system handles those. Never claim or offer abilities you do not have.
Do not use the user's name unless it is truly natural.
About the user:
{about_me}

Things you remember:
{chr(10).join(memory) if memory else "Nothing yet."}
"""

# ---------- CHANNEL: MOUTH AND EARS ----------
recognizer = sr.Recognizer()

def speak(text):
    print("Jarvis:", text)
    hud.set_jarvis(text)
    hud.set_mode("speaking")
    engine = pyttsx3.init()
    engine.setProperty("rate", 175)
    engine.say(text)
    engine.runAndWait()
    hud.set_mode("idle")

SAMPLE_RATE = 16000
BLOCK = 1024
BLOCK_SEC = BLOCK / SAMPLE_RATE
NOISE_THRESHOLD = float(MIC_FLOOR)

def rms(data):
    return float(np.sqrt(np.mean(data.astype(np.float32) ** 2)))

def calibrate():
    """Measures background noise ONCE at startup."""
    global NOISE_THRESHOLD
    print("Calibrating microphone... stay quiet for 1 second.")
    levels = []
    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1,
                        dtype="int16", blocksize=BLOCK) as stream:
        for _ in range(int(1.0 / BLOCK_SEC)):
            data, _ = stream.read(BLOCK)
            levels.append(rms(data))
    NOISE_THRESHOLD = max(np.mean(levels) * 2.5, MIC_FLOOR)
    print("Microphone threshold:", int(NOISE_THRESHOLD))

def listen(active=False, timeout=8, max_phrase=10):
    """active=False: standby, waiting for the wake word.
       active=True: Jarvis is expecting a command from you."""
    hud.set_mode("listening" if active else "idle")
    pre = deque(maxlen=6)    # remembers the last ~0.4s so first syllables aren't lost
    frames = []
    started = False
    silent_time = 0.0
    waited = 0.0
    spoken = 0.0

    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1,
                        dtype="int16", blocksize=BLOCK) as stream:
        while True:
            data, _ = stream.read(BLOCK)
            level = rms(data)

            if not started:
                waited += BLOCK_SEC
                if level > NOISE_THRESHOLD:
                    started = True
                    frames.extend(pre)
                    frames.append(data.copy())
                else:
                    pre.append(data.copy())
                    if waited > timeout:
                        return ""
            else:
                frames.append(data.copy())
                spoken += BLOCK_SEC
                if level < NOISE_THRESHOLD:
                    silent_time += BLOCK_SEC
                else:
                    silent_time = 0.0
                if silent_time > 0.8 or spoken > max_phrase:
                    break

    if active:
        hud.set_mode("thinking")
    audio = sr.AudioData(np.concatenate(frames).tobytes(), SAMPLE_RATE, 2)
    try:
        text = recognizer.recognize_google(audio, language="en-IN").lower()
        print("You:", text)
        if active or find_wake(text) is not None:
            hud.set_user(text)
        return text
    except (sr.UnknownValueError, sr.RequestError):
        return ""

# ---------- PERMISSION SYSTEM ----------
YES_WORDS = {"yes", "yeah", "yep", "yup", "yea", "sure", "okay", "ok",
             "please", "haan", "han", "ha", "ya"}
NO_WORDS = {"no", "nope", "nah", "cancel", "stop", "nahi", "don't", "dont"}

def ask_permission(action):
    speak(f"Shall I {action}? Say yes or no.")
    time.sleep(0.3)
    for attempt in range(2):
        answer = listen(active=True)
        print("Permission answer heard:", repr(answer))
        words = answer.replace(",", " ").split()
        if any(w in YES_WORDS for w in words) or "go ahead" in answer or "do it" in answer:
            return True
        if any(w in NO_WORDS for w in words):
            return False
        if attempt == 0:
            speak("Sorry, I didn't catch that. Yes or no?")
            time.sleep(0.3)
    return False

# ---------- UNDERSTANDING SENTENCES ----------
FILLERS = ["can you", "could you", "would you", "will you", "please", "hey",
           "i want you to", "i want to", "i would like you to", "go ahead and", "just"]

def clean(cmd):
    """Removes polite filler from the start: 'can you play X' -> 'play X'."""
    cmd = cmd.strip(" ,.")
    changed = True
    while changed:
        changed = False
        for f in FILLERS:
            if cmd == f or cmd.startswith(f + " "):
                cmd = cmd[len(f):].strip(" ,.")
                changed = True
    return cmd

def tidy(text):
    text = re.sub(r"\b(please|for me|right now|now|immediately|the app|app|application)\b", "", text)
    return re.sub(r"\s+", " ", text).strip(" ,.")

def tidy_play(text):
    text = re.sub(r"\b(on|from|in|using)\s+youtube\b|\byoutube\b", "", text)
    return tidy(text)

# ---------- TOOLS ----------
SITES = {
    "youtube": "https://www.youtube.com",
    "google": "https://www.google.com",
    "gmail": "https://mail.google.com",
    "github": "https://github.com",
    "linkedin": "https://www.linkedin.com",
    "whatsapp": "https://web.whatsapp.com",
    "instagram": "https://www.instagram.com",
    "facebook": "https://www.facebook.com",
    "maps": "https://maps.google.com",
    "drive": "https://drive.google.com",
    "claude": "https://claude.ai",
}

APPS = {
    "notepad": "notepad",
    "calculator": "calc",
    "paint": "mspaint",
    "file explorer": "explorer",
    "command prompt": "start cmd",
    "task manager": "taskmgr",
    "settings": "start ms-settings:",
}

ALIASES = {
    "vs code": "visual studio code",
    "vscode": "visual studio code",
    "v s code": "visual studio code",
    "bs code": "visual studio code",
    "code": "visual studio code",
    "edge": "microsoft edge",
    "chrome": "google chrome",
}

def scan_start_menu():
    found = {}
    folders = [
        os.path.expandvars(r"%ProgramData%\Microsoft\Windows\Start Menu\Programs"),
        os.path.expandvars(r"%AppData%\Microsoft\Windows\Start Menu\Programs"),
    ]
    for folder in folders:
        for root, _, files in os.walk(folder):
            for f in files:
                if f.lower().endswith(".lnk"):
                    found[f[:-4].lower()] = os.path.join(root, f)
    return found

START_APPS = scan_start_menu()
print(f"Found {len(START_APPS)} apps on this laptop.")

def open_target(name):
    name = tidy(name.strip().lower())
    name = ALIASES.get(name, name)

    if name in SITES:
        webbrowser.open(SITES[name])
        speak(f"Opening {name}.")
        return

    target = None
    label = name
    if name in APPS:
        target = APPS[name]
    else:
        keys = list(START_APPS.keys())
        contains = [k for k in keys if name in k]
        if contains:
            label = min(contains, key=len)
        else:
            close = difflib.get_close_matches(name, keys, n=1, cutoff=0.6)
            if close:
                label = close[0]
        target = START_APPS.get(label)

    if target is None:
        speak(f"I could not find {name} on this laptop.")
        return

    if ask_permission(f"open {label}"):
        if target.lower().endswith(".lnk"):
            os.startfile(target)
        else:
            subprocess.Popen(target, shell=True)
        speak(f"Opening {label}.")
    else:
        speak("Understood. Cancelled.")

VAGUE = {"", "it", "that", "this", "something", "music", "song", "a song",
         "the song", "some music", "one", "anything"}

def youtube_first_video(query):
    opts = {"quiet": True, "skip_download": True,
            "extract_flat": True, "noplaylist": True}
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(f"ytsearch1:{query}", download=False)
    entries = info.get("entries", [])
    if entries:
        return ("https://www.youtube.com/watch?v=" + entries[0]["id"],
                entries[0].get("title", "the video"))
    return None, None

def play_on_youtube(query):
    query = tidy_play(query)
    if query in VAGUE or len(query) < 2:
        speak("What should I play?")
        query = tidy_play(clean(listen(active=True)))
        if query in VAGUE or len(query) < 2:
            speak("I didn't catch that. Cancelled.")
            return
    hud.set_mode("thinking")
    try:
        url, title = youtube_first_video(query)
    except Exception as e:
        print("YouTube lookup error:", e)
        url, title = None, None
    if url:
        webbrowser.open(url + "&autoplay=1")
        speak(f"Playing {title[:70]}.")
    else:
        webbrowser.open("https://www.youtube.com/results?search_query="
                        + urllib.parse.quote(query))
        speak(f"I could not pick a video, so I opened the search for {query}.")

# ---------- BRAIN (fast, streaming) ----------
def warm_up():
    """Loads the AI model into memory so the first answer isn't slow."""
    try:
        ollama.chat(model=MODEL, messages=[{"role": "user", "content": "hi"}],
                    keep_alive="30m", options={"num_predict": 1})
        print("Brain warmed up.")
    except Exception as e:
        print("Warm-up failed (is Ollama running?):", e)

def ask_brain(cmd):
    hud.set_mode("thinking")
    history.append({"role": "user", "content": cmd})
    if len(history) > 9:
        del history[1:len(history) - 8]     # keep the prompt short = faster

    full, buf = "", ""
    try:
        stream = ollama.chat(model=MODEL, messages=history, stream=True,
                             keep_alive="30m", options={"num_predict": 120})
        for chunk in stream:
            piece = chunk["message"]["content"]
            full += piece
            buf += piece
            # speak each sentence as soon as it is ready
            if len(buf) > 25 and buf.rstrip()[-1:] in ".!?":
                speak(buf.strip())
                buf = ""
                hud.set_mode("thinking")
        if buf.strip():
            speak(buf.strip())
    except Exception as e:
        print("Brain error:", e)
        speak("My brain is not responding. Is Ollama running?")
        return
    history.append({"role": "assistant", "content": full})

# ---------- COMMAND HANDLER ----------
def handle_single(cmd):
    """Returns False if Jarvis should shut down, otherwise True."""
    cmd = clean(cmd)
    print("Command:", cmd)
    if not cmd:
        return True
    words = cmd.split()

    if any(p in cmd for p in ["goodbye", "shut down", "go to sleep", "exit jarvis"]):
        speak("Goodbye. Shutting down.")
        return False

    if cmd.startswith("remember"):
        fact = cmd.replace("remember that", "").replace("remember", "").strip()
        memory.append(fact)
        save_memory()
        speak("Noted. I will remember that.")
        return True

    m = re.search(r"\b(open|launch)\s+(.+)", cmd)
    if m:
        open_target(m.group(2))
        return True

    m = re.search(r"\bplay\b\s*(.*)", cmd)
    if m and (cmd.startswith("play") or
              any(k in cmd for k in ["song", "music", "youtube", "video", "playlist"])):
        play_on_youtube(m.group(1))
        return True

    m = re.match(r"(?:search for|search|google)\s+(.+)", cmd)
    if m:
        query = tidy(m.group(1))
        webbrowser.open("https://www.google.com/search?q=" + urllib.parse.quote(query))
        speak(f"Searching for {query}.")
        return True

    if "time" in words:
        speak("It is " + datetime.datetime.now().strftime("%I:%M %p") + ".")
        return True

    if "date" in words:
        speak("Today is " + datetime.datetime.now().strftime("%A, %d %B %Y") + ".")
        return True

    ask_brain(cmd)
    return True
def handle_command(cmd):
    """Splits 'open X and play Y' into separate commands and runs each one."""
    cmd = clean(cmd)
    parts = re.split(r"\s+(?:and then|then|and)\s+(?=(?:open|launch|play|search|google)\b)", cmd)
    # "open youtube" is pointless if we are about to play something on it
    if len(parts) > 1 and any(p.startswith("play") for p in parts[1:]):
        parts = [p for p in parts if p.strip() not in ("open youtube", "launch youtube")]
    for part in parts:
        if handle_single(part) is False:
            return False
    return True
# ---------- MAIN LOOP ----------
def jarvis_loop():
    try:
        import pythoncom
        pythoncom.CoInitialize()
    except Exception:
        pass

    threading.Thread(target=warm_up, daemon=True).start()
    calibrate()
    speak("Jarvis online. At your service.")

    running = True
    while running:
        heard = listen()
        command = find_wake(heard)
        if command is not None:
            if command == "":
                speak("Yes?")
                command = listen(active=True)
            if command:
                running = handle_command(command)
    hud.quit_hud()

threading.Thread(target=jarvis_loop, daemon=True).start()
hud.run()