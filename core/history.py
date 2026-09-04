import os
import json
import uuid
import time
import threading

class HistoryManager:
    """Manages chat conversation history and sessions."""

    def __init__(self, history_file_path=None):
        if history_file_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.history_file = os.path.join(base_dir, "chat_sessions.json")
        else:
            self.history_file = history_file_path

        self._lock = threading.Lock()
        self.sessions = self._load()

    def _load(self):
        with self._lock:
            if os.path.exists(self.history_file):
                try:
                    with open(self.history_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if isinstance(data, dict) and "sessions" in data:
                            return data["sessions"]
                except Exception as e:
                    print(f"[HistoryManager] Error reading history: {e}")
            return []

    def _save(self):
        with self._lock:
            try:
                with open(self.history_file, "w", encoding="utf-8") as f:
                    json.dump({"sessions": self.sessions}, f, indent=2, ensure_ascii=False)
            except Exception as e:
                print(f"[HistoryManager] Error saving history: {e}")

    def list_sessions(self):
        with self._lock:
            result = []
            for s in reversed(self.sessions):
                result.append({
                    "id": s["id"],
                    "title": s.get("title", "New Conversation"),
                    "created_at": s.get("created_at", time.time()),
                    "message_count": len(s.get("messages", []))
                })
            return result

    def get_session(self, session_id):
        with self._lock:
            for s in self.sessions:
                if s["id"] == session_id:
                    return s
        return None

    def create_session(self, title="New Conversation"):
        new_session = {
            "id": str(uuid.uuid4()),
            "title": title,
            "created_at": time.time(),
            "messages": []
        }
        with self._lock:
            self.sessions.append(new_session)
        self._save()
        return new_session

    def add_message(self, session_id, role, content, tool_info=None):
        with self._lock:
            session = None
            for s in self.sessions:
                if s["id"] == session_id:
                    session = s
                    break

            if not session:
                session = {
                    "id": session_id,
                    "title": "New Conversation",
                    "created_at": time.time(),
                    "messages": []
                }
                self.sessions.append(session)

            msg = {
                "role": role,
                "content": content,
                "timestamp": time.time()
            }
            if tool_info:
                msg["tool_info"] = tool_info

            session["messages"].append(msg)

            # Auto-title session if it was "New Conversation" and user just spoke
            if role == "user" and session["title"] == "New Conversation":
                clean_title = content.strip().replace("\n", " ")
                if len(clean_title) > 32:
                    clean_title = clean_title[:32] + "..."
                session["title"] = clean_title

        self._save()

    def delete_session(self, session_id):
        with self._lock:
            self.sessions = [s for s in self.sessions if s["id"] != session_id]
        self._save()
        return True
