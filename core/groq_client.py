import json
import requests

GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_GROQ_MODEL = "qwen/qwen3.8-27b"

AVAILABLE_GROQ_MODELS = [
    {"id": "qwen/qwen3.8-27b", "name": "Qwen 3.8 27B (Recommended - Fast & Intelligent)"},
    {"id": "openai/gpt-oss-120b", "name": "OpenAI GPT-OSS 120B (Deep Reasoning)"},
    {"id": "groq/compound-mini", "name": "Groq Compound Mini (Fast Autonomous Agent)"},
    {"id": "groq/compound", "name": "Groq Compound (Agent System)"},
    {"id": "openai/gpt-oss-20b", "name": "OpenAI GPT-OSS 20B (Instant)"},
    {"id": "llama-3.3-70b-versatile", "name": "Llama 3.3 70B (Meta)"},
    {"id": "llama-3.1-8b-instant", "name": "Llama 3.1 8B (Instant)"}
]

class GroqClient:
    """Client for Groq Cloud ultra-fast inference with dynamic model detection."""

    def __init__(self, api_key: str = "", model: str = DEFAULT_GROQ_MODEL):
        self.api_key = api_key.strip()
        self.model = model or DEFAULT_GROQ_MODEL

    def set_api_key(self, api_key: str):
        self.api_key = api_key.strip()

    def set_model(self, model: str):
        self.model = model

    def get_dynamic_models(self) -> list:
        """Dynamically fetch models available to the current Groq API key."""
        if not self.is_configured():
            return AVAILABLE_GROQ_MODELS
        try:
            r = requests.get(
                "https://api.groq.com/openai/v1/models",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=4
            )
            if r.status_code == 200:
                data = r.json().get("data", [])
                models = []
                for item in data:
                    mid = item.get("id", "")
                    if mid and "whisper" not in mid and "guard" not in mid and "orpheus" not in mid:
                        models.append({"id": mid, "name": mid})
                if models:
                    return models
        except Exception:
            pass
        return AVAILABLE_GROQ_MODELS

    def is_configured(self) -> bool:
        return bool(self.api_key and len(self.api_key) > 10)

    def test_connection(self) -> dict:
        """Tests the Groq API key with a minimal request."""
        if not self.is_configured():
            return {"success": False, "error": "Groq API key is not configured."}

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": "Hi"}],
            "max_tokens": 5
        }

        try:
            r = requests.post(GROQ_ENDPOINT, headers=headers, json=payload, timeout=10)
            if r.status_code == 200:
                return {"success": True, "message": "Groq API connection verified successfully!"}
            elif r.status_code == 401:
                return {"success": False, "error": "Invalid Groq API Key. Please check your key at console.groq.com."}
            else:
                return {"success": False, "error": f"Groq Error (HTTP {r.status_code}): {r.text}"}
        except Exception as e:
            return {"success": False, "error": f"Could not connect to Groq: {e}"}

    def stream_chat(self, messages: list, on_chunk, temperature: float = 0.6, max_tokens: int = 2048) -> str:
        """
        Streams completions from Groq using Server-Sent Events (SSE).
        Invokes on_chunk(token) for real-time typewriter display.
        Returns the full response string.
        """
        if not self.is_configured():
            err_msg = "⚠️ Groq API key is missing. Please enter your free key in Settings (get it at console.groq.com)."
            on_chunk(err_msg)
            return err_msg

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True
        }

        full_content = ""
        try:
            response = requests.post(GROQ_ENDPOINT, headers=headers, json=payload, stream=True, timeout=60)

            if response.status_code == 404 and self.model != "qwen/qwen3.8-27b":
                # Automatically fallback to available working model
                self.model = "qwen/qwen3.8-27b"
                payload["model"] = self.model
                response = requests.post(GROQ_ENDPOINT, headers=headers, json=payload, stream=True, timeout=60)

            if response.status_code == 401:
                err_msg = "❌ Error: Invalid Groq API Key. Please check your key in Settings."
                on_chunk(err_msg)
                return err_msg
            elif response.status_code != 200:
                err_msg = f"❌ Groq API Error ({response.status_code}): {response.text}"
                on_chunk(err_msg)
                return err_msg

            for line in response.iter_lines():
                if not line:
                    continue
                line_str = line.decode("utf-8") if isinstance(line, bytes) else line
                if line_str.startswith("data: "):
                    data_body = line_str[6:].strip()
                    if data_body == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_body)
                        choices = chunk.get("choices", [])
                        if choices:
                            delta = choices[0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                full_content += content
                                on_chunk(content)
                    except Exception:
                        continue

            return full_content

        except requests.exceptions.ConnectionError:
            err_msg = "❌ Network Error: Could not connect to Groq servers. Please check your internet connection."
            on_chunk(err_msg)
            return err_msg
        except Exception as e:
            err_msg = f"❌ Error during Groq streaming: {str(e)}"
            on_chunk(err_msg)
            return err_msg

    def _do_stream(self, messages: list, on_chunk, model: str, max_tokens: int = 2048) -> str | None:
        """Internal: attempts a streaming request with the given model. Returns None on 404."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "stream": True,
        }
        try:
            response = requests.post(GROQ_ENDPOINT, headers=headers, json=payload, stream=True, timeout=60)
            if response.status_code == 404:
                return None  # Signal caller to try next model
            if response.status_code == 401:
                err_msg = "❌ Error: Invalid Groq API Key. Please check your key in Settings."
                on_chunk(err_msg)
                return err_msg
            if response.status_code != 200:
                err_msg = f"❌ Groq API Error ({response.status_code}): {response.text}"
                on_chunk(err_msg)
                return err_msg

            full_content = ""
            for line in response.iter_lines():
                if not line:
                    continue
                line_str = line.decode("utf-8") if isinstance(line, bytes) else line
                if line_str.startswith("data: "):
                    data_body = line_str[6:].strip()
                    if data_body == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_body)
                        choices = chunk.get("choices", [])
                        if choices:
                            delta = choices[0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                full_content += content
                                on_chunk(content)
                    except Exception:
                        continue
            return full_content
        except Exception as e:
            err_msg = f"❌ Error during streaming: {str(e)}"
            on_chunk(err_msg)
            return err_msg

    def stream_vision_chat(self, user_text: str, image_paths: list, on_chunk, max_tokens: int = 2048) -> str:
        """
        Sends image(s) + user question to Groq's vision model and streams the answer.
        Supports reading text from images, analyzing diagrams, solving visible problems.
        Auto-falls back across vision-capable models if one returns 404.
        """
        if not self.is_configured():
            err_msg = "⚠️ Groq API key is missing. Please enter your key in Settings."
            on_chunk(err_msg)
            return err_msg

        import base64
        import mimetypes

        # Build vision content block
        content = []
        encoded_count = 0
        for img_path in image_paths[:3]:   # max 3 images per request
            try:
                mime = mimetypes.guess_type(img_path)[0] or "image/jpeg"
                with open(img_path, "rb") as f:
                    b64_data = base64.b64encode(f.read()).decode("utf-8")
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime};base64,{b64_data}"}
                })
                encoded_count += 1
            except Exception as e:
                print(f"[GroqClient] Could not encode image {img_path}: {e}")

        if encoded_count == 0:
            err_msg = "❌ Could not read any of the attached images. Please try uploading again."
            on_chunk(err_msg)
            return err_msg

        content.append({
            "type": "text",
            "text": user_text if user_text.strip() else "Please describe this image in detail."
        })
        messages = [{"role": "user", "content": content}]

        # Try vision models in priority order (auto-fallback on 404)
        VISION_MODELS = [
            "meta-llama/llama-4-scout-17b-16e-instruct",
            "llama-3.2-90b-vision-preview",
            "llama-3.2-11b-vision-preview",
        ]
        for model in VISION_MODELS:
            print(f"[GroqClient] Trying vision model: {model}")
            result = self._do_stream(messages, on_chunk, model, max_tokens)
            if result is not None:
                return result

        err_msg = "⚠️ Vision analysis unavailable — no compatible vision model found on your Groq plan. Please check console.groq.com for available vision models."
        on_chunk(err_msg)
        return err_msg
