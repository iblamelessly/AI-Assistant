# JARVIS - Personal AI Assistant (Desktop App)

A smart, local personal AI desktop assistant built with **Python**, **Ollama**, and **PyWebView**. Featuring persistent JSON memory, background fact extraction, real-time token streaming, and desktop system automation.

![Jarvis AI Assistant](https://img.shields.io/badge/Jarvis-Desktop%20Assistant-indigo?style=for-the-badge)
![Ollama](https://img.shields.io/badge/Local%20LLM-Ollama-black?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge)

---

## ✨ Features

- 🖥️ **Modern Desktop GUI**: Sleek dark-mode interface built with native Edge WebView2 runtime (lightweight, responsive, zero Electron bloat).
- ⚡ **Real-Time Token Streaming**: Snappy token-by-token streaming responses from local Ollama models (`qwen3:1.7b`, `qwen3:4b`, etc.).
- 🧠 **Dynamic & Async Memory System**:
  - Automatically analyzes conversation in the background to learn about you (name, education, career goals, projects, skills, preferences).
  - Background extraction ensures instant chat responses without blocking or dual-latency lag.
  - Dynamically injects updated memories into the system prompt on every turn.
- 📂 **Visual Memory Center**: An interactive dashboard to view, edit, add, or delete memories stored in `memory.json`.
- ⚙️ **Desktop Automation ("Jarvis" Mode)**:
  - **Launch Apps**: *"Open Notepad"*, *"Open Chrome"*, *"Open VS Code"*, *"Open Spotify"*, etc.
  - **System Metrics**: Real-time monitoring of CPU, RAM, Disk, and Battery usage.
  - **Web Search**: Automatically executes web queries in your default browser.
  - **Time & Calendar**: Tells the current local time, date, and day of week.
- 💬 **Multi-Session Chat History**: Save, switch between, and clear past conversation sessions locally.
- 🔄 **Model Selector**: Detects installed Ollama models and switches models on the fly.
- 📟 **Dual Mode**: Run as a rich Desktop Application or as a terminal CLI (`python main.py --cli`).

---

## 🚀 Getting Started

### Prerequisites

1. **Python 3.10+** (Tested on Python 3.14).
2. **[Ollama](https://ollama.com/)** installed and running on your system.
3. Download your preferred model (e.g., Qwen 3):
   ```bash
   ollama run qwen3:1.7b
   ```

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
├── app.py                     # Desktop application launcher
├── main.py                    # Dual-mode launcher (Desktop / CLI)
├── memory.json                # User memory store
├── memory.example.json        # Blank memory template
├── chat_sessions.json         # Conversation session history
├── requirements.txt           # Python package dependencies
├── README.md                  # Documentation
├── core/
│   ├── assistant.py           # Ollama streaming engine & dynamic prompt builder
│   ├── memory.py              # Thread-safe memory manager & async worker
│   ├── tools.py               # System automation (apps, hardware stats, web)
│   └── history.py             # Multi-session conversation store
└── ui/
    ├── webview_app.py         # PyWebView runner & Python-JS bridge
    └── web/
        ├── index.html         # Modern dark-mode layout
        ├── styles.css         # Glassmorphism styling and themes
        └── app.js             # Frontend controller & streaming renderer
```

---

## 🛡️ Privacy & Local Execution

Everything runs **100% locally** on your machine. Your chats, memories, and model inferences never leave your computer.
