# JARVIS - Personal Autonomous AI Assistant (Desktop App)

A smart, high-performance personal AI desktop assistant built with **Python**, **Groq Cloud API** (`Meta Llama 3.3 70B`), **Local Ollama**, and **PyWebView**. Featuring persistent JSON memory, human-like safety guards with interactive Yes/No approvals, real-time token streaming, neural voice synthesis, and full desktop/terminal automation.

![Jarvis AI Assistant](https://img.shields.io/badge/Jarvis-Desktop%20Assistant-indigo?style=for-the-badge)
![Groq](https://img.shields.io/badge/Groq%20Cloud-Llama%203.3%2070B%20(~300%20T%2Fs)-orange?style=for-the-badge)
![Ollama](https://img.shields.io/badge/Local%20LLM-Ollama-black?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge)

---

## ✨ Features

- ⚡ **Dual Engine: Groq Cloud & Local Ollama**:
  - **Groq Cloud (Default)**: Lightning-fast reasoning (~300 tokens/second) powered by `llama-3.3-70b-versatile` and `llama-3.1-8b-instant`.
  - **Local Ollama Fallback**: Fully offline execution (`qwen3`, `llama3`, `mistral`, etc.) when no internet connection is available.
  - **Live Provider Switching**: Seamlessly toggle between Groq Cloud and Local Ollama inside the Settings modal.

- 🛡️ **Human-like Permission & Ambiguity Guard**:
  - **Human-in-the-Loop Confirmation**: Never deletes files, kills processes, or overwrites scripts without asking for your explicit approval (`Proceed? [Yes / No]`).
  - **Interactive Confirmation Buttons**: One-click **✓ Approve / Yes** and **✕ Cancel / No** buttons appear directly inside chat bubbles.
  - **Ambiguity & Duplicate Detection**: If you ask to delete or modify a file, Jarvis automatically checks your workspace to determine if you mean the original or a backup/duplicate copy before acting.

- 🎙️ **Bidirectional Voice Control**:
  - **Speech-to-Text**: Click the microphone button (`🎙️`) to issue direct voice commands.
  - **Neural Jarvis Voice**: Jarvis speaks back out loud with an English neural voice (Iron Man style) powered by Microsoft Edge Neural TTS.
  - **Voice Mute Toggle**: Quickly enable or mute speech audio anytime in the header.

- 💻 **Full Autonomous Laptop & Project Control**:
  - **PowerShell / Terminal Execution**: Jarvis can execute any command (`git status`, `git commit`, `python script.py`, `pip install`, etc.) and displays formatted terminal output directly in the chat.
  - **File Operations**: Read, create, write, search, and manage files across your machine.
  - **Hardware Automation**: Control Windows master volume directly via Windows CoreAudio (`pycaw`), capture screenshots (*"Take a screenshot"*), and inspect live CPU, RAM, Disk, and Battery stats.
  - **Application Management**: Launch apps (*"Open VS Code"*, *"Open Chrome"*, *"Open Notepad"*) and inspect running processes.

- 🖥️ **Obsidian Dark Desktop GUI**: Modern, responsive dark-mode interface built with native Edge WebView2 runtime (lightweight, zero Electron bloat).
- 🧠 **Dynamic & Async Memory System**: Background fact extraction continuously learns about your preferences, habits, and career goals without stalling conversations.
- 📂 **Visual Memory Center**: Interactive dashboard to view, edit, add, or delete memories stored in `memory.json`.
- 💬 **Multi-Session Chat History**: Save, switch between, and clear past conversation sessions locally.

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
│   ├── assistant.py           # Unified Autonomous Agent engine
│   ├── config.py              # Local persistent configuration manager
│   ├── groq_client.py         # Groq Cloud API streaming client (~300 T/s)
│   ├── permissions.py         # Human-in-the-Loop permission & ambiguity guard
│   ├── memory.py              # Thread-safe memory manager & async worker
│   ├── voice.py               # Edge-TTS neural speech synthesis
│   ├── tools.py               # Laptop tools (terminal, volume, apps, hardware)
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
