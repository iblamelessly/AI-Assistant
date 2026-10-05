"""
JARVIS - Personal AI Assistant (Desktop Application)
Entry point to launch the modern desktop UI.
"""

import sys
import os

# Ensure Windows console supports UTF-8 characters and emojis safely
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import requests

def check_ollama():
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=2)
        if r.status_code == 200:
            models = [m.get("name") for m in r.json().get("models", [])]
            print(f"[Ollama] Detected local models: {', '.join(models)}")
            return True
    except Exception:
        print("[Ollama] Warning: Ollama not running at http://localhost:11434 (offline models disabled).")
    return False

def main():
    print("[JARVIS] Starting Jarvis Desktop Assistant...")
    check_ollama()
    from ui.webview_app import start_desktop_app
    start_desktop_app()

if __name__ == "__main__":
    main()
