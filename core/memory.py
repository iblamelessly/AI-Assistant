import os
import json
import threading
import requests

DEFAULT_MEMORY_STRUCTURE = {
    "user": {
        "name": "",
        "career_goal": "",
        "education": "",
        "projects": [],
        "skills": [],
        "preferences": [],
        "other": []
    }
}

class MemoryManager:
    """Thread-safe persistent memory manager with background extraction."""

    def __init__(self, memory_file_path=None):
        if memory_file_path is None:
            # Default to memory.json in parent directory of core
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.memory_file = os.path.join(base_dir, "memory.json")
        else:
            self.memory_file = memory_file_path

        self._lock = threading.Lock()
        self._listeners = []
        self.memory = self._load_memory()

    def add_listener(self, callback):
        """Register a callback for memory updates."""
        if callback not in self._listeners:
            self._listeners.append(callback)

    def _notify_listeners(self):
        for callback in self._listeners:
            try:
                callback(self.get_memory())
            except Exception as e:
                print(f"[MemoryManager] Listener callback error: {e}")

    def _load_memory(self):
        with self._lock:
            if os.path.exists(self.memory_file):
                try:
                    with open(self.memory_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        # Ensure basic structure exists
                        if "user" not in data:
                            data["user"] = {}
                        for key, default_val in DEFAULT_MEMORY_STRUCTURE["user"].items():
                            if key not in data["user"]:
                                data["user"][key] = default_val if not isinstance(default_val, list) else []
                        return data
                except Exception as e:
                    print(f"[MemoryManager] Error reading memory file: {e}")

            # If memory.json does not exist, check for memory.example.json template
            example_file = os.path.join(os.path.dirname(self.memory_file), "memory.example.json")
            if os.path.exists(example_file):
                try:
                    with open(example_file, "r", encoding="utf-8") as f:
                        template_data = json.load(f)
                        # Save template as local memory.json
                        with open(self.memory_file, "w", encoding="utf-8") as out:
                            json.dump(template_data, out, indent=4, ensure_ascii=False)
                        return template_data
                except Exception:
                    pass

            # Return copy of default
            return json.loads(json.dumps(DEFAULT_MEMORY_STRUCTURE))

    def save_memory(self):
        with self._lock:
            try:
                with open(self.memory_file, "w", encoding="utf-8") as f:
                    json.dump(self.memory, f, indent=4, ensure_ascii=False)
            except Exception as e:
                print(f"[MemoryManager] Error saving memory: {e}")
        self._notify_listeners()

    def get_memory(self):
        with self._lock:
            return json.loads(json.dumps(self.memory))

    def get_formatted_summary(self):
        """Returns clean formatted JSON string of user memory for the system prompt."""
        with self._lock:
            return json.dumps(self.memory["user"], indent=2)

    def update_profile_field(self, field, value):
        """Updates string fields like name, career_goal, education."""
        with self._lock:
            if field in ["name", "career_goal", "education"]:
                self.memory["user"][field] = str(value).strip()
        self.save_memory()

    def add_list_item(self, category, item):
        """Adds an item to projects, skills, preferences, or other."""
        category = category.lower().strip()
        item = str(item).strip()
        if not item:
            return False

        with self._lock:
            if category in ["projects", "skills", "preferences", "other"]:
                if item not in self.memory["user"][category]:
                    self.memory["user"][category].append(item)
                    self.save_memory()
                    return True
        return False

    def remove_list_item(self, category, item_or_index):
        """Removes an item from list categories."""
        category = category.lower().strip()
        with self._lock:
            if category in ["projects", "skills", "preferences", "other"]:
                items = self.memory["user"][category]
                if isinstance(item_or_index, int) and 0 <= item_or_index < len(items):
                    items.pop(item_or_index)
                    self.save_memory()
                    return True
                elif item_or_index in items:
                    items.remove(item_or_index)
                    self.save_memory()
                    return True
        return False

    def trigger_background_extraction(self, user_message, ollama_url, model):
        """Launches memory extraction in a separate daemon thread to avoid blocking."""
        thread = threading.Thread(
            target=self._extract_memory_worker,
            args=(user_message, ollama_url, model),
            daemon=True
        )
        thread.start()

    def _extract_memory_worker(self, user_message, ollama_url, model):
        # Skip trivial or short messages
        if len(user_message.strip()) < 5:
            return

        memory_prompt = f"""You are a memory extraction system for a personal AI assistant.
Analyze the user's message and identify ONLY information that is useful to remember about the user for future conversations.

Current message:
"{user_message}"

Return ONLY valid JSON in this exact format:
{{
    "name": "",
    "career_goal": "",
    "education": "",
    "project": "",
    "skill": "",
    "preference": "",
    "other": ""
}}

Rules:
- Only include facts explicitly stated by the user about themselves.
- Do not guess or invent anything.
- Leave fields empty if there is no relevant information.
- Do not save normal questions or temporary conversation.
- If the user gives a new project, put it in "project".
- If the user gives a career goal, put it in "career_goal".
- If the user gives their name, put it in "name".
- If the user gives education information, put it in "education".
- If the user mentions a skill they have or are learning, put it in "skill".
- If the user states a preference, put it in "preference".
"""

        try:
            response = requests.post(
                ollama_url,
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": memory_prompt}],
                    "stream": False,
                    "think": False
                },
                timeout=20
            )

            if response.status_code != 200:
                return

            result = response.json().get("message", {}).get("content", "").strip()
            # Remove markdown code fences if present
            if "```" in result:
                result = result.replace("```json", "").replace("```", "").strip()

            extracted = json.loads(result)

            updated = False
            with self._lock:
                if extracted.get("name") and extracted["name"].strip():
                    self.memory["user"]["name"] = extracted["name"].strip()
                    updated = True

                if extracted.get("career_goal") and extracted["career_goal"].strip():
                    self.memory["user"]["career_goal"] = extracted["career_goal"].strip()
                    updated = True

                if extracted.get("education") and extracted["education"].strip():
                    self.memory["user"]["education"] = extracted["education"].strip()
                    updated = True

                for key, target_list in [
                    ("project", "projects"),
                    ("skill", "skills"),
                    ("preference", "preferences"),
                    ("other", "other")
                ]:
                    val = extracted.get(key)
                    if val and isinstance(val, str) and val.strip():
                        val = val.strip()
                        if val not in self.memory["user"][target_list]:
                            self.memory["user"][target_list].append(val)
                            updated = True

            if updated:
                self.save_memory()
                print(f"[MemoryManager] Successfully updated memories in background!")

        except Exception as e:
            # Silent fail for background extraction to never disrupt conversation
            pass
