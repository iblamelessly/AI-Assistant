import json
import requests
from pathlib import Path

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

class UsageTracker:
    """Tracks token consumption, rate limit headers, and generative asset counts."""

    def __init__(self):
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.total_tokens = 0
        self.total_requests = 0
        self.ai_images_count = 0
        self.ai_videos_count = 0
        self.documents_count = 0
        self.rate_limit_remaining_tokens = None
        self.rate_limit_limit_tokens = None
        self.rate_limit_remaining_requests = None
        self.rate_limit_limit_requests = None
        self.rate_limit_reset_tokens = None
        self.rate_limit_reset_requests = None

    def _get_storage_path(self):
        try:
            return Path(__file__).resolve().parent.parent / "usage_stats.json"
        except Exception:
            return Path("usage_stats.json")

    def _load_persisted(self):
        try:
            p = self._get_storage_path()
            if p.exists():
                with open(p, "r", encoding="utf-8") as f:
                    d = json.load(f)
                    self.prompt_tokens = d.get("prompt_tokens", 0)
                    self.completion_tokens = d.get("completion_tokens", 0)
                    self.total_tokens = d.get("total_tokens", 0)
                    self.total_requests = d.get("total_requests", 0)
                    self.ai_images_count = d.get("ai_images", 0)
                    self.ai_videos_count = d.get("ai_videos", 0)
                    self.documents_count = d.get("documents", 0)
                    self.rate_limit_remaining_tokens = d.get("rate_limit_remaining_tokens")
                    self.rate_limit_limit_tokens = d.get("rate_limit_limit_tokens")
                    self.rate_limit_remaining_requests = d.get("rate_limit_remaining_requests")
                    self.rate_limit_limit_requests = d.get("rate_limit_limit_requests")
        except Exception:
            pass

    def _save_persisted(self):
        try:
            p = self._get_storage_path()
            with open(p, "w", encoding="utf-8") as f:
                json.dump(self.get_stats(), f, indent=2)
        except Exception:
            pass

    def record_chat_tokens(self, prompt: int, completion: int, total: int):
        self.prompt_tokens += max(0, prompt)
        self.completion_tokens += max(0, completion)
        self.total_tokens += max(0, total)
        self.total_requests += 1
        self._save_persisted()

    def record_headers(self, headers: dict):
        if not headers:
            return
        updated = False
        for k, v in headers.items():
            kl = k.lower()
            if kl == "x-ratelimit-remaining-tokens":
                try:
                    self.rate_limit_remaining_tokens = int(v)
                    updated = True
                except Exception: pass
            elif kl == "x-ratelimit-limit-tokens":
                try:
                    self.rate_limit_limit_tokens = int(v)
                    updated = True
                except Exception: pass
            elif kl == "x-ratelimit-remaining-requests":
                try:
                    self.rate_limit_remaining_requests = int(v)
                    updated = True
                except Exception: pass
            elif kl == "x-ratelimit-limit-requests":
                try:
                    self.rate_limit_limit_requests = int(v)
                    updated = True
                except Exception: pass
            elif kl == "x-ratelimit-reset-tokens":
                self.rate_limit_reset_tokens = v
            elif kl == "x-ratelimit-reset-requests":
                self.rate_limit_reset_requests = v
        if updated:
            self._save_persisted()

    def record_image(self):
        self.ai_images_count += 1
        self._save_persisted()

    def record_video(self):
        self.ai_videos_count += 1
        self._save_persisted()

    def record_document(self):
        self.documents_count += 1
        self._save_persisted()

    def get_stats(self) -> dict:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "total_requests": self.total_requests,
            "ai_images": self.ai_images_count,
            "ai_videos": self.ai_videos_count,
            "documents": self.documents_count,
            "rate_limit_remaining_tokens": self.rate_limit_remaining_tokens,
            "rate_limit_limit_tokens": self.rate_limit_limit_tokens,
            "rate_limit_remaining_requests": self.rate_limit_remaining_requests,
            "rate_limit_limit_requests": self.rate_limit_limit_requests,
            "rate_limit_reset_tokens": self.rate_limit_reset_tokens,
            "rate_limit_reset_requests": self.rate_limit_reset_requests,
        }

# Global singleton usage tracker
usage_tracker = UsageTracker()
usage_tracker._load_persisted()

class GroqClient:
    """Client for Groq Cloud ultra-fast inference with dynamic model detection."""

    def __init__(self, api_key: str = "", model: str = DEFAULT_GROQ_MODEL):
        self.api_key = api_key.strip()
        self.model = model or DEFAULT_GROQ_MODEL
        self.usage_tracker = usage_tracker

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
            "stream": True,
            "stream_options": {"include_usage": True}
        }

        full_content = ""
        prompt_tokens_used = 0
        completion_tokens_used = 0
        total_tokens_used = 0

        try:
            response = requests.post(GROQ_ENDPOINT, headers=headers, json=payload, stream=True, timeout=60)
            if response.headers:
                self.usage_tracker.record_headers(dict(response.headers))

            if response.status_code == 404 and self.model != "qwen/qwen3.8-27b":
                # Automatically fallback to available working model
                self.model = "qwen/qwen3.8-27b"
                payload["model"] = self.model
                response = requests.post(GROQ_ENDPOINT, headers=headers, json=payload, stream=True, timeout=60)
                if response.headers:
                    self.usage_tracker.record_headers(dict(response.headers))

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
                        if "usage" in chunk and chunk["usage"]:
                            u = chunk["usage"]
                            prompt_tokens_used = u.get("prompt_tokens", 0)
                            completion_tokens_used = u.get("completion_tokens", 0)
                            total_tokens_used = u.get("total_tokens", 0)
                    except Exception:
                        continue

            if total_tokens_used == 0 and full_content:
                # Estimate tokens if not provided in stream
                completion_tokens_used = max(1, len(full_content) // 4)
                prompt_tokens_used = sum(max(1, len(m.get("content", "")) // 4) for m in messages if isinstance(m.get("content"), str))
                total_tokens_used = prompt_tokens_used + completion_tokens_used

            self.usage_tracker.record_chat_tokens(prompt_tokens_used, completion_tokens_used, total_tokens_used)
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
            if response.headers:
                self.usage_tracker.record_headers(dict(response.headers))
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
            if full_content:
                comp_est = max(1, len(full_content) // 4)
                prompt_est = 200
                self.usage_tracker.record_chat_tokens(prompt_est, comp_est, prompt_est + comp_est)
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

    def generate_document_structure(self, topic: str, doc_type: str = "pptx", max_tokens: int = 4096) -> dict | None:
        """
        Uses Groq LLM in JSON mode to generate rich, topic-specific document and slide outlines.
        Produces 10-14 slides with comprehensive domain knowledge and structured document sections.
        """
        if not self.is_configured():
            return None

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        system_instruction = (
            "You are JARVIS's executive presentation and technical documentation intelligence. "
            "Generate an exhaustive, highly intellectual, domain-accurate document structure in JSON format. "
            "Never provide generic placeholders or empty filler. Analyze the topic with actual facts, figures, "
            "real architecture, formulas, frameworks, metrics, and case studies."
        )

        user_prompt = f"""
Analyze the given topic and create a deep, comprehensive {doc_type.upper()} presentation and document outline in JSON.
TOPIC: "{topic}"

REQUIREMENTS:
1. Provide a specific, compelling "title" and "subtitle".
2. Create 10 to 14 "slides" covering:
   - Slide 1: {{"type": "title", "title": "...", "subtitle": "...", "badge": "EXECUTIVE BRIEFING"}}
   - Slide 2: {{"type": "agenda", "title": "Executive Overview & Roadmap", "subtitle": "Strategic trajectory and core domains", "cards": [{{"tag": "PART 01", "heading": "...", "desc": "..."}}, {{"tag": "PART 02", "heading": "...", "desc": "..."}}, {{"tag": "PART 03", "heading": "...", "desc": "..."}}, {{"tag": "PART 04", "heading": "...", "desc": "..."}}]}}
   - Slides 3-5: {{"type": "cards", "title": "...", "subtitle": "...", "cards": [{{"tag": "...", "heading": "...", "desc": "..."}}, ...]}} (3 to 4 cards each explaining core principles, systems, components, or methodologies)
   - Slides 6-8: {{"type": "split", "title": "...", "subtitle": "...", "left": {{"heading": "...", "text": "..."}}, "bullets": [["Lead 1", "Detailed description with facts"], ["Lead 2", "Detailed description"], ["Lead 3", "Detailed description"], ["Lead 4", "Detailed description"]]}}
   - Slide 9: {{"type": "metrics", "title": "...", "subtitle": "...", "metrics": [{{"value": "...", "label": "...", "caption": "..."}}, {{"value": "...", "label": "...", "caption": "..."}}, {{"value": "...", "label": "...", "caption": "..."}}]}} (real statistics, speedups, benchmarks, or growth figures)
   - Slides 10-11: Deep-dive architectures, real-world case studies, or technical workflows (using "cards" or "split")
   - Slide 12: {{"type": "conclusion", "title": "Strategic Roadmap & Conclusion", "subtitle": "Key takeaways and forward horizons", "bullets": [["Milestone 1", "Actionable insight"], ["Milestone 2", "Actionable insight"], ["Milestone 3", "Actionable insight"]]}}

3. Create 5 to 7 "document_sections" for Word/PDF reports:
   - Section 1: {{"heading": "1. Executive Summary", "type": "callout", "text": "In-depth summary with strategic context."}}
   - Section 2: {{"heading": "2. Foundational Architecture & Principles", "type": "paragraphs", "paragraphs": ["Detailed paragraph 1...", "Detailed paragraph 2..."]}}
   - Section 3: {{"heading": "3. Comparative Analysis & Key Dimensions", "type": "table", "headers": ["Dimension", "Traditional Approach", "Modern / Target State", "Impact / Advantage"], "rows": [["...", "...", "...", "..."], ["...", "...", "...", "..."], ["...", "...", "...", "..."], ["...", "...", "...", "..."]]}}
   - Section 4: {{"heading": "4. Implementation Methodology & Workflows", "type": "bullets", "bullets": [["Step 1", "Detailed execution methodology..."], ["Step 2", "..."], ["Step 3", "..."]]}}
   - Section 5: {{"heading": "5. Empirical Impact & Risk Mitigation", "type": "paragraphs", "paragraphs": ["Analysis of metrics, risks, and mitigations..."]}}
   - Section 6: {{"heading": "6. Conclusion & Strategic Directives", "type": "callout", "text": "Final synthesis and forward recommendations."}}

Return ONLY a valid JSON object matching this schema. Do not include markdown formatting or extra text.
"""

        models_to_try = ["llama-3.3-70b-versatile", self.model, "qwen/qwen3.8-27b"]
        seen_models = set()
        for m in models_to_try:
            if not m or m in seen_models:
                continue
            seen_models.add(m)
            payload = {
                "model": m,
                "messages": [
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": user_prompt}
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.5,
                "max_tokens": max_tokens
            }
            try:
                resp = requests.post(GROQ_ENDPOINT, headers=headers, json=payload, timeout=45)
                if resp.headers:
                    self.usage_tracker.record_headers(dict(resp.headers))
                if resp.status_code == 200:
                    data = resp.json()
                    usage = data.get("usage", {})
                    if usage:
                        self.usage_tracker.record_chat_tokens(
                            usage.get("prompt_tokens", 0),
                            usage.get("completion_tokens", 0),
                            usage.get("total_tokens", 0)
                        )
                    raw_content = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                    if raw_content:
                        parsed = json.loads(raw_content)
                        if isinstance(parsed, dict) and ("slides" in parsed or "document_sections" in parsed):
                            return parsed
                elif resp.status_code in [400, 404]:
                    continue
                else:
                    pass
            except Exception as e:
                pass
    def classify_intent(self, user_message: str) -> dict | None:
        """
        Uses an ultra-fast LLM to classify user message intent into structured JSON.
        Acts as the intelligent brain dispatcher across all JARVIS capabilities.
        """
        if not self.is_configured() or not user_message or not user_message.strip():
            return None

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        system_instruction = (
            "You are JARVIS's central cognitive routing dispatcher. "
            "Analyze the user's input and determine if they want to execute an action. "
            "Categories:\n"
            "- 'image_generate': user wants an AI-generated image (prompt, optional style)\n"
            "- 'image_alter': user wants to alter an existing image with a style (cyberpunk, anime, sketch, vintage, etc.)\n"
            "- 'video_generate': user wants an AI video produced from text (prompt)\n"
            "- 'document_create': user wants a presentation (pptx), document (docx), or report (pdf) created (topic, doc_type, optional theme)\n"
            "- 'chat': general question, conversation, explanation, or coding help\n\n"
            "Return valid JSON matching:\n"
            "{\n"
            "  \"intent\": \"image_generate\" | \"image_alter\" | \"video_generate\" | \"document_create\" | \"chat\",\n"
            "  \"params\": {\n"
            "     \"prompt\": \"...\",\n"
            "     \"style\": \"...\",\n"
            "     \"topic\": \"...\",\n"
            "     \"doc_type\": \"pptx\" | \"docx\" | \"pdf\",\n"
            "     \"theme\": \"...\"\n"
            "  }\n"
            "}"
        )

        payload = {
            "model": "llama-3.1-8b-instant",
            "messages": [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": user_message}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.1,
            "max_tokens": 150
        }

        try:
            resp = requests.post(GROQ_ENDPOINT, headers=headers, json=payload, timeout=6)
            if resp.headers:
                self.usage_tracker.record_headers(dict(resp.headers))
            if resp.status_code == 200:
                data = resp.json()
                usage = data.get("usage", {})
                if usage:
                    self.usage_tracker.record_chat_tokens(
                        usage.get("prompt_tokens", 0),
                        usage.get("completion_tokens", 0),
                        usage.get("total_tokens", 0)
                    )
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                if content:
                    parsed = json.loads(content)
                    if isinstance(parsed, dict) and "intent" in parsed:
                        return parsed
        except Exception:
            pass
        return None

