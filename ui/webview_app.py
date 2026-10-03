import os
import json
import base64
import mimetypes
import time
import threading
from pathlib import Path

# Ensure Microsoft Edge WebView2 allows audio autoplay without transient gesture expiration
os.environ["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = "--autoplay-policy=no-user-gesture-required"

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

        from core.groq_client import usage_tracker

        return {
            "sessions": sessions,
            "active_session_id": active_id,
            "models": installed_models,
            "current_model": self.engine.model,
            "memory": self.memory_mgr.get_memory(),
            "system_stats": AssistantTools.get_system_stats(),
            "voice_enabled": self.voice_engine.is_enabled() if self.voice_engine else False,
            "voice_name": getattr(self.voice_engine, "voice", "en-GB-RyanNeural"),
            "config": self.config_mgr.get_all(),
            "usage_stats": usage_tracker.get_stats()
        }

    def send_message(self, user_message, session_id, attachments=None, voice_mode=False):
        """Asynchronously streams response tokens to the UI via evaluate_js with dynamic activity states."""
        def run_stream():
            def on_status(status_text, status_type="thinking", detail=""):
                if self._window:
                    js_code = f"window.onStatusUpdate({json.dumps(status_text)}, {json.dumps(status_type)}, {json.dumps(detail)});"
                    self._window.evaluate_js(js_code)

            def on_chunk(token):
                if self._window:
                    js_code = f"window.onStreamChunk({json.dumps(token)});"
                    self._window.evaluate_js(js_code)

            def on_complete(full_resp, tool_info, audio_b64=None, model_used=None):
                if self._window:
                    js_code = f"window.onStreamComplete({json.dumps(full_resp)}, {json.dumps(tool_info)}, {json.dumps(audio_b64)}, {json.dumps(model_used)}, {json.dumps(bool(voice_mode))});"
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
                attachments=attachments,
                on_status=on_status,
                voice_mode=voice_mode
            )

        thread = threading.Thread(target=run_stream, daemon=True)
        thread.start()
        return {"status": "started"}

    def toggle_voice(self, enabled):
        if self.voice_engine:
            self.voice_engine.set_enabled(bool(enabled))
            return self.voice_engine.is_enabled()
        return False

    def set_voice(self, voice_name):
        """Updates preferred voice in engine and config."""
        if self.voice_engine:
            self.voice_engine.set_voice(voice_name)
            self.config_mgr.set("voice_name", voice_name)
            return True
        return False

    def test_voice(self, voice_name=None):
        """Synthesizes a test phrase in English to verify audible speech output."""
        if voice_name and self.voice_engine:
            self.voice_engine.set_voice(voice_name)
        sample = "Good day, sir. JARVIS speech synthesis is online and speaking in English."
        b64 = None
        if self.voice_engine:
            b64 = self.voice_engine.synthesize_and_speak(sample, play_audio=True)
        return {"success": bool(b64), "audio_b64": b64, "text": sample}

    def speak_aloud(self, text: str):
        """Speaks any text aloud through the laptop speakers using JARVIS's British neural voice."""
        if self.voice_engine:
            self.voice_engine.speak_aloud(text)
            return True
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

    def get_usage_stats(self):
        """Returns token usage, generation counters, and rate limits."""
        from core.groq_client import usage_tracker
        return usage_tracker.get_stats()

    def set_window_on_top(self, stay_on_top: bool):
        """Controls whether the JARVIS desktop window stays on top of all other apps."""
        if self._window:
            try:
                self._window.on_top = bool(stay_on_top)
                return True
            except Exception as e:
                print(f"[AssistantApi] set_window_on_top error: {e}")
        return False

    def toggle_mini_mode(self, enabled=None):
        """Switches between full window mode and compact floating mini voice orb mode."""
        if not self._window:
            return False
        try:
            if enabled is None:
                enabled = not getattr(self, "_is_mini", False)

            if enabled:
                if not getattr(self, "_is_mini", False):
                    self._prev_width = self._window.width or 1140
                    self._prev_height = self._window.height or 780
                    self._prev_x = self._window.x
                    self._prev_y = self._window.y
                self._is_mini = True
                self._window.on_top = True
                self._window.resize(320, 180)
                try:
                    import ctypes
                    user32 = ctypes.windll.user32
                    screen_w = user32.GetSystemMetrics(0)
                    screen_h = user32.GetSystemMetrics(1)
                    target_x = max(0, screen_w - 340)
                    target_y = max(0, screen_h - 240)
                    self._window.move(target_x, target_y)
                except Exception:
                    pass
                return True
            else:
                self._is_mini = False
                prev_w = getattr(self, "_prev_width", 1140)
                prev_h = getattr(self, "_prev_height", 780)
                self._window.resize(prev_w, prev_h)
                if getattr(self, "_prev_x", None) is not None and getattr(self, "_prev_y", None) is not None:
                    try:
                        self._window.move(self._prev_x, self._prev_y)
                    except Exception:
                        pass
                return False
        except Exception as e:
            print(f"[AssistantApi] toggle_mini_mode error: {e}")
            return False

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
        if "google_api_key" in settings:
            self.engine.set_google_api_key(settings["google_api_key"])
        if "voice_name" in settings:
            self.set_voice(settings["voice_name"])

        return {"status": "success", "config": self.config_mgr.get_all()}

    def test_google_connection(self, api_key=None):
        """Tests Google Gemini API key connection."""
        if api_key:
            from core.gemini_client import GeminiClient
            client = GeminiClient(api_key=api_key)
            return client.test_connection()
        return self.engine.gemini_client.test_connection()

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
            if not file_path:
                return None
            clean_str = str(file_path).strip().strip("'\"")
            norm_str = os.path.normpath(clean_str)
            p = Path(norm_str).expanduser().resolve()
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
        min_size=(300, 160),
        background_color="#0d0d0d"
    )

    api.set_window(window)
    webview.start(debug=False)

if __name__ == "__main__":
    start_desktop_app()
