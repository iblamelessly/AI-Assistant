import json
import requests
from typing import List, Dict, Any
from .groq_client import usage_tracker

GEMINI_OPENAI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
GEMINI_REST_ENDPOINT_BASE = "https://generativelanguage.googleapis.com/v1beta/models"

AVAILABLE_GEMINI_MODELS = [
    {"id": "gemini-3.8-flash", "name": "Google Gemini 3.8 Flash (Flagship Intelligence & Agents)"},
    {"id": "gemini-3.5-flash", "name": "Google Gemini 3.5 Flash (High-Performance Coding & Reasoning)"},
    {"id": "gemini-3.5-flash-lite", "name": "Google Gemini 3.5 Flash-Lite (Fast & Cost-Efficient)"},
    {"id": "gemini-3.6-flash", "name": "Google Gemini 3.6 Flash (Balanced Token Efficiency)"}
]

DEFAULT_GEMINI_MODEL = "gemini-3.8-flash"


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
        """Tests the Google Gemini API key with a minimal request using the native REST endpoint."""
        if not self.is_configured():
            return {"success": False, "error": "Google Gemini API key is not configured."}

        test_model = DEFAULT_GEMINI_MODEL
        native_url = f"{GEMINI_REST_ENDPOINT_BASE}/{test_model}:generateContent?key={self.api_key}"
        try:
            r = requests.post(
                native_url,
                json={"contents": [{"parts": [{"text": "Hi"}]}], "generationConfig": {"maxOutputTokens": 5}},
                timeout=15
            )
            if r.status_code == 200:
                return {"success": True, "message": f"Google Gemini API verified! ({test_model})", "models": [m["id"] for m in AVAILABLE_GEMINI_MODELS]}
            else:
                return {"success": False, "error": f"Google Gemini Error (HTTP {r.status_code}): {r.text[:200]}"}
        except Exception as e:
            return {"success": False, "error": f"Could not connect to Google Gemini: {e}"}

    def stream_chat(self, messages: list, on_chunk, temperature: float = 0.7, max_tokens: int = 2048, model_override: str = None) -> str:
        """
        Streams completions from Google Gemini.
        Tries native REST streaming (key as query param) first for maximum compatibility,
        then falls back to OpenAI-compatible endpoint.
        """
        if not self.is_configured():
            err_msg = "⚠️ Google Gemini API key is missing. Please enter your key in Settings."
            on_chunk(err_msg)
            return err_msg

        target_model = model_override or self.model or DEFAULT_GEMINI_MODEL
        if target_model.startswith("models/"):
            target_model = target_model[7:]

        # Try native REST streaming first (most reliable with API keys)
        result = self._stream_native_rest(messages, on_chunk, target_model, temperature, max_tokens)
        if result and not result.startswith("❌"):
            return result

        # Fallback: try OpenAI-compatible endpoint
        return self._stream_openai_compat(messages, on_chunk, target_model, temperature, max_tokens)

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

            return "❌ Gemini generated an empty response."
        except Exception as ex:
            return f"❌ Google Gemini streaming error: {ex}"

    def _stream_openai_compat(self, messages: list, on_chunk, model: str, temperature: float, max_tokens: int) -> str:
        """Fallback: stream via Google's OpenAI-compatible endpoint (Bearer auth)."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model,
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
            print(f"[GeminiClient] OpenAI-compat endpoint error: {e}")

        err_msg = "❌ Google Gemini could not generate a response via any endpoint."
        on_chunk(err_msg)
        return err_msg
