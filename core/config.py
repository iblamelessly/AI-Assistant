import os
import json
import threading

DEFAULT_CONFIG = {
    "provider": "groq",  # "groq" or "ollama"
    "groq_api_key": "",
    "groq_model": "super-ai",
    "google_api_key": "",
    "google_model": "gemini-3.8-flash",
    "ollama_model": "qwen3:1.7b",
    "ollama_url": "http://localhost:11434",
    "voice_enabled": True,
    "voice_conversation_mode": False,
    "continuous_listen": True,
    "confirm_sensitive_actions": True,
    "confirm_personal_data_access": True,
    "window_mode": "normal",
    "window_x": 100,
    "window_y": 100,
    "start_on_boot": False,
    "max_agent_steps": 10
}

class ConfigManager:
    """Manages local, private application configuration (API keys, providers, preferences)."""

    def __init__(self, config_path=None):
        if config_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.config_file = os.path.join(base_dir, "config.json")
        else:
            self.config_file = config_path

        self._lock = threading.Lock()
        self.config = self._load()

    def _load(self):
        with self._lock:
            data = dict(DEFAULT_CONFIG)
            if os.path.exists(self.config_file):
                try:
                    with open(self.config_file, "r", encoding="utf-8") as f:
                        saved = json.load(f)
                        if isinstance(saved, dict):
                            data.update(saved)
                except Exception as e:
                    print(f"[ConfigManager] Error reading config: {e}")

            # Check environment variable fallback for Groq API key
            env_key = os.environ.get("GROQ_API_KEY", "").strip()
            if env_key and not data.get("groq_api_key"):
                data["groq_api_key"] = env_key

            # Check environment variable fallback for Google API key
            env_google = (os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY", "")).strip()
            if env_google and not data.get("google_api_key"):
                data["google_api_key"] = env_google

            return data

    def save(self):
        with self._lock:
            try:
                with open(self.config_file, "w", encoding="utf-8") as f:
                    json.dump(self.config, f, indent=4, ensure_ascii=False)
            except Exception as e:
                print(f"[ConfigManager] Error saving config: {e}")

    def get(self, key, default=None):
        with self._lock:
            return self.config.get(key, default)

    def set(self, key, value):
        with self._lock:
            self.config[key] = value
        self.save()

    def get_all(self):
        with self._lock:
            return dict(self.config)

    def update_settings(self, new_settings: dict):
        with self._lock:
            for k, v in new_settings.items():
                if k in DEFAULT_CONFIG:
                    self.config[k] = v
        self.save()
        return self.get_all()
