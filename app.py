"""
JARVIS - Personal AI Assistant (Desktop Application)
Entry point to launch the modern desktop UI.
"""

import sys
import os
import requests

def check_ollama():
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=2)
        if r.status_code == 200:
            models = [m.get("name") for m in r.json().get("models", [])]
            print(f"✅ Ollama detected! Available models: {', '.join(models)}")
            return True
    except Exception:
        print("⚠️ Warning: Ollama does not seem to be running at http://localhost:11434.")
        print("   Jarvis will start, but please run `ollama serve` to chat.")
    return False

def main():
    print("🚀 Starting Jarvis Desktop Assistant...")
    check_ollama()
    from ui.webview_app import start_desktop_app
    start_desktop_app()

if __name__ == "__main__":
    main()
