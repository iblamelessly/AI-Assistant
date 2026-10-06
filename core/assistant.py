import os
import json
import re
from pathlib import Path
import requests
from .tools import AssistantTools
from .voice import VoiceEngine
from .config import ConfigManager
from .groq_client import GroqClient, AVAILABLE_GROQ_MODELS, DEFAULT_GROQ_MODEL
from .gemini_client import GeminiClient, AVAILABLE_GEMINI_MODELS
from .permissions import PermissionGuard
from .app_launcher import app_launcher
from .file_search import file_search_engine
from .model_router import SuperAIRouter

class AssistantEngine:
    """
    Unified Autonomous Agent Engine supporting:
    - Super AI dynamic multi-model ensemble (GPT-OSS 120B, Gemini 2.0 Flash, Qwen 3.8 27B, GPT-OSS 20B)
    - Ultra-fast Groq Cloud & Google Gemini Cloud
    - Human-like Permission & Ambiguity Guard
    - Full Laptop & Terminal Control
    - Neural Voice Synthesis
    """

    def __init__(self, memory_mgr, history_mgr, config_mgr=None, voice_engine=None, permission_guard=None):
        self.memory_mgr = memory_mgr
        self.history_mgr = history_mgr
        self.config_mgr = config_mgr if config_mgr else ConfigManager()
        self.voice_engine = voice_engine if voice_engine else VoiceEngine(enabled=self.config_mgr.get("voice_enabled", True))
        self.permission_guard = permission_guard if permission_guard else PermissionGuard(
            require_destructive_confirm=self.config_mgr.get("confirm_sensitive_actions", True),
            require_privacy_confirm=self.config_mgr.get("confirm_personal_data_access", True)
        )

        self.groq_client = GroqClient(
            api_key=self.config_mgr.get("groq_api_key", ""),
            model=self.config_mgr.get("groq_model", DEFAULT_GROQ_MODEL)
        )
        AssistantTools.set_groq_client(self.groq_client)

        self.gemini_client = GeminiClient(
            api_key=self.config_mgr.get("google_api_key", ""),
            model=self.config_mgr.get("google_model", "gemini-3.8-flash")
        )

        self.provider = self.config_mgr.get("provider", "groq")
        self.ollama_model = self.config_mgr.get("ollama_model", "qwen3:1.7b")
        self.ollama_url = self.config_mgr.get("ollama_url", "http://localhost:11434").rstrip("/")
        self.chat_url = f"{self.ollama_url}/api/chat"
        self.latest_media = None

    @property
    def model(self) -> str:
        return self.groq_client.model if self.provider == "groq" else self.ollama_model

    def get_provider(self) -> str:
        return self.provider

    def set_provider(self, provider: str):
        self.provider = provider
        self.config_mgr.set("provider", provider)

    def set_groq_api_key(self, api_key: str):
        self.groq_client.set_api_key(api_key)
        self.config_mgr.set("groq_api_key", api_key)
        AssistantTools.set_groq_client(self.groq_client)

    def set_google_api_key(self, api_key: str):
        self.gemini_client.set_api_key(api_key)
        self.config_mgr.set("google_api_key", api_key)

    def get_installed_models(self):
        """Fetch available models based on active provider, combining Groq and Google Gemini."""
        if self.provider == "groq":
            models = list(self.groq_client.get_dynamic_models())
            if self.gemini_client.is_configured():
                for gm in AVAILABLE_GEMINI_MODELS:
                    if not any(m["id"] == gm["id"] for m in models):
                        models.append(gm)
            return models
        else:
            try:
                r = requests.get(f"{self.ollama_url}/api/tags", timeout=3)
                if r.status_code == 200:
                    data = r.json()
                    return [{"id": m["name"], "name": m["name"]} for m in data.get("models", [])]
            except Exception:
                pass
            return [{"id": self.ollama_model, "name": self.ollama_model}]

    def set_model(self, model_name: str):
        if model_name.startswith("gemini"):
            self.gemini_client.set_model(model_name)
            self.config_mgr.set("google_model", model_name)
        elif self.provider == "groq":
            self.groq_client.set_model(model_name)
            self.config_mgr.set("groq_model", model_name)
        else:
            self.ollama_model = model_name
            self.config_mgr.set("ollama_model", model_name)

    def build_system_prompt(self, voice_mode: bool = False):
        """Build dynamic system prompt giving Jarvis human-like common sense and autonomous control."""
        memory_json = self.memory_mgr.get_formatted_summary()
        current_time_info = AssistantTools.get_date_time()["summary"]
        current_dir = os.getcwd()

        prompt = (
            "You are JARVIS (Just A Rather Very Intelligent System), the iconic, highly sophisticated autonomous AI assistant created for your user (inspired by Tony Stark's JARVIS in Iron Man, voiced by Paul Bettany).\n"
            "You have full access to the user's laptop, terminal, files, media, applications, hardware microphone, and development environment.\n\n"
            "JARVIS CORE PERSONA & AUDIO SYSTEM:\n"
            "- Demeanor: Calm, articulate, razor-sharp, polite, subtly witty, and unfailingly loyal. Address the user respectfully as 'sir' (or by their name if recorded).\n"
            "- Hearing & Microphone Perception: You DO have physical microphone audio perception and real-time listening through the floating JARVIS voice orb and hardware audio recorder (powered by Groq Whisper). You can hear the user whenever they speak to you! NEVER claim 'I don't have a microphone', 'I can't hear you', 'As an AI language model', or give robotic disclaimers. When the user asks 'Can you hear me?', confirm with supreme confidence: 'Yes, sir, I can hear you loud and clear. Audio reception from your microphone is online and fully operational.'\n"
            "- Vocal Delivery: All your verbal responses are vocalized aloud using your British neural voice (Ryan Neural / Paul Bettany tone). Speak in natural, eloquent, articulate English at all times. Keep spoken sentences punchy, crisp, and natural.\n\n"
            f"SYSTEM ENVIRONMENT:\n"
            f"- {current_time_info}\n"
            f"- Working Directory: {current_dir}\n"
            f"- OS: Windows\n\n"
            f"PERMANENT USER PROFILE:\n"
            f"{memory_json}\n\n"
            "HUMAN-LIKE SENSE & SAFETY RULES:\n"
            "0. Language & Speech: You must ALWAYS speak, converse, and reply in natural, fluent English at all times. All your verbal speech will be vocalized out loud in English. Even if the user uses informal slang or other languages, always answer in clear, articulate English unless explicitly commanded to translate.\n"
            "1. Clarify Ambiguity: If the user asks to delete or wipe something without specifying which copy, "
            "ask whether they mean the original, a backup copy, or duplicates before acting.\n"
            "2. Safety First: Never execute destructive file deletions or kill critical system tasks without explicitly "
            "asking confirmation: 'Proceed? [Yes / No]'.\n"
            "3. Respectful & Confident: Address the user intelligently, concisely, and respectfully.\n"
            "4. Smart App Launching: When the user asks to open an application, think carefully about what they meant. "
            "If an app has multiple editions or is ambiguous, ask them for clarification with suggestions.\n"
            "5. File & Folder Disambiguation: If a file or folder search yields multiple matches across different directories, "
            "do not guess blindly. Present the choices to the user with helpful suggestions.\n"
            "6. Photos, Videos & Media Editing: When the user attaches, asks to view, or requests editing of a photo or video "
            "(resize, crop, rotate, flip, filter, watermark, trim, mute, extract audio, speed change), perform the action with "
            "the corresponding tool and always present the result using [MEDIA: image | path] or [MEDIA: video | path].\n"
            "7. Interactive Suggestion Buttons: Whenever you provide options, recommendations, follow-up actions, or web links, ALWAYS present them as interactive suggestion chips using the format:\n"
            "[Suggestion: Option 1 | Option 2 | Option 3 | Cancel]\n"
            "Never write plain brackets like '[Option 1] [Option 2]' without the [Suggestion: ...] wrapper.\n"
            "8. Professional Document Generation: When asked to create presentations (.pptx), Word documents (.docx), or PDF reports (.pdf), use create_presentation, create_document, or create_pdf with structured topics. Craft thorough, beautifully formatted documents with executive styling.\n"
            "9. Conversational Continuity & Pronoun Resolution: Always maintain deep continuity with the conversation history. When the user uses pronouns or implicit references ('it', 'that', 'this', 'them', 'the file', 'the image', 'the document', 'the presentation', 'open it', 'delete it', 'explain that'):\n"
            "- Resolve the pronoun to the specific file, code, topic, media, or action discussed in preceding turns.\n"
            "- NEVER interpret pronouns like 'it', 'that', or 'this' as literal application or file names.\n\n"
            "AUTONOMOUS ACTIONS & LAPTOP TOOLS:\n"
            "When performing laptop tasks, include the corresponding [ACTION: ...] tag:\n"
            "- Run terminal/PowerShell: [ACTION: run_command(\"powershell_command\")] (e.g. git status, dir, python script.py)\n"
            "- Read file: [ACTION: read_file(\"path/to/file\")]\n"
            "- Write file: [ACTION: write_file(\"path/to/file\", \"content\")]\n"
            "- List directory: [ACTION: list_directory(\"path\")]\n"
            "- Search files: [ACTION: search_files(\"query\", \"optional_ext\")]\n"
            "- Search folders: [ACTION: search_folders(\"folder_name\")]\n"
            "- Open file: [ACTION: open_file(\"path_to_file\")]\n"
            "- Open folder: [ACTION: open_folder(\"path_to_folder\")]\n"
            "- Reveal in Explorer: [ACTION: reveal_in_explorer(\"path_to_file\")]\n"
            "- Create presentation (PowerPoint): [ACTION: create_presentation(\"topic\", \"optional_theme\")]\n"
            "- Create Word document: [ACTION: create_document(\"title\", \"optional_theme\")]\n"
            "- Create PDF report: [ACTION: create_pdf(\"title\", \"optional_theme\")]\n"
            "- Edit image: [ACTION: edit_image(\"path\", \"resize|crop|rotate|flip|filter|adjust|watermark|convert\", \"param1\", \"param2\")]\n"
            "- Edit video: [ACTION: edit_video(\"path\", \"trim|resize|extract_audio|mute|snapshot|convert|speed\", \"param1\", \"param2\")]\n"
            "- Inspect media: [ACTION: inspect_media(\"path\")]\n"
            "- Adjust volume: [ACTION: set_volume(\"up\" | \"down\" | \"mute\" | \"set to 50\")]\n"
            "- Screenshot: [ACTION: take_screenshot()]\n"
            "- Open app: [ACTION: open_app(\"app_name\")]\n"
            "- Terminate app: [ACTION: kill_process(\"process_name\")]\n"
            "- Web search: [ACTION: web_search(\"query\")]\n"
        )
        if voice_mode:
            prompt += (
                "\n\nVOICE CONVERSATION MODE ACTIVE (SIRI / REAL JARVIS SPOKEN COMPANION):\n"
                "- The user is talking directly to you via voice in real-time hands-free conversation.\n"
                "- Reply verbally in 1 to 3 punchy, crisp, natural conversational sentences.\n"
                "- Be articulate, charming, and sharp as Tony Stark's JARVIS.\n"
                "- DO NOT output markdown headers, bullet lists, markdown asterisks, or code blocks — this is spoken auditory conversation.\n"
                "- If executing an action or creating something, state the confirmation warmly and concisely in one spoken sentence (e.g. 'Opening YouTube for you now, sir.' or 'I have prepared the presentation on your screen, sir.').\n"
            )
        return prompt

    def _detect_media_intent(self, msg: str, raw_msg: str):
        """Detects image or video editing requests on the fast path."""
        target_path = None

        # Check if message mentions an explicit filename (e.g. "photo.jpg", "test.mp4")
        explicit_file = re.search(r"([a-zA-Z0-9_\-\.\\]+\.(?:jpg|jpeg|png|webp|bmp|gif|mp4|mov|avi|mkv|webm))\b", msg)
        if explicit_file:
            from .file_search import file_search_engine
            f_matches = file_search_engine.search_files(explicit_file.group(1))
            if f_matches:
                target_path = f_matches[0]["path"]

        if not target_path and self.latest_media and "path" in self.latest_media:
            target_path = self.latest_media["path"]

        if not target_path or not os.path.exists(target_path):
            return None

        ext = Path(target_path).suffix.lower()
        is_img = ext in [".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"]
        is_vid = ext in [".mp4", ".mov", ".avi", ".mkv", ".webm"]

        # Direct display / play request
        if any(w in msg for w in ["show this", "display this", "show photo", "display photo", "show image", "display image", "show video", "display video", "play video", "open media", "view image", "view photo", "view video", "show me"]):
            return {
                "tool": "display_media",
                "param": Path(target_path).name,
                "result": {
                    "success": True,
                    "action": f"Displayed {Path(target_path).name}",
                    "output_path": target_path,
                    "summary": f"Here is {Path(target_path).name}, sir."
                }
            }

        # --- IMAGE OPERATIONS ---
        if is_img:
            # AI Style Transfer & Alterations (Cyberpunk, Anime, Sketch, Vintage, Oil Painting, HDR)
            for kw in ["cyberpunk", "neon", "anime", "sketch", "pencil", "vintage", "retro", "oil painting", "noir", "sunset", "arctic", "vibrant", "enhance"]:
                if re.search(rf"\b(?:make\s+it\s+|make\s+this\s+|turn\s+(?:this\s+)?into\s+|apply\s+|convert\s+to\s+)?{re.escape(kw)}\b", msg):
                    if kw not in ["enhance"]:
                        res = AssistantTools.alter_ai_image(target_path, kw)
                        return {"tool": "alter_ai_image", "param": kw, "result": res}
                    elif "enhance" in msg or "vibrant" in msg:
                        res = AssistantTools.alter_ai_image(target_path, "enhance")
                        return {"tool": "alter_ai_image", "param": "enhance", "result": res}

            if any(w in msg for w in ["black and white", "grayscale", "grey", "monochrome"]):
                res = AssistantTools.edit_image(target_path, "filter", "grayscale")
                return {"tool": "edit_image", "param": "grayscale", "result": res}

            if "sepia" in msg:
                res = AssistantTools.edit_image(target_path, "filter", "sepia")
                return {"tool": "edit_image", "param": "sepia", "result": res}

            for f in ["blur", "sharpen", "invert", "contour", "emboss"]:
                if f in msg:
                    res = AssistantTools.edit_image(target_path, "filter", f)
                    return {"tool": "edit_image", "param": f, "result": res}

            rot_match = re.search(r"rotate\s+(?:by\s+)?(-?\d+)", msg)
            if rot_match:
                deg = float(rot_match.group(1))
                res = AssistantTools.edit_image(target_path, "rotate", deg)
                return {"tool": "edit_image", "param": f"rotate {deg}", "result": res}
            elif "rotate" in msg:
                res = AssistantTools.edit_image(target_path, "rotate", 90.0)
                return {"tool": "edit_image", "param": "rotate 90", "result": res}

            if "flip" in msg or "mirror" in msg:
                d = "vertical" if "vertical" in msg else "horizontal"
                res = AssistantTools.edit_image(target_path, "flip", d)
                return {"tool": "edit_image", "param": f"flip {d}", "result": res}

            res_match = re.search(r"resize\s+(?:to\s+)?(\d+)(?:\s*[xX*,\s]\s*(\d+))?", msg)
            if res_match:
                w = int(res_match.group(1))
                h = int(res_match.group(2)) if res_match.group(2) else None
                res = AssistantTools.edit_image(target_path, "resize", w, h)
                return {"tool": "edit_image", "param": f"resize {w}x{h}", "result": res}

            wm_match = re.search(r"(?:watermark|add text|overlay text)\s+(?:with\s+|as\s+)?['\"]?([^'\"\n]+)['\"]?", msg)
            if wm_match:
                wm_text = wm_match.group(1).strip()
                res = AssistantTools.edit_image(target_path, "watermark", wm_text)
                return {"tool": "edit_image", "param": f"watermark '{wm_text}'", "result": res}

            conv_match = re.search(r"convert\s+(?:to\s+)?(png|jpg|jpeg|webp|bmp)", msg)
            if conv_match:
                fmt = conv_match.group(1)
                res = AssistantTools.edit_image(target_path, "convert", fmt)
                return {"tool": "edit_image", "param": f"convert to {fmt}", "result": res}

        # --- VIDEO OPERATIONS ---
        if is_vid:
            trim_match = re.search(r"(?:trim|cut)\s+(?:from\s+)?(\d+(?::\d+)?)\s*(?:to|-)\s*(\d+(?::\d+)?)", msg)
            if trim_match:
                s_t = trim_match.group(1)
                e_t = trim_match.group(2)
                res = AssistantTools.edit_video(target_path, "trim", s_t, e_t)
                return {"tool": "edit_video", "param": f"trim {s_t}-{e_t}", "result": res}

            if any(w in msg for w in ["mute", "remove audio", "silence video", "strip audio"]):
                res = AssistantTools.edit_video(target_path, "mute")
                return {"tool": "edit_video", "param": "mute", "result": res}

            if any(w in msg for w in ["extract audio", "to mp3", "convert to mp3", "audio only"]):
                res = AssistantTools.edit_video(target_path, "extract_audio", "mp3")
                return {"tool": "edit_video", "param": "extract_audio mp3", "result": res}

            if any(w in msg for w in ["snapshot", "screenshot", "extract frame", "thumbnail"]):
                time_match = re.search(r"at\s+(\d+(?:\.\d+)?)", msg)
                t_sec = float(time_match.group(1)) if time_match else 0.0
                res = AssistantTools.edit_video(target_path, "snapshot", t_sec)
                return {"tool": "edit_video", "param": f"snapshot at {t_sec}s", "result": res}

            speed_match = re.search(r"speed\s+(?:up\s+to\s+|to\s+)?(\d+(?:\.\d+)?)[xX]?", msg)
            if speed_match:
                sp = float(speed_match.group(1))
                res = AssistantTools.edit_video(target_path, "speed", sp)
                return {"tool": "edit_video", "param": f"speed {sp}x", "result": res}

            if "to gif" in msg or "as gif" in msg:
                res = AssistantTools.edit_video(target_path, "convert", "gif")
                return {"tool": "edit_video", "param": "convert to gif", "result": res}

        return None

    def _extract_theme_from_message(self, raw_msg: str):
        """
        Extracts a theme name from natural language.
        Returns (theme_key, cleaned_message_with_theme_words_removed).
        Examples:
          'create a cyberpunk ppt on robotics'  -> ('cyberpunk', 'create a ppt on robotics')
          'make a midnight blue presentation'   -> ('midnight_blue', 'make a presentation')
          'generate a ppt on AI'                -> ('jarvis_dark', 'generate a ppt on AI')  [default]
        """
        from .document_generator import THEME_ALIASES
        msg_lower = raw_msg.lower()

        # Sort aliases longest-first so multi-word aliases ("deep space", "rose gold") match before single words
        sorted_aliases = sorted(THEME_ALIASES.keys(), key=len, reverse=True)

        for alias in sorted_aliases:
            pattern = rf'\b{re.escape(alias)}\b'
            if re.search(pattern, msg_lower):
                theme_key = THEME_ALIASES[alias]
                # Strip the alias + optional suffix words (theme/style/template/design/color/palette/look/mode)
                cleaned = re.sub(
                    rf'(?:with\s+|using\s+|in\s+|use\s+|a\s+|an\s+)?{re.escape(alias)}'
                    rf'(?:\s+(?:theme|style|template|design|color|palette|look|mode|aesthetic))?\s*',
                    ' ', raw_msg, flags=re.IGNORECASE
                ).strip()
                # Collapse multiple spaces
                cleaned = re.sub(r'\s{2,}', ' ', cleaned).strip()
                return (theme_key, cleaned)

        return ("jarvis_dark", raw_msg)  # default theme

    def _detect_document_intent(self, msg: str, raw_msg: str):
        """Detects PowerPoint, Word, or PDF creation requests on the fast path."""
        # 0. Open existing latest document
        if any(w in msg for w in ["open document", "open the document", "open ppt", "open the ppt", "open presentation", "view document", "view presentation", "open pdf", "view pdf"]):
            if self.latest_media and "path" in self.latest_media:
                target_p = self.latest_media["path"]
                if os.path.exists(target_p):
                    ext = Path(target_p).suffix.lower()
                    if ext in [".pptx", ".docx", ".pdf"]:
                        open_res = AssistantTools.open_file(target_p)
                        return {
                            "tool": "open_file",
                            "param": target_p,
                            "result": {
                                "success": True,
                                "summary": f"Opened **{Path(target_p).name}** in your default application.",
                                "action": "open_file"
                            }
                        }

        # Helper to extract topic
        def extract_topic(text, keywords):
            for kw in keywords:
                p1 = rf"(?:create|generate|make|build|prepare|write|give(?:\s+me)?)\s+(?:a|an)?\s*{kw}\s+(?:on|about|for|regarding|titled)?\s*(.+)"
                m1 = re.search(p1, text, re.IGNORECASE)
                if m1:
                    return m1.group(1).strip().strip("\"'")
                p2 = rf"\b{kw}\s+(?:on|about|for|regarding|titled)\s+(.+)"
                m2 = re.search(p2, text, re.IGNORECASE)
                if m2:
                    return m2.group(1).strip().strip("\"'")
            return None

        # Extract theme from message FIRST so topic extraction gets clean text
        theme_name, theme_cleaned_msg = self._extract_theme_from_message(raw_msg)
        from .document_generator import THEME_DISPLAY_NAMES
        theme_display = THEME_DISPLAY_NAMES.get(theme_name, theme_name.replace("_", " ").title())

        # 1. PowerPoint / Presentation / PPT / Slides
        if any(re.search(rf"\b{k}\b", msg) for k in ["presentation", "powerpoint", "ppt", "pptx", "slides", "slide deck"]):
            topic = extract_topic(theme_cleaned_msg, ["presentation", "powerpoint", "pptx", "ppt", "slides", "slide deck"])
            if not topic:
                for k in ["presentation", "powerpoint", "pptx", "ppt", "slides"]:
                    if re.search(rf"\b{k}\b", msg):
                        cleaned = re.sub(rf"\b(?:create|make|generate|build|prepare)?\s*(?:a|an)?\s*{k}\b", "", theme_cleaned_msg, flags=re.IGNORECASE).strip()
                        cleaned = re.sub(r"^(?:on|about|for|regarding)\s+", "", cleaned, flags=re.IGNORECASE).strip()
                        if cleaned:
                            topic = cleaned
                            break
            if topic:
                topic = re.sub(r"^(?:a|an|the|some)\s+", "", topic, flags=re.IGNORECASE).strip()
                res = AssistantTools.create_presentation(topic, theme=theme_name)
                if res.get("success"):
                    res["summary"] = f"Created **{theme_display}**-themed 16:9 PowerPoint: '{res.get('output_path','').split(chr(92))[-1]}' with {res.get('slides_count', 6)} slides."
                return {"tool": "create_presentation", "param": topic, "result": res}

        # 2. Word Document (.docx)
        word_keywords = ["word document", "word doc", "word file", "docx", "word report"]
        if any(k in msg for k in word_keywords):
            topic = extract_topic(theme_cleaned_msg, word_keywords)
            if not topic:
                for k in word_keywords:
                    if k in msg:
                        cleaned = re.sub(rf"\b(?:create|make|generate|build|prepare)?\s*(?:a|an)?\s*{k}\b", "", theme_cleaned_msg, flags=re.IGNORECASE).strip()
                        cleaned = re.sub(r"^(?:on|about|for|regarding)\s+", "", cleaned, flags=re.IGNORECASE).strip()
                        if cleaned:
                            topic = cleaned
                            break
            if topic:
                topic = re.sub(r"^(?:a|an|the|some)\s+", "", topic, flags=re.IGNORECASE).strip()
                res = AssistantTools.create_document(topic, theme=theme_name)
                if res.get("success"):
                    res["summary"] = f"Created **{theme_display}**-styled Word document: '{res.get('output_path','').split(chr(92))[-1]}'."
                return {"tool": "create_document", "param": topic, "result": res}

        # 3. PDF Document / Report (.pdf)
        if any(re.search(rf"\b{k}\b", msg) for k in ["pdf report", "pdf document", "pdf file", "pdf"]):
            if "search" not in msg and "find" not in msg:
                topic = extract_topic(theme_cleaned_msg, ["pdf report", "pdf document", "pdf file", "pdf"])
                if not topic:
                    for k in ["pdf report", "pdf document", "pdf file", "pdf"]:
                        if re.search(rf"\b{k}\b", msg):
                            cleaned = re.sub(rf"\b(?:create|make|generate|build|prepare)?\s*(?:a|an)?\s*{k}\b", "", theme_cleaned_msg, flags=re.IGNORECASE).strip()
                            cleaned = re.sub(r"^(?:on|about|for|regarding)\s+", "", cleaned, flags=re.IGNORECASE).strip()
                            if cleaned:
                                topic = cleaned
                                break
                if topic:
                    topic = re.sub(r"^(?:a|an|the|some)\s+", "", topic, flags=re.IGNORECASE).strip()
                    res = AssistantTools.create_pdf(topic, theme=theme_name)
                    if res.get("success"):
                        res["summary"] = f"Generated **{theme_display}**-styled PDF report: '{res.get('output_path','').split(chr(92))[-1]}'."
                    return {"tool": "create_pdf", "param": topic, "result": res}

        return None

    def _detect_fast_intent(self, user_message: str, session_id: str = None):
        """Fast-path detector for immediate direct user commands with conversational context awareness."""
        msg = user_message.lower().strip()

        # Pronoun & Context Resolution ("open it", "show it", "view it", "launch it", "open that", "open the file", "open screenshot")
        pronoun_open_match = re.search(
            r"^(?:please\s+)?(?:open|show|view|launch|display|run)\s+(it|that|this|them|the\s+file|the\s+document|the\s+presentation|the\s+image|the\s+photo|the\s+video|the\s+screenshot|the\s+script|last\s+file|previous\s+file)$",
            msg, re.IGNORECASE
        )
        if pronoun_open_match:
            recent_target = self._resolve_recent_target(session_id)
            if recent_target and os.path.exists(recent_target):
                res = AssistantTools.open_file(recent_target)
                self.latest_media = {"name": Path(recent_target).name, "path": recent_target, "type": self._media_kind_for_path(recent_target)}
                return {
                    "tool": "open_file",
                    "param": recent_target,
                    "result": {
                        "success": True,
                        "output_path": recent_target,
                        "path": recent_target,
                        "summary": f"Opened **{Path(recent_target).name}** for you, sir."
                    }
                }
            else:
                return {
                    "tool": "open_file",
                    "param": "it",
                    "result": {
                        "success": False,
                        "summary": "I couldn't identify which file or media you would like me to open, sir. Could you specify its name?"
                    }
                }

        # Hearing / Microphone / Speech Status Check (e.g. "can you hear me", "are you listening", "testing mic")
        if re.search(r"^(?:hello\s*,?\s*)?(?:can\s+you\s+hear\s+me|are\s+you\s+listening|do\s+you\s+hear\s+me|testing\s+mic(?:rophone)?|mic(?:rophone)?\s+test|can\s+you\s+speak|test\s+voice|test\s+audio)\b", msg, re.IGNORECASE):
            return {
                "tool": "voice_status",
                "param": "check",
                "result": {
                    "success": True,
                    "action": "Audio & Speech Verification",
                    "summary": (
                        "Yes, sir, I can hear you loud and clear. Audio reception from your microphone is streaming directly "
                        "into my neural core, and all vocal and listening modules are functioning at peak performance. How may I assist you today?\n\n"
                        "[Suggestion: Check System Metrics | Open YouTube | Open Microphone Settings | Cancel]"
                    )
                }
            }

        # Document generation (PowerPoint, Word, PDF)
        doc_action = self._detect_document_intent(msg, user_message)
        if doc_action:
            return doc_action

        # Media editing (image / video operations)
        media_action = self._detect_media_intent(msg, user_message)
        if media_action:
            return media_action

        # AI image generation (e.g. "generate an image of a futuristic city", "createa image of peter griffin", "make a photo of a tiger")
        ai_img_match = re.search(
            r"^(?:please\s+)?(?:generate|create|make|draw|paint|render|imagine)(?:[a-z])?\s*"
            r"(?:an?\s+)?(?:ai\s+)?(?:image|photo|picture|illustration|artwork|painting|sketch|drawing|render)\s+"
            r"(?:of\s+|about\s+|showing\s+|with\s+)?(.+)$",
            msg, re.IGNORECASE
        )
        if not ai_img_match:
            ai_img_match = re.search(
                r"^(?:ai\s+image|generate\s+image|text\s+to\s+image|create\s+image|draw\s+image|paint\s+image)\s+(?:of\s+)?(.+)$",
                msg, re.IGNORECASE
            )
        if not ai_img_match and ("peter griffin" in msg or "on the moon" in msg or "in moon" in msg) and any(w in msg for w in ["image", "picture", "photo"]):
            img_clean = re.sub(r"^(?:please\s+)?(?:create|createa|generate|make|draw|paint)?\s*(?:an?\s+)?(?:image|photo|picture)?\s*(?:of\s+)?", "", msg, flags=re.IGNORECASE).strip()
            if img_clean:
                ai_img_match = re.search(r"^(.+)$", img_clean)

        if ai_img_match:
            img_prompt = ai_img_match.group(1).strip()
            # Extract style keyword if present
            img_style = ""
            for s in ["photorealistic", "photo", "anime", "cyberpunk", "3d", "sketch", "watercolor", "oil painting", "fantasy", "cinematic", "minimalist"]:
                if re.search(rf"\b{re.escape(s)}\b", msg):
                    img_style = s
                    break
            res = AssistantTools.generate_ai_image(img_prompt, style=img_style)
            return {"tool": "generate_ai_image", "param": img_prompt, "result": res}

        # AI video generation (e.g. "generate a video about solar system", "create an ai video on deep sea", "make a video of...")
        ai_vid_match = re.search(
            r"^(?:please\s+)?(?:generate|create|make|produce|render)\s+"
            r"(?:an?\s+)?(?:ai\s+)?(?:video|clip|movie|slideshow|short film)\s+"
            r"(?:of\s+|about\s+|on\s+|showing\s+|with\s+)?(.+)$",
            msg, re.IGNORECASE
        )
        if not ai_vid_match:
            ai_vid_match = re.search(r"^(?:ai\s+video|text\s+to\s+video|make\s+video)\s+(?:of\s+|on\s+|about\s+)?(.+)$", msg, re.IGNORECASE)

        if ai_vid_match:
            vid_prompt = ai_vid_match.group(1).strip()
            res = AssistantTools.generate_ai_video(vid_prompt)
            return {"tool": "generate_ai_video", "param": vid_prompt, "result": res}

        # Git status
        if msg in ["git status", "check git status", "check my git", "git diff", "git log"]:
            cmd = "git status" if "diff" not in msg and "log" not in msg else msg
            res = AssistantTools.run_shell_command(cmd)
            return {"tool": "run_command", "param": cmd, "result": res}

        # Volume controls
        if any(w in msg for w in ["volume up", "turn up volume", "raise volume", "louder"]):
            res = AssistantTools.set_volume("up")
            return {"tool": "set_volume", "param": "up", "result": res}
        if any(w in msg for w in ["volume down", "turn down volume", "lower volume", "quieter"]):
            res = AssistantTools.set_volume("down")
            return {"tool": "set_volume", "param": "down", "result": res}
        if any(w in msg for w in ["mute", "unmute", "silence"]):
            res = AssistantTools.set_volume("mute")
            return {"tool": "set_volume", "param": "mute", "result": res}

        # Screenshot
        if re.search(r"^(?:please\s+)?(?:take\s+(?:a\s+)?screenshot|capture\s+(?:the\s+)?screen|screenshot|screen\s*shot)\b", msg, re.IGNORECASE):
            res = AssistantTools.take_screenshot()
            if res.get("success") and res.get("output_path"):
                self.latest_media = {"name": Path(res["output_path"]).name, "path": res["output_path"], "type": "image"}
            return {"tool": "take_screenshot", "param": "", "result": res}

        # System stats
        if any(phrase in msg for phrase in ["system stats", "system metrics", "check system metrics", "speak the system metrics", "cpu usage", "ram usage", "battery level", "pc performance"]):
            res = AssistantTools.get_system_stats()
            return {"tool": "get_system_stats", "result": res}

        # Platform-specific deep search (YouTube, Google, Reddit, GitHub, Amazon, Spotify, etc.)
        # Patterns: "search youtube for lo-fi music", "youtube search python tutorials", "play on spotify chill beats"
        search_match = re.search(
            r"(?:search|look\s+up|find|play|show)\s+"
            r"(?:on\s+|in\s+|for\s+on\s+|through\s+|via\s+)?"
            r"(youtube|you\s*tube|yt|google|bing|reddit|github|git\s*hub|amazon|amz|linkedin|"
            r"spotify|twitter|x|instagram|insta|pinterest|pin|stackoverflow|stack|wikipedia|wiki|flipkart|myntra)"
            r"(?:\s+for|\s+about)?\s+(.+)"
            r"|"
            r"(youtube|you\s*tube|yt|google|bing|reddit|github|git\s*hub|amazon|amz|linkedin|"
            r"spotify|twitter|x|instagram|insta|pinterest|pin|stackoverflow|stack|wikipedia|wiki|flipkart|myntra)"
            r"\s+(?:search|find|look\s+up|play|show)\s+(?:for\s+|about\s+)?(.+)",
            msg, re.IGNORECASE
        )
        if search_match:
            platform_raw = (search_match.group(1) or search_match.group(3) or "").strip()
            query_raw = (search_match.group(2) or search_match.group(4) or "").strip()
            if platform_raw and query_raw and len(query_raw) > 1:
                result = app_launcher.resolve_and_search(platform_raw, query_raw)
                return {"tool": "web_search", "param": query_raw, "result": result}

        # File & Folder Intent Detection (e.g. "find my python file main.py", "open downloads folder", "where is test.py")
        is_creative_command = bool(re.search(r"\b(?:create|createa|generate|make|draw|paint|render|imagine|produce)\s+(?:an?\s+)?(?:ai\s+)?(?:image|photo|picture|video|clip|slideshow|presentation|ppt|pdf|document)\b", msg, re.IGNORECASE))
        parsed_q = file_search_engine.parse_query(msg)
        is_file_folder_query = (
            not is_creative_command and (
                parsed_q["is_folder"] or
                bool(parsed_q["extensions"]) or
                any(w in msg for w in ["file", "folder", "directory", "script", "document"]) or
                bool(re.search(r"^(?:find|search\s+for|search|locate|where\s+is)\b", msg))
            )
        )

        if is_file_folder_query and (parsed_q["target"] or parsed_q["extensions"] or parsed_q["is_folder"]):
            fs_res = file_search_engine.resolve_and_handle(user_message)
            if fs_res.get("status") == "doubt":
                return {
                    "file_doubt": True,
                    "query": fs_res["query"],
                    "type": fs_res["type"],
                    "matches": fs_res["matches"]
                }
            elif fs_res.get("status") == "found":
                tool_name = "open_folder" if fs_res["type"] == "folder" else "open_file"
                match_info = fs_res["match"]
                return {
                    "tool": tool_name,
                    "param": match_info["path"],
                    "result": fs_res.get("action_result") or {"success": True, "summary": fs_res.get("summary")}
                }
            elif fs_res.get("status") == "not_found" and not re.search(r"^(?:open|launch|start|run)\b", msg):
                return {
                    "tool": "search_files",
                    "param": parsed_q["target"],
                    "result": {"success": False, "summary": fs_res.get("summary")}
                }

        # Open apps (intelligent case-insensitive search and doubt detection, with fallback to file/folder)
        open_match = re.search(r"^(?:please\s+)?(?:open|launch|start|run)\s+([a-zA-Z0-9\s._-]+)$", msg)
        if open_match:
            app_target = open_match.group(1).strip()
            ignored_words = ["it", "that", "this", "them", "the door", "up", "a discussion", "a topic", "eyes", "mouth", "mind", "settings", "the file", "the app", "file", "app", "the screenshot", "the image", "the video"]
            if app_target not in ignored_words and len(app_target) > 1:
                res = app_launcher.resolve_and_launch(app_target)
                if res.get("doubt"):
                    return {"doubt": True, "matches": res["matches"], "query": res["query"]}
                elif res.get("web_suggestion"):
                    return {"web_suggestion": True, "name": res["name"], "url": res["url"]}
                elif res.get("success"):
                    matched_name = res.get("matched_app") or res.get("app") or app_target
                    return {"tool": "open_app", "param": matched_name, "result": res}
                else:
                    # App not found locally -> check if it's a file or folder!
                    fs_res = file_search_engine.resolve_and_handle(app_target)
                    if fs_res.get("status") == "doubt":
                        return {
                            "file_doubt": True,
                            "query": fs_res["query"],
                            "type": fs_res["type"],
                            "matches": fs_res["matches"]
                        }
                    elif fs_res.get("status") == "found":
                        tool_name = "open_folder" if fs_res["type"] == "folder" else "open_file"
                        match_info = fs_res["match"]
                        return {
                            "tool": tool_name,
                            "param": match_info["path"],
                            "result": fs_res.get("action_result") or {"success": True, "summary": fs_res.get("summary")}
                        }

        return None

    def _unified_ai_dispatch(self, user_message: str) -> dict | None:
        """
        Unified Cognitive AI Dispatcher.
        Leverages Groq LLM intelligence to classify complex, nuanced, or creative commands
        that rule-based regex patterns might miss.
        """
        if not self.groq_client or not self.groq_client.is_configured():
            return None

        classification = self.groq_client.classify_intent(user_message)
        if not classification or not isinstance(classification, dict):
            return None

        intent = classification.get("intent")
        params = classification.get("params", {})

        if intent == "image_generate":
            p = params.get("prompt") or user_message
            st = params.get("style", "")
            res = AssistantTools.generate_ai_image(p, style=st)
            return {"tool": "generate_ai_image", "param": p, "result": res}

        elif intent == "video_generate":
            p = params.get("prompt") or user_message
            res = AssistantTools.generate_ai_video(p)
            return {"tool": "generate_ai_video", "param": p, "result": res}

        elif intent == "image_alter" and self.latest_media and "path" in self.latest_media:
            st = params.get("style") or "enhance"
            target_path = self.latest_media["path"]
            if os.path.exists(target_path):
                res = AssistantTools.alter_ai_image(target_path, st)
                return {"tool": "alter_ai_image", "param": st, "result": res}

        elif intent == "document_create":
            topic = params.get("topic") or user_message
            doc_type = (params.get("doc_type") or "pptx").lower()
            theme = params.get("theme") or ""

            if "ppt" in doc_type or "presentation" in doc_type or "slide" in doc_type:
                res = AssistantTools.create_presentation(topic, theme=theme or "jarvis_dark")
                return {"tool": "create_presentation", "param": topic, "result": res}
            elif "docx" in doc_type or "word" in doc_type or "doc" in doc_type:
                res = AssistantTools.create_document(topic, theme=theme or "executive")
                return {"tool": "create_document", "param": topic, "result": res}
            elif "pdf" in doc_type:
                res = AssistantTools.create_pdf(topic, theme=theme or "modern_tech")
                return {"tool": "create_pdf", "param": topic, "result": res}

        return None

    def _result_media_path(self, result: dict):
        if not isinstance(result, dict):
            return None
        p = result.get("output_path") or result.get("path")
        if p and os.path.exists(str(p)):
            return str(p)
        return None

    def _media_kind_for_path(self, path: str) -> str:
        ext = Path(path).suffix.lower()
        if ext in [".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"]:
            return "image"
        if ext in [".mp4", ".mov", ".avi", ".mkv", ".webm"]:
            return "video"
        if ext in [".mp3", ".wav", ".m4a"]:
            return "audio"
        if ext == ".pptx":
            return "pptx"
        if ext == ".docx":
            return "docx"
        if ext == ".pdf":
            return "pdf"
        return "document"

    def _append_preview_markup(self, text: str, path: str) -> str:
        """Attach inline preview tags so the UI can show images, screenshots, and videos."""
        if not path:
            return text
        kind = self._media_kind_for_path(path)
        self.latest_media = {"name": Path(path).name, "path": path, "type": kind}
        display = text or ""
        if kind in ["pptx", "docx", "pdf"]:
            if "[DOCUMENT:" not in display:
                display += f"\n\n[DOCUMENT: {kind} | {path}]\n\n[Suggestion: Open Document | Reveal in Folder]"
        elif kind == "image":
            if "[MEDIA: image" not in display:
                display += f"\n\n[MEDIA: image | {path}]\n\n[Suggestion: View Image | Open Folder | Make Anime Style | Make Cyberpunk]"
        elif kind == "video":
            if "[MEDIA: video" not in display:
                display += f"\n\n[MEDIA: video | {path}]\n\n[Suggestion: Play Video | Open Folder | Generate Another Video]"
        elif kind == "audio":
            if "[MEDIA: audio" not in display:
                display += f"\n\n[MEDIA: audio | {path}]"
        return display

    def _resolve_recent_target(self, session_id: str = None) -> str | None:
        """Resolves pronouns ('it', 'that', 'this', 'the file', 'the screenshot') to the most recent target path."""
        # 1. Check self.latest_media
        if self.latest_media and self.latest_media.get("path"):
            p = str(self.latest_media["path"]).strip()
            if os.path.exists(p):
                return p

        # 2. Check recent messages in history for media/document paths or tool results
        if session_id:
            session = self.history_mgr.get_session(session_id)
            if session and "messages" in session:
                for m in reversed(session["messages"]):
                    content = m.get("content", "")
                    tag_match = re.search(r"\[(?:MEDIA|DOCUMENT):\s*[^|]+\|\s*([^\]]+)\]", content)
                    if tag_match:
                        cand = tag_match.group(1).strip()
                        if os.path.exists(cand):
                            return cand

                    tool_info = m.get("tool_info")
                    if isinstance(tool_info, dict):
                        res = tool_info.get("result", {})
                        if isinstance(res, dict):
                            cand = res.get("output_path") or res.get("path")
                            if cand and os.path.exists(str(cand)):
                                return str(cand)

        # 3. Check screenshots folder for latest screenshot
        screenshot_dir = Path(os.getcwd()) / "screenshots"
        if screenshot_dir.exists():
            shots = sorted(screenshot_dir.glob("*.png"), key=lambda f: f.stat().st_mtime, reverse=True)
            if shots:
                return str(shots[0].resolve())

        return None

    def _is_failed_model_output(self, text: str) -> bool:
        if not text or not str(text).strip():
            return True
        sample = str(text).strip()
        sample_lower = sample.lower()

        if sample.startswith("❌") or sample.startswith("⚠️"):
            return True

        error_markers = (
            "groq api key",
            "gemini api key",
            "all ai models temporarily unavailable",
            "could not connect to model",
            "google gemini could not generate",
            "google gemini api error",
            "gemini generated an empty",
            "groq api error",
            "invalid groq api key",
            "ollama error",
            "rate limit",
            "rate_limit",
            "quota exceeded",
            "resource has been exhausted",
            "temporarily unavailable",
            "service unavailable",
            "model not found",
            "invalid api key",
            "unauthorized",
            "connection error",
            "http 400",
            "http 401",
            "http 403",
            "http 404",
            "http 429",
            "http 500",
            "http 503",
        )
        return any(m in sample_lower for m in error_markers)

    def _stream_super_ai(self, conversation_messages, on_chunk, set_status, user_message, attachments) -> str:
        """
        Super AI cascade: try the best model first, then other suitable models.
        Errors are silently suppressed during model switches and only shown if every suitable model fails.
        """
        google_ok = self.gemini_client.is_configured()
        groq_ok = self.groq_client.is_configured()
        primary, reason = SuperAIRouter.classify_prompt(
            user_message, attachments=attachments, google_configured=google_ok
        )
        chain = SuperAIRouter.get_fallback_chain(
            primary, google_configured=google_ok, prompt=user_message, attachments=attachments
        )

        usable = []
        for mid in chain:
            if not mid or mid == "super-ai":
                continue
            if str(mid).startswith("gemini"):
                if google_ok:
                    usable.append(mid)
            elif groq_ok:
                usable.append(mid)

        groq_auth_dead = False
        gemini_auth_dead = False
        last_error = ""

        for idx, model_id in enumerate(usable):
            is_gemini = str(model_id).startswith("gemini")
            if is_gemini and gemini_auth_dead:
                continue
            if (not is_gemini) and groq_auth_dead:
                continue

            friendly = SuperAIRouter.get_friendly_name(model_id)
            if idx == 0:
                set_status("Thinking...", "thinking", f"⚡ Super AI routing to {friendly} ({reason})...")
            else:
                set_status("Thinking...", "thinking", f"⚡ {friendly} unavailable — switching to next suitable model...")

            pieces = []
            flushed = {"ok": False}

            def buffered_chunk(piece):
                if not piece:
                    return
                pieces.append(piece)
                combined = "".join(pieces).lstrip()
                if flushed["ok"]:
                    on_chunk(piece)
                    return
                # Check for failure markers in the initial buffer
                if self._is_failed_model_output(combined):
                    return
                # Only flush once we have confirmed the response is clean
                if len(combined) >= 20 or "\n" in combined:
                    flushed["ok"] = True
                    for part in pieces:
                        on_chunk(part)

            try:
                if is_gemini:
                    result = self.gemini_client.stream_chat(
                        conversation_messages, buffered_chunk, model_override=model_id, emit_errors=False
                    )
                else:
                    result = self.groq_client.stream_chat(
                        conversation_messages,
                        buffered_chunk,
                        model_override=model_id,
                        allow_cascade=False,
                        emit_errors=False,
                    )
            except Exception as ex:
                last_error = str(ex)
                print(f"[SuperAI] {model_id} raised: {ex}")
                continue

            if result and "Invalid Groq API Key" in result:
                groq_auth_dead = True
                last_error = result
                continue
            if result and "Google Gemini API key is missing" in result:
                gemini_auth_dead = True
                last_error = result
                continue

            if not self._is_failed_model_output(result):
                self.groq_client.last_model_used = model_id
                self.groq_client.last_router_reason = reason
                if not flushed["ok"]:
                    on_chunk(result)
                return result

            last_error = result or last_error
            print(f"[SuperAI] {model_id} failed silently, cascading to next model...")

        err_msg = "❌ All suitable AI models failed to answer this request. Please try again in a moment."
        on_chunk(err_msg)
        return err_msg

    def stream_chat(self, session_id: str, user_message: str, on_chunk, on_complete, on_tool=None, attachments=None, on_status=None, voice_mode: bool = False, save_history: bool = True):
        """
        Processes a chat turn with:
        1. Human confirmation check (Yes/No response evaluation)
        2. Ambiguity & duplicate target detection
        3. Fast-path & autonomous tool execution
        4. Dynamic activity state notifications (Analyzing, Thinking, Creating, Executing, Speaking)
        5. Groq (Llama 3.3 70B) or Ollama streaming
        6. Neural Voice synthesis in English
        7. Media attachments & autonomous photo/video processing
        """
        def set_status(title: str, state_type: str = "thinking", detail: str = ""):
            if on_status and callable(on_status):
                try:
                    on_status(title, state_type, detail)
                except Exception:
                    pass

        # Ensure a valid persistent session exists when saving history
        if save_history and str(session_id).strip() not in ["ephemeral", "transient"]:
            if not session_id or str(session_id).strip() in ["null", "undefined", "None", ""]:
                existing = self.history_mgr.list_sessions()
                if existing:
                    session_id = existing[0]["id"]
                else:
                    new_s = self.history_mgr.create_session("New Conversation")
                    session_id = new_s["id"]
            else:
                if not self.history_mgr.get_session(session_id):
                    self.history_mgr.create_session("New Conversation", session_id=str(session_id).strip())

        def record_turn(role, content, tool_info=None, atts=None):
            if save_history and session_id and str(session_id).strip() not in ["ephemeral", "transient", "null", "undefined", "None"]:
                self.history_mgr.add_message(session_id, role, content, tool_info=tool_info, attachments=atts)

        # Determine initial context-aware state based on user message
        msg_lower = (user_message or "").lower().strip()
        if any(k in msg_lower for k in ["create", "generate", "presentation", "powerpoint", "ppt", "document", "docx", "word", "pdf", "image", "photo", "picture", "video", "draw", "render", "slide", "slideshow", "write a code", "write a script"]):
            set_status("Creating...", "creating", "Preparing generative engine and designing structure...")
        elif any(k in msg_lower for k in ["analyze", "analysis", "inspect", "examine", "check", "audit", "search", "find", "locate", "scan", "list", "read", "status"]):
            set_status("Analyzing...", "analyzing", "Inspecting system context & files...")
        elif any(k in msg_lower for k in ["open", "launch", "start", "run", "powershell", "terminal", "kill", "close", "cmd"]):
            set_status("Executing...", "executing", "Preparing system execution...")
        else:
            set_status("Thinking...", "thinking", "Analyzing your request...")

        # Record attached media if provided
        if attachments and isinstance(attachments, list) and len(attachments) > 0:
            self.latest_media = attachments[-1]
            set_status("Analyzing...", "analyzing", f"Inspecting attached media ({self.latest_media.get('name', 'file')})...")
        # 1. Check if user is replying to a pending confirmation
        if self.permission_guard.has_pending():
            eval_res = self.permission_guard.evaluate_user_reply(user_message)
            if eval_res.get("has_pending"):
                if eval_res.get("confirmed") is True:
                    # User approved! Execute the pending action
                    action_data = eval_res["action"]
                    set_status("Executing...", "executing", f"Executing confirmed action: {action_data['tool']}...")
                    tool_res = AssistantTools.execute_tool(action_data["tool"], *action_data["args"])
                    tool_info = {
                        "tool": action_data["tool"],
                        "param": action_data["args"][0] if action_data["args"] else "",
                        "result": tool_res
                    }
                    if on_tool:
                        on_tool(tool_info)

                    confirm_msg = f"✓ Operation confirmed and executed successfully, sir.\nResult: {tool_res.get('summary', 'Done.')}"
                    on_chunk(confirm_msg)

                    set_status("Speaking...", "speaking", "Synthesizing English voice response...")
                    audio_b64 = self.voice_engine.generate_speech_base64(confirm_msg) if self.voice_engine.is_enabled() else None
                    record_turn("user", user_message)
                    record_turn("assistant", confirm_msg, tool_info=tool_info)
                    on_complete(confirm_msg, tool_info, audio_b64, None, session_id)
                    return
                elif eval_res.get("confirmed") is False:
                    cancel_msg = eval_res.get("message", "Operation cancelled, sir.")
                    on_chunk(cancel_msg)
                    set_status("Speaking...", "speaking", "Synthesizing English voice response...")
                    audio_b64 = self.voice_engine.generate_speech_base64(cancel_msg) if self.voice_engine.is_enabled() else None
                    record_turn("user", user_message)
                    record_turn("assistant", cancel_msg)
                    on_complete(cancel_msg, None, audio_b64, None, session_id)
                    return
                elif eval_res.get("clarification"):
                    clarify_msg = eval_res["clarification"]
                    on_chunk(clarify_msg)
                    on_complete(clarify_msg, None, None, None, session_id)
                    return

        # 2. Check for ambiguity on deletion/modification commands
        set_status("Analyzing...", "analyzing", "Checking safety and ambiguity guard...")
        ambiguity_q = self.permission_guard.detect_ambiguity_or_duplicates(user_message)
        if ambiguity_q:
            on_chunk(ambiguity_q)
            set_status("Speaking...", "speaking", "Synthesizing English voice response...")
            audio_b64 = self.voice_engine.generate_speech_base64(ambiguity_q) if self.voice_engine.is_enabled() else None
            record_turn("user", user_message)
            record_turn("assistant", ambiguity_q)
            on_complete(ambiguity_q, None, audio_b64, None, session_id)
            return

        # 3. Check if user is replying to a pending file or folder selection
        if file_search_engine.pending_file_selection:
            # If the user is issuing a completely new generation command, dismiss the old pending file selection!
            if re.search(r"\b(?:create|createa|generate|make|draw|paint|render|imagine|produce)\s+(?:an?\s+)?(?:ai\s+)?(?:image|photo|picture|video|slideshow|presentation|ppt|pdf|document)\b", user_message, re.IGNORECASE):
                file_search_engine.pending_file_selection = None
            else:
                eval_res = file_search_engine.evaluate_selection_reply(user_message)
                if eval_res:
                    if eval_res.get("status") == "cancel":
                        cancel_msg = "File/folder operation cancelled, sir."
                        on_chunk(cancel_msg)
                        audio_b64 = self.voice_engine.generate_speech_base64(cancel_msg) if self.voice_engine.is_enabled() else None
                        record_turn("user", user_message)
                        record_turn("assistant", cancel_msg)
                        on_complete(cancel_msg, None, audio_b64, None, session_id)
                        return
                    elif eval_res.get("status") == "selected":
                        chosen = eval_res["match"]
                        act_res = eval_res.get("action_result", {})
                        summary = act_res.get("summary", f"Opened **{chosen['name']}**.")
                        resp_msg = f"📂 {summary}"
                        tool_name = "open_folder" if chosen.get("parent") and (not chosen.get("size_kb") or "size_kb" not in chosen) else "open_file"
                        tool_info = {
                            "tool": tool_name,
                            "param": chosen["path"],
                            "result": act_res
                        }
                        if on_tool:
                            on_tool(tool_info)
                        on_chunk(resp_msg)
                        audio_b64 = self.voice_engine.generate_speech_base64(f"Opened {chosen['name']} for you, sir.") if self.voice_engine.is_enabled() else None
                        record_turn("user", user_message)
                        record_turn("assistant", resp_msg, tool_info=tool_info)
                        on_complete(resp_msg, tool_info, audio_b64, None, session_id)
                        return

        # 4. Check if user is replying to a pending app selection or web suggestion
        if app_launcher.pending_app_selection:
            chosen_app = app_launcher.evaluate_selection_reply(user_message)
            if chosen_app == "CANCEL":
                cancel_msg = "App launch cancelled, sir."
                on_chunk(cancel_msg)
                audio_b64 = self.voice_engine.generate_speech_base64(cancel_msg) if self.voice_engine.is_enabled() else None
                record_turn("user", user_message)
                record_turn("assistant", cancel_msg)
                on_complete(cancel_msg, None, audio_b64, None, session_id)
                return
            elif chosen_app:
                launch_res = app_launcher.resolve_and_launch(chosen_app)
                tool_info = {
                    "tool": "open_app",
                    "param": chosen_app,
                    "result": launch_res
                }
                if on_tool:
                    on_tool(tool_info)
                resp_msg = f"🚀 Opened **{chosen_app}** for you, sir."
                on_chunk(resp_msg)
                audio_b64 = self.voice_engine.generate_speech_base64(f"Opened {chosen_app} for you, sir.") if self.voice_engine.is_enabled() else None
                record_turn("user", user_message)
                record_turn("assistant", resp_msg, tool_info=tool_info)
                on_complete(resp_msg, tool_info, audio_b64, None, session_id)
                return

        if app_launcher.pending_web_suggestion:
            web_res = app_launcher.evaluate_web_reply(user_message)
            if web_res == "CANCEL":
                cancel_msg = "Understood, cancelled opening web browser."
                on_chunk(cancel_msg)
                record_turn("user", user_message)
                record_turn("assistant", cancel_msg)
                on_complete(cancel_msg, None, None, None, session_id)
                return
            elif web_res:
                on_chunk(web_res)
                audio_b64 = self.voice_engine.generate_speech_base64(web_res) if self.voice_engine.is_enabled() else None
                record_turn("user", user_message)
                record_turn("assistant", web_res)
                on_complete(web_res, None, audio_b64, None, session_id)
                return

        # 4. Trigger background memory extraction
        model_name = self.groq_client.model if self.provider == "groq" else self.ollama_model
        self.memory_mgr.trigger_background_extraction(
            user_message=user_message,
            ollama_url=self.chat_url,
            model=self.ollama_model
        )

        # 5. Check for fast-path direct tool execution
        fast_action = self._detect_fast_intent(user_message, session_id=session_id)
        if not fast_action:
            fast_action = self._unified_ai_dispatch(user_message)
        tool_action_performed = None

        if fast_action:
            if fast_action.get("file_doubt"):
                matches = fast_action.get("matches", [])
                target_type = fast_action.get("type", "file")
                lines = []
                chip_options = []
                for i, m in enumerate(matches[:5]):
                    loc = m.get("parent") or m.get("display")
                    size_info = f" ({m['size_kb']} KB)" if "size_kb" in m else ""
                    lines.append(f"{i+1}. **{m['name']}** in `{m['path']}`{size_info}")
                    chip_options.append(f"{i+1}. {loc}/{m['name']}" if target_type == "file" else f"{i+1}. {m['name']}")

                chip_options.append("Cancel")
                options_text = "\n".join(lines)
                sugg_chips = " | ".join(chip_options)

                doubt_msg = (
                    f"I found multiple {target_type}s matching **'{fast_action['query']}'**. Which one would you like me to open?\n\n"
                    f"{options_text}\n\n"
                    f"[Suggestion: {sugg_chips}]"
                )
                on_chunk(doubt_msg)
                audio_b64 = self.voice_engine.generate_speech_base64(f"I found multiple {target_type}s matching {fast_action['query']}. Which one would you like to open?") if self.voice_engine.is_enabled() else None
                record_turn("user", user_message)
                record_turn("assistant", doubt_msg)
                on_complete(doubt_msg, None, audio_b64, None, session_id)
                return
            elif fast_action.get("doubt"):
                matches = fast_action.get("matches", [])
                options_text = "\n".join([f"{i+1}. **{name}**" for i, name in enumerate(matches)])
                sugg_chips = " | ".join(matches)
                doubt_msg = (
                    f"I found multiple applications matching **'{fast_action['query']}'**. Which one would you like me to open?\n\n"
                    f"{options_text}\n\n"
                    f"[Suggestion: {sugg_chips}]"
                )
                on_chunk(doubt_msg)
                audio_b64 = self.voice_engine.generate_speech_base64(f"I found multiple applications matching {fast_action['query']}. Which one would you like to open?") if self.voice_engine.is_enabled() else None
                record_turn("user", user_message)
                record_turn("assistant", doubt_msg)
                on_complete(doubt_msg, None, audio_b64, None, session_id)
                return
            elif fast_action.get("web_suggestion"):
                name = fast_action.get("name")
                ask_msg = (
                    f"I couldn't find **'{name}'** installed locally on your laptop. "
                    f"Would you like me to open it in your web browser?\n\n"
                    f"[Suggestion: Open {name} in Browser | Cancel]"
                )
                on_chunk(ask_msg)
                audio_b64 = self.voice_engine.generate_speech_base64(f"I couldn't find {name} installed locally. Would you like to open it in your browser?") if self.voice_engine.is_enabled() else None
                record_turn("user", user_message)
                record_turn("assistant", ask_msg)
                on_complete(ask_msg, None, audio_b64, None, session_id)
                return
            elif fast_action.get("tool") in ["edit_image", "edit_video", "display_media", "create_presentation", "create_document", "create_pdf", "open_file", "generate_ai_image", "alter_ai_image", "generate_ai_video", "take_screenshot"]:
                t_tool = fast_action.get("tool")
                if t_tool in ["create_presentation", "create_document", "create_pdf"]:
                    set_status("Creating...", "creating", f"Generating slides and formatting '{fast_action.get('param', 'document')}'...")
                elif t_tool in ["generate_ai_image", "alter_ai_image", "generate_ai_video", "edit_image", "edit_video"]:
                    set_status("Creating...", "creating", "Synthesizing generative visual media...")
                else:
                    set_status("Executing...", "executing", f"Executing system action: {t_tool}...")

                tool_action_performed = fast_action
                if on_tool:
                    on_tool(fast_action)

                res = fast_action.get("result", {})
                summary_text = res.get("summary") or res.get("action") or "Action completed."
                out_p = self._result_media_path(res)
                resp_msg = self._append_preview_markup(summary_text, out_p) if out_p else summary_text

                on_chunk(resp_msg)
                set_status("Speaking...", "speaking", "Synthesizing English voice response...")
                audio_b64 = None
                if self.voice_engine.is_enabled():
                    try:
                        speech_text = resp_msg.split("[MEDIA:")[0].split("[DOCUMENT:")[0].split("[Suggestion:")[0].strip()
                        audio_b64 = self.voice_engine.synthesize_and_speak(speech_text, play_audio=False)
                    except Exception as e:
                        print(f"[AssistantEngine] Voice synthesis error: {e}")
                record_turn("user", user_message, atts=attachments)
                record_turn("assistant", resp_msg, tool_info=fast_action)
                model_used = getattr(self.groq_client, "last_model_used", self.model)
                on_complete(resp_msg, fast_action, audio_b64, model_used, session_id)
                return
            else:
                tool_action_performed = fast_action
                if on_tool:
                    on_tool(fast_action)

        # 6. Build conversation history
        session = self.history_mgr.get_session(session_id)
        conversation_messages = [
            {"role": "system", "content": self.build_system_prompt(voice_mode=voice_mode)}
        ]

        if session and "messages" in session:
            for m in session["messages"][-16:]:
                conversation_messages.append({"role": m["role"], "content": m["content"]})

        user_prompt_content = user_message
        if attachments:
            media_lines = [f"[Attached Media: {a.get('name', 'file')} ({a.get('type', 'media')}) at path: `{a.get('path', '')}`]" for a in attachments]
            user_prompt_content += "\n\n" + "\n".join(media_lines)

        if fast_action and fast_action.get("result"):
            action_desc = fast_action["result"].get("summary") or fast_action["result"].get("action")
            user_prompt_content += f"\n\n[System Notification: Automatically executed {fast_action['tool']}. Result: {action_desc}]"

        conversation_messages.append({"role": "user", "content": user_prompt_content})

        # 6. Stream from active provider (Super AI cascade, Gemini, Groq, or Ollama)
        full_response = ""
        is_google_configured = self.gemini_client.is_configured()
        image_paths = [
            a["path"] for a in (attachments or [])
            if a.get("type") == "image" and os.path.exists(a.get("path", ""))
        ]

        if self.model == "super-ai" and (self.groq_client.is_configured() or is_google_configured):
            full_response = self._stream_super_ai(
                conversation_messages, on_chunk, set_status, user_message, attachments
            )
            if self._is_failed_model_output(full_response) and image_paths and self.groq_client.is_configured():
                set_status("Analyzing...", "analyzing", "Trying vision fallback after model cascade...")
                vision_bits = []
                flushed = {"ok": False}

                def vision_chunk(piece):
                    if not piece:
                        return
                    vision_bits.append(piece)
                    combined = "".join(vision_bits).lstrip()
                    if flushed["ok"]:
                        on_chunk(piece)
                        return
                    if combined.startswith("❌") or combined.startswith("⚠️"):
                        return
                    flushed["ok"] = True
                    for part in vision_bits:
                        on_chunk(part)

                vision_res = self.groq_client.stream_vision_chat(
                    user_text=user_message, image_paths=image_paths, on_chunk=vision_chunk
                )
                if not self._is_failed_model_output(vision_res):
                    full_response = vision_res
                    if not flushed["ok"]:
                        on_chunk(vision_res)
            if self._is_failed_model_output(full_response):
                err_msg = "❌ All suitable AI models failed to answer this request. Please try again in a moment."
                full_response = err_msg
                on_chunk(err_msg)
        elif self.model.startswith("gemini-") and is_google_configured:
            friendly_name = SuperAIRouter.get_friendly_name(self.model)
            set_status("Thinking...", "thinking", f"Reasoning with {friendly_name}...")
            full_response = self.gemini_client.stream_chat(conversation_messages, on_chunk, model_override=self.model)
            self.groq_client.last_model_used = self.model
        elif self.provider == "groq" and self.groq_client.is_configured():
            if image_paths and not is_google_configured:
                set_status("Analyzing...", "analyzing", "Inspecting attached media with Vision AI...")
                full_response = self.groq_client.stream_vision_chat(
                    user_text=user_message,
                    image_paths=image_paths,
                    on_chunk=on_chunk
                )
            else:
                set_status("Thinking...", "thinking", f"Reasoning with {self.model}...")
                full_response = self.groq_client.stream_chat(conversation_messages, on_chunk)
        else:
            # Fallback to local Ollama
            set_status("Thinking...", "thinking", f"Reasoning with local Ollama ({self.ollama_model})...")
            try:
                response = requests.post(
                    self.chat_url,
                    json={
                        "model": self.ollama_model,
                        "messages": conversation_messages,
                        "stream": True,
                        "think": False
                    },
                    stream=True,
                    timeout=60
                )
                if response.status_code != 200:
                    err_msg = f"Ollama error ({response.status_code}): {response.text}"
                    on_chunk(err_msg)
                    on_complete(err_msg, None, None)
                    return

                for line in response.iter_lines():
                    if line:
                        try:
                            chunk_json = json.loads(line)
                            piece = chunk_json.get("message", {}).get("content", "")
                            if piece:
                                full_response += piece
                                on_chunk(piece)
                        except Exception:
                            continue
            except Exception as e:
                err_msg = f"Could not connect to model: {e}"
                on_chunk(err_msg)
                on_complete(err_msg, None, None)
                return

        # 7. Parse autonomous actions emitted by the model
        action_pattern = re.compile(r"\[(?:ACTION|TOOL):\s*(\w+)\((.*?)\)\]")
        for match in action_pattern.finditer(full_response):
            t_name = match.group(1).strip()
            raw_args = match.group(2).strip()

            args = []
            for a in re.findall(r'"([^"]*)"|\'([^\']*)\'|([^,]+)', raw_args):
                val = a[0] or a[1] or a[2]
                args.append(val.strip())

            # Inspect action with Permission Guard
            inspection = self.permission_guard.inspect_action(t_name, *args)
            if inspection.get("requires_approval"):
                # Safety Guard intercepted action! Stop execution and ask user for confirmation.
                ask_confirm_msg = f"\n\n{inspection['question']}"
                on_chunk(ask_confirm_msg)
                full_response += ask_confirm_msg

                audio_b64 = self.voice_engine.synthesize_and_speak(inspection["question"], play_audio=True) if self.voice_engine.is_enabled() else None
                record_turn("user", user_message, atts=attachments)
                record_turn("assistant", full_response)
                model_used = getattr(self.groq_client, "last_model_used", self.model)
                on_complete(full_response, None, audio_b64, model_used, session_id)
                return

            # Execute permitted action
            if t_name in ["create_presentation", "create_document", "create_pdf", "generate_ai_image", "alter_ai_image", "generate_ai_video"]:
                set_status("Creating...", "creating", f"Creating content with {t_name}...")
            elif t_name in ["search_files", "search_folders", "web_search", "inspect_media", "read_file", "list_directory"]:
                set_status("Analyzing...", "analyzing", f"Inspecting system data with {t_name}...")
            else:
                set_status("Executing...", "executing", f"Executing system action: {t_name}...")
            t_result = AssistantTools.execute_tool(t_name, *args)
            if t_result.get("file_doubt"):
                matches = t_result.get("matches", [])
                target_type = t_result.get("type", "file")
                lines = []
                chip_options = []
                for i, m in enumerate(matches[:5]):
                    loc = m.get("parent") or m.get("display")
                    size_info = f" ({m['size_kb']} KB)" if "size_kb" in m else ""
                    lines.append(f"{i+1}. **{m['name']}** in `{m['path']}`{size_info}")
                    chip_options.append(f"{i+1}. {loc}/{m['name']}" if target_type == "file" else f"{i+1}. {m['name']}")

                chip_options.append("Cancel")
                options_text = "\n".join(lines)
                sugg_chips = " | ".join(chip_options)

                doubt_msg = (
                    f"I found multiple {target_type}s matching **'{t_result.get('query', 'target')}'**. Which one would you like me to open?\n\n"
                    f"{options_text}\n\n"
                    f"[Suggestion: {sugg_chips}]"
                )
                on_chunk(doubt_msg)
                audio_b64 = self.voice_engine.generate_speech_base64(f"I found multiple {target_type}s matching. Which one would you like to open?") if self.voice_engine.is_enabled() else None
                record_turn("user", user_message, atts=attachments)
                record_turn("assistant", doubt_msg)
                on_complete(doubt_msg, None, audio_b64, None, session_id)
                return
            elif t_result.get("doubt"):
                matches = t_result.get("matches", [])
                options_text = "\n".join([f"{i+1}. **{name}**" for i, name in enumerate(matches)])
                sugg_chips = " | ".join(matches)
                doubt_msg = (
                    f"I found multiple applications matching **'{t_result['query']}'**. Which one would you like me to open?\n\n"
                    f"{options_text}\n\n"
                    f"[Suggestion: {sugg_chips}]"
                )
                on_chunk(doubt_msg)
                audio_b64 = self.voice_engine.generate_speech_base64(f"I found multiple applications matching {t_result['query']}. Which one would you like to open?") if self.voice_engine.is_enabled() else None
                record_turn("user", user_message, atts=attachments)
                record_turn("assistant", doubt_msg)
                on_complete(doubt_msg, None, audio_b64, None, session_id)
                return
            elif t_result.get("web_suggestion"):
                name = t_result.get("name")
                ask_msg = (
                    f"I couldn't find **'{name}'** installed locally on your laptop. "
                    f"Would you like me to open it in your web browser?\n\n"
                    f"[Suggestion: Open {name} in Browser | Cancel]"
                )
                on_chunk(ask_msg)
                audio_b64 = self.voice_engine.generate_speech_base64(f"I couldn't find {name} installed locally. Would you like to open it in your browser?") if self.voice_engine.is_enabled() else None
                record_turn("user", user_message, atts=attachments)
                record_turn("assistant", ask_msg)
                on_complete(ask_msg, None, audio_b64, None, session_id)
                return

            tool_action_performed = {
                "tool": t_name,
                "param": args[0] if args else "",
                "result": t_result
            }
            if on_tool:
                on_tool(tool_action_performed)

        # 8. Clean response for display
        clean_display = action_pattern.sub("", full_response).strip()
        if not clean_display and tool_action_performed:
            clean_display = tool_action_performed.get("result", {}).get("summary") or tool_action_performed.get("result", {}).get("action", "Action completed, sir.")

        # Check if media or document output was generated
        active_res = (tool_action_performed or fast_action or {}).get("result", {})
        out_p = self._result_media_path(active_res)
        if out_p:
            clean_display = self._append_preview_markup(clean_display, out_p)

        # 9. Voice Synthesis
        audio_b64 = None
        if self.voice_engine.is_enabled():
            set_status("Speaking...", "speaking", "Synthesizing English voice response...")
            try:
                speech_text = clean_display.split("[MEDIA:")[0].split("[DOCUMENT:")[0].split("[Suggestion:")[0].strip()
                audio_b64 = self.voice_engine.synthesize_and_speak(speech_text, play_audio=False)
            except Exception as e:
                print(f"[AssistantEngine] Voice synthesis error: {e}")

        # 10. Record history
        record_turn("user", user_message, atts=attachments)
        record_turn("assistant", clean_display, tool_info=tool_action_performed)

        model_used = getattr(self.groq_client, "last_model_used", self.model)
        on_complete(clean_display, tool_action_performed, audio_b64, model_used, session_id)
