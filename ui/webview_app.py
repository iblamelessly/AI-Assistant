import os
import json
import base64
import mimetypes
import time
import threading
from pathlib import Path
import webview

from core.memory import MemoryManager
from core.history import HistoryManager
from core.tools import AssistantTools
from core.assistant import AssistantEngine
from core.voice import VoiceEngine
from core.config import ConfigManager
from core.permissions import PermissionGuard
from core.mic import MicrophoneEngine

class AssistantApi:
    """Python API bridge exposed to the Webview UI."""

    def __init__(self, memory_mgr, history_mgr, engine, voice_engine, config_mgr=None, mic_engine=None):
        self.memory_mgr = memory_mgr
        self.history_mgr = history_mgr
        self.engine = engine
        self.voice_engine = voice_engine
        self.config_mgr = config_mgr if config_mgr else (getattr(engine, "config_mgr", None) or ConfigManager())
        self.mic_engine = mic_engine if mic_engine else MicrophoneEngine()
        self._window = None

    def set_window(self, window):
        self._window = window

    def init_app(self):
        """Initial data payload required when frontend loads."""
        sessions = self.history_mgr.list_sessions()
        active_id = None
        if not sessions:
            new_s = self.history_mgr.create_session("New Conversation")
            sessions = self.history_mgr.list_sessions()
            active_id = new_s["id"]
        else:
            active_id = sessions[0]["id"]

        installed_models = self.engine.get_installed_models()

        return {
            "sessions": sessions,
            "active_session_id": active_id,
            "models": installed_models,
            "current_model": self.engine.model,
            "memory": self.memory_mgr.get_memory(),
            "system_stats": AssistantTools.get_system_stats(),
            "voice_enabled": self.voice_engine.is_enabled() if self.voice_engine else False,
            "config": self.config_mgr.get_all()
        }

    def send_message(self, user_message, session_id, attachments=None):
        """Asynchronously streams response tokens to the UI via evaluate_js."""
        def run_stream():
            def on_chunk(token):
                if self._window:
                    js_code = f"window.onStreamChunk({json.dumps(token)});"
                    self._window.evaluate_js(js_code)

            def on_complete(full_resp, tool_info, audio_b64=None):
                if self._window:
                    js_code = f"window.onStreamComplete({json.dumps(full_resp)}, {json.dumps(tool_info)}, {json.dumps(audio_b64)});"
                    self._window.evaluate_js(js_code)

            def on_tool(tool_info):
                if self._window:
                    js_code = f"window.onToolExecuted({json.dumps(tool_info)});"
                    self._window.evaluate_js(js_code)

            self.engine.stream_chat(
                session_id=session_id,
                user_message=user_message,
                on_chunk=on_chunk,
                on_complete=on_complete,
                on_tool=on_tool,
                attachments=attachments
            )

        thread = threading.Thread(target=run_stream, daemon=True)
        thread.start()
        return {"status": "started"}

    def toggle_voice(self, enabled):
        if self.voice_engine:
            self.voice_engine.set_enabled(bool(enabled))
            return self.voice_engine.is_enabled()
        return False

    def get_sessions(self):
        return self.history_mgr.list_sessions()

    def create_session(self):
        return self.history_mgr.create_session("New Conversation")

    def load_session(self, session_id):
        s = self.history_mgr.get_session(session_id)
        if not s:
            s = self.history_mgr.create_session("New Conversation")
        return s

    def delete_session(self, session_id):
        self.history_mgr.delete_session(session_id)
        return self.history_mgr.list_sessions()

    def clear_session_messages(self, session_id):
        session = self.history_mgr.get_session(session_id)
        if session:
            session["messages"] = []
            self.history_mgr._save()
        return True

    def get_memory(self):
        return self.memory_mgr.get_memory()

    def update_profile(self, name, career_goal, education):
        self.memory_mgr.update_profile_field("name", name)
        self.memory_mgr.update_profile_field("career_goal", career_goal)
        self.memory_mgr.update_profile_field("education", education)
        return self.memory_mgr.get_memory()

    def add_memory_item(self, category, item):
        self.memory_mgr.add_list_item(category, item)
        return self.memory_mgr.get_memory()

    def remove_memory_item(self, category, index):
        self.memory_mgr.remove_list_item(category, index)
        return self.memory_mgr.get_memory()

    def get_models(self):
        return self.engine.get_installed_models()

    def set_model(self, model_name):
        self.engine.set_model(model_name)
        return True

    def get_system_stats(self):
        return AssistantTools.get_system_stats()

    def execute_terminal_command(self, command):
        """Allows direct execution of PowerShell / terminal commands."""
        return AssistantTools.run_shell_command(command)

    def save_settings(self, settings):
        """Save settings updated from frontend UI."""
        if not isinstance(settings, dict):
            return {"status": "error", "message": "Invalid settings payload"}

        self.config_mgr.update_settings(settings)

        # Apply settings to assistant engine
        if "provider" in settings:
            self.engine.set_provider(settings["provider"])
        if "groq_api_key" in settings:
            self.engine.set_groq_api_key(settings["groq_api_key"])
        if "groq_model" in settings and self.engine.provider == "groq":
            self.engine.set_model(settings["groq_model"])
        if "ollama_model" in settings and self.engine.provider == "ollama":
            self.engine.set_model(settings["ollama_model"])
        if "ollama_url" in settings:
            self.engine.ollama_url = settings["ollama_url"].rstrip("/")
            self.engine.chat_url = f"{self.engine.ollama_url}/api/chat"
        if "confirm_sensitive_actions" in settings:
            self.engine.permission_guard.require_destructive_confirm = bool(settings["confirm_sensitive_actions"])
        if "confirm_personal_data_access" in settings:
            self.engine.permission_guard.require_privacy_confirm = bool(settings["confirm_personal_data_access"])

        return {"status": "success", "config": self.config_mgr.get_all()}

    def start_voice_recording(self):
        """Starts hardware microphone recording in background."""
        if self.mic_engine:
            ok = self.mic_engine.start_recording()
            return {"status": "recording" if ok else "error"}
        return {"status": "error", "message": "Microphone engine not available"}

    def stop_voice_recording(self):
        """Stops microphone recording and transcribes via Groq Whisper."""
        if self.mic_engine:
            wav_bytes = self.mic_engine.stop_recording()
            groq_key = self.config_mgr.get("groq_api_key", "")
            text = self.mic_engine.transcribe(wav_bytes, groq_api_key=groq_key)
            return {"status": "success", "text": text}
        return {"status": "error", "text": ""}

    def select_media_files(self):
        """Opens native Windows file dialog for selecting photos or videos."""
        if not self._window:
            return []
        file_types = (
            "Media Files (*.jpg;*.jpeg;*.png;*.webp;*.gif;*.bmp;*.mp4;*.mov;*.avi;*.mkv;*.webm;*.mp3;*.wav)",
            "Image Files (*.jpg;*.jpeg;*.png;*.webp;*.gif;*.bmp)",
            "Video Files (*.mp4;*.mov;*.avi;*.mkv;*.webm)",
            "All Files (*.*)"
        )
        try:
            res = self._window.create_file_dialog(
                webview.OPEN_DIALOG,
                allow_multiple=True,
                file_types=file_types
            )
            if not res:
                return []

            selected = []
            for path_str in res:
                p = Path(path_str)
                if p.exists():
                    ext = p.suffix.lower()
                    mtype = "image" if ext in [".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"] else (
                        "video" if ext in [".mp4", ".mov", ".avi", ".mkv", ".webm"] else (
                            "audio" if ext in [".mp3", ".wav", ".m4a"] else "file"
                        )
                    )
                    selected.append({
                        "name": p.name,
                        "path": str(p.resolve()),
                        "size": p.stat().st_size,
                        "type": mtype
                    })
            return selected
        except Exception as e:
            print(f"[AssistantApi] select_media_files error: {e}")
            return []

    def upload_media_file(self, filename, base64_data):
        """Saves pasted or dropped base64 media file into media/uploads."""
        try:
            upload_dir = Path(__file__).resolve().parent.parent / "media" / "uploads"
            upload_dir.mkdir(parents=True, exist_ok=True)

            if "," in base64_data:
                _, base64_data = base64_data.split(",", 1)

            raw_bytes = base64.b64decode(base64_data)

            orig_name = Path(filename).name if filename else "upload"
            stem = Path(orig_name).stem
            suffix = Path(orig_name).suffix.lower()
            if not suffix:
                suffix = ".png"

            timestamp = time.strftime("%Y%m%d_%H%M%S")
            target_path = upload_dir / f"{stem}_{timestamp}{suffix}"
            target_path.write_bytes(raw_bytes)

            ext = suffix.lower()
            mtype = "image" if ext in [".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"] else (
                "video" if ext in [".mp4", ".mov", ".avi", ".mkv", ".webm"] else (
                    "audio" if ext in [".mp3", ".wav", ".m4a"] else "file"
                )
            )

            return {
                "success": True,
                "name": target_path.name,
                "path": str(target_path.resolve()),
                "size": len(raw_bytes),
                "type": mtype
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_media_data_url(self, file_path):
        """Reads a local media file and returns a base64 data URL for webview rendering."""
        try:
            p = Path(file_path).expanduser().resolve()
            if not p.exists():
                return None
            mime, _ = mimetypes.guess_type(str(p))
            if not mime:
                ext = p.suffix.lower()
                if ext in [".jpg", ".jpeg"]:
                    mime = "image/jpeg"
                elif ext == ".png":
                    mime = "image/png"
                elif ext == ".webp":
                    mime = "image/webp"
                elif ext == ".gif":
                    mime = "image/gif"
                elif ext == ".mp4":
                    mime = "video/mp4"
                elif ext == ".webm":
                    mime = "video/webm"
                elif ext == ".mp3":
                    mime = "audio/mp3"
                else:
                    mime = "application/octet-stream"

            data = p.read_bytes()
            b64 = base64.b64encode(data).decode("utf-8")
            return f"data:{mime};base64,{b64}"
        except Exception as e:
            print(f"[AssistantApi] get_media_data_url error: {e}")
            return None

    def reveal_in_explorer(self, file_path):
        """Reveals the given file or folder in Windows File Explorer."""
        return AssistantTools.reveal_in_explorer(file_path)

    def open_document_file(self, file_path):
        """Opens a presentation, Word document, or PDF directly in default OS application."""
        return AssistantTools.open_file(file_path)


def start_desktop_app():
    """Initializes and runs the Jarvis PyWebView desktop application with full autonomous agent capabilities."""
    config_mgr = ConfigManager()
    memory_mgr = MemoryManager()
    history_mgr = HistoryManager()
    permission_guard = PermissionGuard(
        require_destructive_confirm=config_mgr.get("confirm_sensitive_actions", True),
        require_privacy_confirm=config_mgr.get("confirm_personal_data_access", True)
    )
    voice_engine = VoiceEngine(enabled=config_mgr.get("voice_enabled", True))
    mic_engine = MicrophoneEngine()
    engine = AssistantEngine(
        memory_mgr=memory_mgr,
        history_mgr=history_mgr,
        config_mgr=config_mgr,
        voice_engine=voice_engine,
        permission_guard=permission_guard
    )

    api = AssistantApi(memory_mgr, history_mgr, engine, voice_engine, config_mgr=config_mgr, mic_engine=mic_engine)

    html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web", "index.html")

    window = webview.create_window(
        title="JARVIS - Autonomous AI Assistant",
        url=html_path,
        js_api=api,
        width=1140,
        height=780,
        min_size=(880, 620),
        background_color="#0d0d0d"
    )

    api.set_window(window)
    webview.start(debug=False)

if __name__ == "__main__":
    start_desktop_app()
