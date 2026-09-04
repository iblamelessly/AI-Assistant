import os
import json
import threading
import webview

from core.memory import MemoryManager
from core.history import HistoryManager
from core.tools import AssistantTools
from core.assistant import AssistantEngine

class AssistantApi:
    """Python API bridge exposed to the Webview UI."""

    def __init__(self, memory_mgr, history_mgr, engine):
        self.memory_mgr = memory_mgr
        self.history_mgr = history_mgr
        self.engine = engine
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
            "system_stats": AssistantTools.get_system_stats()
        }

    def send_message(self, user_message, session_id):
        """Asynchronously streams response tokens to the UI via evaluate_js."""
        def run_stream():
            def on_chunk(token):
                if self._window:
                    js_code = f"window.onStreamChunk({json.dumps(token)});"
                    self._window.evaluate_js(js_code)

            def on_complete(full_resp, tool_info):
                if self._window:
                    js_code = f"window.onStreamComplete({json.dumps(full_resp)}, {json.dumps(tool_info)});"
                    self._window.evaluate_js(js_code)

            def on_tool(tool_info):
                pass

            self.engine.stream_chat(
                session_id=session_id,
                user_message=user_message,
                on_chunk=on_chunk,
                on_complete=on_complete,
                on_tool=on_tool
            )

        thread = threading.Thread(target=run_stream, daemon=True)
        thread.start()
        return {"status": "started"}

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


def start_desktop_app():
    """Initializes and runs the Jarvis PyWebView desktop application."""
    memory_mgr = MemoryManager()
    history_mgr = HistoryManager()
    engine = AssistantEngine(memory_mgr, history_mgr)

    api = AssistantApi(memory_mgr, history_mgr, engine)

    html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web", "index.html")

    window = webview.create_window(
        title="JARVIS - Personal AI Assistant",
        url=html_path,
        js_api=api,
        width=1120,
        height=760,
        min_size=(860, 600),
        background_color="#080c14"
    )

    api.set_window(window)
    webview.start(debug=False)

if __name__ == "__main__":
    start_desktop_app()
