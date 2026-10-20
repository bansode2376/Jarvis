import json
import os
import subprocess
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

try:
    import psutil
    psutil.cpu_percent()
except Exception:
    psutil = None

PORT = 8765
HTML_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hud.html")

state = {"mode": "idle", "user": "", "jarvis": "", "quit": False}

def set_mode(m):
    state["mode"] = m

def set_user(t):
    state["user"] = t

def set_jarvis(t):
    state["jarvis"] = t

def quit_hud():
    state["quit"] = True

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # keeps the black window clean

    def _send(self, body, ctype):
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.startswith("/state"):
            data = dict(state)
            if psutil:
                data["cpu"] = psutil.cpu_percent()
                data["ram"] = psutil.virtual_memory().percent
            else:
                data["cpu"] = None
                data["ram"] = None
            self._send(json.dumps(data).encode(), "application/json")
        elif self.path.startswith("/quit"):
            state["quit"] = True
            self._send(b"ok", "text/plain")
        else:
            with open(HTML_PATH, "rb") as f:
                self._send(f.read(), "text/html; charset=utf-8")

def open_window():
    url = f"http://localhost:{PORT}"
    browsers = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    for path in browsers:
        if os.path.exists(path):
            subprocess.Popen([path, f"--app={url}", "--start-fullscreen"])
            return
    webbrowser.open(url)

def run():
    try:
        server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    except OSError:
        print("Port is busy. Close any other running Jarvis window and try again.")
        return
    threading.Thread(target=server.serve_forever, daemon=True).start()
    open_window()
    try:
        while not state["quit"]:
            time.sleep(0.2)
    except KeyboardInterrupt:
        pass
    time.sleep(0.6)