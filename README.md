# JARVIS - Personal Autonomous AI Assistant (Desktop App)

A smart, high-performance personal AI desktop assistant built with **Python**, **Groq Cloud API** (`Meta Llama 3.3 70B`), **Local Ollama**, and **PyWebView**. Featuring persistent JSON memory, human-like safety guards with interactive Yes/No approvals, real-time token streaming, neural voice synthesis, and full desktop/terminal automation.

![Jarvis AI Assistant](https://img.shields.io/badge/Jarvis-Desktop%20Assistant-indigo?style=for-the-badge)
![Groq](https://img.shields.io/badge/Groq%20Cloud-Llama%203.3%2070B%20(~300%20T%2Fs)-orange?style=for-the-badge)
![Ollama](https://img.shields.io/badge/Local%20LLM-Ollama-black?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge)

---

- 🤖 **Autonomous Multi-Step Agent Loop & Task Planner**:
  - **Goal Decomposition & Planning**: Decomposes complex user instructions (*"open Chrome, search for Python courses, open the first useful result"*) into structured sequential steps.
  - **Observation & Verification**: Verifies action outcomes via process/window states, filesystem checks, and GUI observations instead of falsely claiming completion.
  - **Error Recovery & Loop Control**: Automatic recovery on failures, strict 10-step safety limit, and instantaneous thread-safe Emergency Stop (`Esc` or "stop").

- 🖱️ **Controlled Computer Automation Layer**:
  - **Full Mouse & Keyboard Control**: Mouse move, click, double click, right click, drag, scroll, and Unicode keyboard typing via native Win32 `SendInput`.
  - **Window Management**: Find, focus, minimize, maximize, resize, move, and close windows.
  - **Clipboard Integration**: Safe read and write operations on Windows clipboard.

- 👁️ **Vision-Guided GUI Interaction**:
  - **Multimodal Screen Perception**: Captures high-DPI screenshots via Win32 GDI BitBlt without screen-grab errors.
  - **Resolution-Independent Element Localization**: Scales relative coordinates to screen resolution to locate and click UI elements dynamically.

- 🪟 **Persistent Floating JARVIS & System Tray**:
  - **Native System Tray Integration**: Background tray menu (Open JARVIS, Mini Robot, Voice Listening, Settings, Exit).
  - **Global Alt+J Hotkey**: Toggles JARVIS from anywhere in Windows, even when other applications or games are active.
  - **Continuous Hands-Free Voice Companion**: Calibrated Voice Activity Detection (VAD) with noise immunity and auto-re-arming.

---

## 🚀 Getting Started

### Prerequisites

1. **Python 3.10+** (Tested on Python 3.14 on Windows).
2. **Groq API Key (Free)**:
   - Create a free account at [console.groq.com](https://console.groq.com).
   - Generate an API Key under [console.groq.com/keys](https://console.groq.com/keys).
3. *(Optional)* **[Ollama](https://ollama.com/)** if you wish to run completely offline models locally.

### Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/iblamelessly/AI-Assistant.git
   cd AI-Assistant
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Configure your Settings:
   - Launch the app and click the ⚙️ **Settings** gear icon in the top right.
   - Paste your free Groq API key into the **Groq API Key** field.
   - Click **Save Settings**. (Your key is securely stored in your local `config.json` and will never be tracked by git).

---

## 🏃 Running the Assistant

### Install Desktop Shortcut (with Custom Icon)
```bash
python install_shortcut.py
```
This creates a **JARVIS AI** desktop shortcut on your Windows Desktop using `pythonw.exe` so it launches seamlessly without opening a terminal window.

### Launch Desktop Application Manually
```bash
python app.py
```
*(Or simply `python main.py`)*

### Launch CLI / Terminal Mode
```bash
python main.py --cli
```

---

## 📁 Project Structure

```
AI-Assistant/
├── app.py                     # Desktop application entrypoint
├── main.py                    # Dual-mode launcher (Desktop / CLI)
├── config.json                # Local configurations & Groq API key (Git-ignored)
├── config.example.json        # Template configuration
├── memory.json                # User memory store (Git-ignored)
├── memory.example.json        # Blank memory template
├── chat_sessions.json         # Conversation session history (Git-ignored)
├── requirements.txt           # Python package dependencies
├── README.md                  # Documentation
├── core/
│   ├── assistant.py           # Unified Autonomous Super AI engine & dispatcher
│   ├── ai_image.py            # FLUX text-to-image & neural style alteration
│   ├── ai_video.py            # Multi-scene AI video slideshow compiler
│   ├── document_generator.py  # 21-theme professional presentation & document engine
│   ├── config.py              # Local persistent configuration manager
│   ├── groq_client.py         # Groq Cloud API client & UsageTracker
│   ├── mic.py                 # Whisper recording & phonetic accent normalization
│   ├── permissions.py         # Human-in-the-Loop permission & ambiguity guard
│   ├── memory.py              # Thread-safe memory manager & async worker
│   ├── voice.py               # Edge-TTS neural speech synthesis
│   ├── tools.py               # Tool registry & unified tool execution
│   └── history.py             # Multi-session conversation store
└── ui/
    ├── webview_app.py         # PyWebView desktop runner & Python-JS bridge
    └── web/
        ├── index.html         # Obsidian dark-mode layout
        ├── styles.css         # Glassmorphism styling & permission prompt buttons
        └── app.js             # Frontend controller & streaming renderer
```

---

## 🛡️ Privacy & Security Guarantee

- **Zero Data Leakage**: Your personal credentials, API keys, memories, and chat sessions are stored exclusively in local files (`config.json`, `memory.json`, `chat_sessions.json`), which are strictly ignored in `.gitignore`.
- **Sensitive Action Safeguards**: JARVIS never executes destructive system operations or writes over existing files without your explicit permission.
