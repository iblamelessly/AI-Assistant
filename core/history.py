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
            sessions = []
            if os.path.exists(self.history_file):
                try:
                    with open(self.history_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if isinstance(data, dict) and "sessions" in data:
                            sessions = data["sessions"]
                except Exception as e:
                    print(f"[HistoryManager] Error reading history: {e}")

            # 1. Sanitize sessions so every session has a valid string ID and list of messages
            cleaned = []
            needs_save = False
            for s in sessions:
                if not isinstance(s, dict):
                    continue
                s_id = s.get("id")
                if not s_id or s_id == "None" or str(s_id).strip() == "":
                    s["id"] = str(uuid.uuid4())
                    needs_save = True
                if "messages" not in s or not isinstance(s["messages"], list):
                    s["messages"] = []
                    needs_save = True
                cleaned.append(s)

            # 2. Stitch fragmented sessions where user question and assistant reply were split into two separate sessions
            stitched = []
            i = 0
            while i < len(cleaned):
                curr = cleaned[i]
                curr_msgs = curr.get("messages", [])
                
                # Check if current has 1 user message and next has 1 assistant message created around the same time
                if (i + 1 < len(cleaned) and 
                    len(curr_msgs) == 1 and curr_msgs[0].get("role") == "user"):
                    nxt = cleaned[i + 1]
                    nxt_msgs = nxt.get("messages", [])
                    if (len(nxt_msgs) == 1 and nxt_msgs[0].get("role") == "assistant" and 
                        nxt.get("title") in ["New Conversation", "", None] and
                        abs(nxt.get("created_at", 0) - curr.get("created_at", 0)) < 120):
                        # Merge assistant reply into user session
                        curr_msgs.append(nxt_msgs[0])
                        stitched.append(curr)
                        needs_save = True
                        i += 2
                        continue

                # Remove completely empty sessions unless it is the only session
                if len(curr_msgs) == 0 and len(cleaned) > 1:
                    needs_save = True
                    i += 1
                    continue

                stitched.append(curr)
                i += 1

            if needs_save:
                try:
                    with open(self.history_file, "w", encoding="utf-8") as f:
                        json.dump({"sessions": stitched}, f, indent=2, ensure_ascii=False)
                except Exception as e:
                    print(f"[HistoryManager] Error saving sanitized history: {e}")

            return stitched

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
                s_id = s.get("id")
                if not s_id:
                    continue
                result.append({
                    "id": str(s_id),
                    "title": s.get("title", "New Conversation"),
                    "created_at": s.get("created_at", time.time()),
                    "message_count": len(s.get("messages", []))
                })
            return result

    def get_session(self, session_id):
        if not session_id or session_id in ["ephemeral", "transient", "null", "undefined", "None"]:
            return None
        target = str(session_id).strip()
        with self._lock:
            for s in self.sessions:
                if str(s.get("id", "")).strip() == target:
                    return s
        return None

    def create_session(self, title="New Conversation", session_id=None):
        new_id = str(session_id).strip() if session_id else str(uuid.uuid4())
        new_session = {
            "id": new_id,
            "title": title,
            "created_at": time.time(),
            "messages": []
        }
        with self._lock:
            self.sessions.append(new_session)
        self._save()
        return new_session

    def add_message(self, session_id, role, content, tool_info=None, attachments=None):
        if not session_id or session_id in ["ephemeral", "transient", "null", "undefined", "None"]:
            return None

        target = str(session_id).strip()
        with self._lock:
            session = None
            for s in self.sessions:
                if str(s.get("id", "")).strip() == target:
                    session = s
                    break

            if not session:
                session = {
                    "id": target,
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
            if attachments:
                msg["attachments"] = attachments

            session["messages"].append(msg)

            # Auto-title session if it was "New Conversation" and user just spoke
            if role == "user" and session.get("title") in ["New Conversation", "", None]:
                clean_title = content.strip().replace("\n", " ")
                if len(clean_title) > 32:
                    clean_title = clean_title[:32] + "..."
                session["title"] = clean_title

        self._save()
        return session

    def delete_session(self, session_id):
        with self._lock:
            self.sessions = [s for s in self.sessions if s["id"] != session_id]
        self._save()
        return True
