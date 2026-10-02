import json
import requests
from typing import List, Dict, Any
from .groq_client import usage_tracker

GEMINI_OPENAI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
GEMINI_REST_ENDPOINT_BASE = "https://generativelanguage.googleapis.com/v1beta/models"

AVAILABLE_GEMINI_MODELS = [
    {"id": "gemini-2.0-flash", "name": "Google Gemini 2.0 Flash (Next-Gen Reasoning & Speed)"},
    {"id": "gemini-1.5-pro", "name": "Google Gemini 1.5 Pro (Massive 2M Context & Deep Analysis)"},
    {"id": "gemini-1.5-flash", "name": "Google Gemini 1.5 Flash (Fast Multimodal)"}
]

DEFAULT_GEMINI_MODEL = "gemini-2.0-flash"


class GeminiClient:
    """
    Google Gemini Cloud inference client.
    Supports streaming completions, multimodal analysis, and dynamic model switching.
    Uses standard requests with zero external package dependencies.
    """

    def __init__(self, api_key: str = "", model: str = DEFAULT_GEMINI_MODEL):
        self.api_key = api_key.strip()
        self.model = model or DEFAULT_GEMINI_MODEL
        self.usage_tracker = usage_tracker

    def set_api_key(self, api_key: str):
        self.api_key = api_key.strip()

    def set_model(self, model: str):
        self.model = model

    def is_configured(self) -> bool:
        return bool(self.api_key and len(self.api_key) > 10)

    def test_connection(self) -> dict:
        """Tests the Google Gemini API key with a minimal request."""
        if not self.is_configured():
            return {"success": False, "error": "Google Gemini API key is not configured."}

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "gemini-2.0-flash",
            "messages": [{"role": "user", "content": "Hi"}],
            "max_tokens": 5
        }

        try:
            r = requests.post(GEMINI_OPENAI_ENDPOINT, headers=headers, json=payload, timeout=10)
            if r.status_code == 200:
                return {"success": True, "message": "Google Gemini API connection verified successfully!"}
            elif r.status_code in [400, 401, 403]:
                native_url = f"{GEMINI_REST_ENDPOINT_BASE}/gemini-2.0-flash:generateContent?key={self.api_key}"
                r2 = requests.post(native_url, json={"contents": [{"parts": [{"text": "Hi"}]}]}, timeout=10)
                if r2.status_code == 200:
                    return {"success": True, "message": "Google Gemini API verified via native endpoint!"}
                return {"success": False, "error": f"Invalid Google Gemini API Key (HTTP {r.status_code}): {r.text[:120]}"}
            else:
                return {"success": False, "error": f"Google Gemini Error (HTTP {r.status_code}): {r.text[:120]}"}
        except Exception as e:
            return {"success": False, "error": f"Could not connect to Google Gemini: {e}"}

    def stream_chat(self, messages: list, on_chunk, temperature: float = 0.7, max_tokens: int = 2048, model_override: str = None) -> str:
        """
        Streams completions from Google Gemini using Server-Sent Events (SSE).
        Tries Google's OpenAI-compatible endpoint first, then falls back to native REST streaming.
        """
        if not self.is_configured():
            err_msg = "⚠️ Google Gemini API key is missing. Please enter your key in Settings."
            on_chunk(err_msg)
            return err_msg

        target_model = model_override or self.model or DEFAULT_GEMINI_MODEL
        if target_model.startswith("models/"):
            target_model = target_model[7:]

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": target_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True
        }

        try:
            response = requests.post(GEMINI_OPENAI_ENDPOINT, headers=headers, json=payload, stream=True, timeout=60)
            if response.status_code == 200:
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

                if full_content:
                    comp_est = max(1, len(full_content) // 4)
                    prompt_est = sum(max(1, len(m.get("content", "")) // 4) for m in messages if isinstance(m.get("content"), str))
                    self.usage_tracker.record_chat_tokens(prompt_est, comp_est, prompt_est + comp_est)
                    return full_content
        except Exception as e:
            print(f"[GeminiClient] OpenAI endpoint error: {e}")

        return self._stream_native_rest(messages, on_chunk, target_model, temperature, max_tokens)

    def _stream_native_rest(self, messages: list, on_chunk, model: str, temperature: float, max_tokens: int) -> str:
        url = f"{GEMINI_REST_ENDPOINT_BASE}/{model}:streamGenerateContent?alt=sse&key={self.api_key}"

        contents = []
        system_instruction = None
        for m in messages:
            role = m.get("role")
            text = m.get("content", "")
            if role == "system":
                system_instruction = {"parts": [{"text": text}]}
            elif role == "user":
                contents.append({"role": "user", "parts": [{"text": text}]})
            elif role == "assistant":
                contents.append({"role": "model", "parts": [{"text": text}]})

        body = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens
            }
        }
        if system_instruction:
            body["systemInstruction"] = system_instruction

        try:
            headers = {"Content-Type": "application/json"}
            resp = requests.post(url, headers=headers, json=body, stream=True, timeout=60)
            if resp.status_code != 200:
                err_msg = f"❌ Google Gemini API Error ({resp.status_code}): {resp.text[:160]}"
                on_chunk(err_msg)
                return err_msg

            full_content = ""
            for line in resp.iter_lines():
                if not line:
                    continue
                line_str = line.decode("utf-8") if isinstance(line, bytes) else line
                if line_str.startswith("data: "):
                    data_body = line_str[6:].strip()
                    try:
                        chunk = json.loads(data_body)
                        candidates = chunk.get("candidates", [])
                        if candidates:
                            parts = candidates[0].get("content", {}).get("parts", [])
                            for p in parts:
                                txt = p.get("text", "")
                                if txt:
                                    full_content += txt
                                    on_chunk(txt)
                    except Exception:
                        continue

            if full_content:
                comp_est = max(1, len(full_content) // 4)
                prompt_est = 250
                self.usage_tracker.record_chat_tokens(prompt_est, comp_est, prompt_est + comp_est)
                return full_content

            err_msg = "⚠️ Gemini generated an empty response."
            on_chunk(err_msg)
            return err_msg
        except Exception as ex:
            err_msg = f"❌ Google Gemini streaming connection error: {ex}"
            on_chunk(err_msg)
            return err_msg
