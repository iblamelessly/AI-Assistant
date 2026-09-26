import os
import json
import re
import requests
from .tools import AssistantTools
from .voice import VoiceEngine
from .config import ConfigManager
from .groq_client import GroqClient, AVAILABLE_GROQ_MODELS
from .permissions import PermissionGuard
from .app_launcher import app_launcher
from .file_search import file_search_engine

class AssistantEngine:
    """
    Unified Autonomous Agent Engine supporting:
    - Ultra-fast Groq Cloud (Llama 3.3 70B) & Local Ollama
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
            model=self.config_mgr.get("groq_model", "llama-3.3-70b-versatile")
        )

        self.provider = self.config_mgr.get("provider", "groq")
        self.ollama_model = self.config_mgr.get("ollama_model", "qwen3:1.7b")
        self.ollama_url = self.config_mgr.get("ollama_url", "http://localhost:11434").rstrip("/")
        self.chat_url = f"{self.ollama_url}/api/chat"

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

    def get_installed_models(self):
        """Fetch available models based on active provider."""
        if self.provider == "groq":
            return [m["id"] for m in self.groq_client.get_dynamic_models()]
        else:
            try:
                r = requests.get(f"{self.ollama_url}/api/tags", timeout=3)
                if r.status_code == 200:
                    data = r.json()
                    return [m["name"] for m in data.get("models", [])]
            except Exception:
                pass
            return [self.ollama_model]

    def set_model(self, model_name: str):
        if self.provider == "groq":
            self.groq_client.set_model(model_name)
            self.config_mgr.set("groq_model", model_name)
        else:
            self.ollama_model = model_name
            self.config_mgr.set("ollama_model", model_name)

    def build_system_prompt(self):
        """Build dynamic system prompt giving Jarvis human-like common sense and autonomous control."""
        memory_json = self.memory_mgr.get_formatted_summary()
        current_time_info = AssistantTools.get_date_time()["summary"]
        current_dir = os.getcwd()

        return (
            "You are JARVIS, an intelligent, human-like autonomous AI assistant for your user.\n"
            "You have full access to the user's laptop, terminal, and development environment (like Iron Man).\n\n"
            f"SYSTEM ENVIRONMENT:\n"
            f"- {current_time_info}\n"
            f"- Working Directory: {current_dir}\n"
            f"- OS: Windows\n\n"
            f"PERMANENT USER PROFILE:\n"
            f"{memory_json}\n\n"
            "HUMAN-LIKE SENSE & SAFETY RULES:\n"
            "1. Clarify Ambiguity: If the user asks to delete or wipe something without specifying which copy, "
            "ask whether they mean the original, a backup copy, or duplicates before acting.\n"
            "2. Safety First: Never execute destructive file deletions or kill critical system tasks without explicitly "
            "asking confirmation: 'Proceed? [Yes / No]'.\n"
            "3. Respectful & Confident: Address the user intelligently, concisely, and respectfully.\n"
            "4. Smart App Launching: When the user asks to open an application, think carefully about what they meant. "
            "If an app has multiple editions or is ambiguous, ask them for clarification with suggestions.\n"
            "5. File & Folder Disambiguation: If a file or folder search yields multiple matches across different directories, "
            "do not guess blindly. Present the choices to the user with helpful suggestions.\n\n"
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
            "- Adjust volume: [ACTION: set_volume(\"up\" | \"down\" | \"mute\" | \"set to 50\")]\n"
            "- Screenshot: [ACTION: take_screenshot()]\n"
            "- Open app: [ACTION: open_app(\"app_name\")]\n"
            "- Terminate app: [ACTION: kill_process(\"process_name\")]\n"
            "- Web search: [ACTION: web_search(\"query\")]\n"
        )

    def _detect_fast_intent(self, user_message: str):
        """Fast-path detector for immediate direct user commands."""
        msg = user_message.lower().strip()

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
        if any(w in msg for w in ["take a screenshot", "take screenshot", "capture screen"]):
            res = AssistantTools.take_screenshot()
            return {"tool": "take_screenshot", "param": "", "result": res}

        # System stats
        if any(phrase in msg for phrase in ["system stats", "cpu usage", "ram usage", "battery level", "pc performance"]):
            res = AssistantTools.get_system_stats()
            return {"tool": "get_system_stats", "result": res}

        # File & Folder Intent Detection (e.g. "find my python file main.py", "open downloads folder", "where is test.py")
        parsed_q = file_search_engine.parse_query(msg)
        is_file_folder_query = (
            parsed_q["is_folder"] or
            bool(parsed_q["extensions"]) or
            any(w in msg for w in ["file", "folder", "directory", "script", "document"]) or
            bool(re.search(r"^(?:find|search\s+for|search|locate|where\s+is)\b", msg))
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
            ignored_words = ["the door", "up", "a discussion", "a topic", "eyes", "mouth", "mind", "settings"]
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

    def stream_chat(self, session_id: str, user_message: str, on_chunk, on_complete, on_tool=None):
        """
        Processes a chat turn with:
        1. Human confirmation check (Yes/No response evaluation)
        2. Ambiguity & duplicate target detection
        3. Fast-path & autonomous tool execution
        4. Groq (Llama 3.3 70B) or Ollama streaming
        5. Neural Voice synthesis
        """
        # 1. Check if user is replying to a pending confirmation
        if self.permission_guard.has_pending():
            eval_res = self.permission_guard.evaluate_user_reply(user_message)
            if eval_res.get("has_pending"):
                if eval_res.get("confirmed") is True:
                    # User approved! Execute the pending action
                    action_data = eval_res["action"]
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

                    audio_b64 = self.voice_engine.generate_speech_base64(confirm_msg) if self.voice_engine.is_enabled() else None
                    self.history_mgr.add_message(session_id, "user", user_message)
                    self.history_mgr.add_message(session_id, "assistant", confirm_msg, tool_info=tool_info)
                    on_complete(confirm_msg, tool_info, audio_b64)
                    return
                elif eval_res.get("confirmed") is False:
                    cancel_msg = eval_res.get("message", "Operation cancelled, sir.")
                    on_chunk(cancel_msg)
                    audio_b64 = self.voice_engine.generate_speech_base64(cancel_msg) if self.voice_engine.is_enabled() else None
                    self.history_mgr.add_message(session_id, "user", user_message)
                    self.history_mgr.add_message(session_id, "assistant", cancel_msg)
                    on_complete(cancel_msg, None, audio_b64)
                    return
                elif eval_res.get("clarification"):
                    clarify_msg = eval_res["clarification"]
                    on_chunk(clarify_msg)
                    on_complete(clarify_msg, None, None)
                    return

        # 2. Check for ambiguity on deletion/modification commands
        ambiguity_q = self.permission_guard.detect_ambiguity_or_duplicates(user_message)
        if ambiguity_q:
            on_chunk(ambiguity_q)
            audio_b64 = self.voice_engine.generate_speech_base64(ambiguity_q) if self.voice_engine.is_enabled() else None
            self.history_mgr.add_message(session_id, "user", user_message)
            self.history_mgr.add_message(session_id, "assistant", ambiguity_q)
            on_complete(ambiguity_q, None, audio_b64)
            return

        # 3. Check if user is replying to a pending file or folder selection
        if file_search_engine.pending_file_selection:
            eval_res = file_search_engine.evaluate_selection_reply(user_message)
            if eval_res:
                if eval_res.get("status") == "cancel":
                    cancel_msg = "File/folder operation cancelled, sir."
                    on_chunk(cancel_msg)
                    audio_b64 = self.voice_engine.generate_speech_base64(cancel_msg) if self.voice_engine.is_enabled() else None
                    self.history_mgr.add_message(session_id, "user", user_message)
                    self.history_mgr.add_message(session_id, "assistant", cancel_msg)
                    on_complete(cancel_msg, None, audio_b64)
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
                    self.history_mgr.add_message(session_id, "user", user_message)
                    self.history_mgr.add_message(session_id, "assistant", resp_msg, tool_info=tool_info)
                    on_complete(resp_msg, tool_info, audio_b64)
                    return

        # 4. Check if user is replying to a pending app selection or web suggestion
        if app_launcher.pending_app_selection:
            chosen_app = app_launcher.evaluate_selection_reply(user_message)
            if chosen_app == "CANCEL":
                cancel_msg = "App launch cancelled, sir."
                on_chunk(cancel_msg)
                audio_b64 = self.voice_engine.generate_speech_base64(cancel_msg) if self.voice_engine.is_enabled() else None
                self.history_mgr.add_message(session_id, "user", user_message)
                self.history_mgr.add_message(session_id, "assistant", cancel_msg)
                on_complete(cancel_msg, None, audio_b64)
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
                self.history_mgr.add_message(session_id, "user", user_message)
                self.history_mgr.add_message(session_id, "assistant", resp_msg, tool_info=tool_info)
                on_complete(resp_msg, tool_info, audio_b64)
                return

        if app_launcher.pending_web_suggestion:
            web_res = app_launcher.evaluate_web_reply(user_message)
            if web_res == "CANCEL":
                cancel_msg = "Understood, cancelled opening web browser."
                on_chunk(cancel_msg)
                self.history_mgr.add_message(session_id, "user", user_message)
                self.history_mgr.add_message(session_id, "assistant", cancel_msg)
                on_complete(cancel_msg, None, None)
                return
            elif web_res:
                on_chunk(web_res)
                audio_b64 = self.voice_engine.generate_speech_base64(web_res) if self.voice_engine.is_enabled() else None
                self.history_mgr.add_message(session_id, "user", user_message)
                self.history_mgr.add_message(session_id, "assistant", web_res)
                on_complete(web_res, None, audio_b64)
                return

        # 4. Trigger background memory extraction
        model_name = self.groq_client.model if self.provider == "groq" else self.ollama_model
        self.memory_mgr.trigger_background_extraction(
            user_message=user_message,
            ollama_url=self.chat_url,
            model=self.ollama_model
        )

        # 5. Check for fast-path direct tool execution
        fast_action = self._detect_fast_intent(user_message)
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
                self.history_mgr.add_message(session_id, "user", user_message)
                self.history_mgr.add_message(session_id, "assistant", doubt_msg)
                on_complete(doubt_msg, None, audio_b64)
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
                self.history_mgr.add_message(session_id, "user", user_message)
                self.history_mgr.add_message(session_id, "assistant", doubt_msg)
                on_complete(doubt_msg, None, audio_b64)
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
                self.history_mgr.add_message(session_id, "user", user_message)
                self.history_mgr.add_message(session_id, "assistant", ask_msg)
                on_complete(ask_msg, None, audio_b64)
                return
            else:
                tool_action_performed = fast_action
                if on_tool:
                    on_tool(fast_action)

        # 6. Build conversation history
        session = self.history_mgr.get_session(session_id)
        conversation_messages = [
            {"role": "system", "content": self.build_system_prompt()}
        ]

        if session and "messages" in session:
            for m in session["messages"][-16:]:
                conversation_messages.append({"role": m["role"], "content": m["content"]})

        user_prompt_content = user_message
        if fast_action and fast_action.get("result"):
            action_desc = fast_action["result"].get("summary") or fast_action["result"].get("action")
            user_prompt_content += f"\n\n[System Notification: Automatically executed {fast_action['tool']}. Result: {action_desc}]"

        conversation_messages.append({"role": "user", "content": user_prompt_content})

        # 6. Stream from active provider (Groq or Ollama)
        full_response = ""
        if self.provider == "groq" and self.groq_client.is_configured():
            full_response = self.groq_client.stream_chat(conversation_messages, on_chunk)
        else:
            # Fallback to local Ollama
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

                audio_b64 = self.voice_engine.generate_speech_base64(inspection["question"]) if self.voice_engine.is_enabled() else None
                self.history_mgr.add_message(session_id, "user", user_message)
                self.history_mgr.add_message(session_id, "assistant", full_response)
                on_complete(full_response, None, audio_b64)
                return

            # Execute permitted action
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
                self.history_mgr.add_message(session_id, "user", user_message)
                self.history_mgr.add_message(session_id, "assistant", doubt_msg)
                on_complete(doubt_msg, None, audio_b64)
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
                self.history_mgr.add_message(session_id, "user", user_message)
                self.history_mgr.add_message(session_id, "assistant", doubt_msg)
                on_complete(doubt_msg, None, audio_b64)
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
                self.history_mgr.add_message(session_id, "user", user_message)
                self.history_mgr.add_message(session_id, "assistant", ask_msg)
                on_complete(ask_msg, None, audio_b64)
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

        # 9. Voice Synthesis
        audio_b64 = None
        if self.voice_engine.is_enabled():
            try:
                audio_b64 = self.voice_engine.generate_speech_base64(clean_display)
            except Exception as e:
                print(f"[AssistantEngine] Voice synthesis error: {e}")

        # 10. Record history
        self.history_mgr.add_message(session_id, "user", user_message)
        self.history_mgr.add_message(session_id, "assistant", clean_display, tool_info=tool_action_performed)

        on_complete(clean_display, tool_action_performed, audio_b64)
