import os
import json
import re
import requests
from .tools import AssistantTools
from .voice import VoiceEngine
from .config import ConfigManager
from .groq_client import GroqClient, AVAILABLE_GROQ_MODELS
from .permissions import PermissionGuard

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
            "3. Respectful & Confident: Address the user intelligently, concisely, and respectfully.\n\n"
            "AUTONOMOUS ACTIONS & LAPTOP TOOLS:\n"
            "When performing laptop tasks, include the corresponding [ACTION: ...] tag:\n"
            "- Run terminal/PowerShell: [ACTION: run_command(\"powershell_command\")] (e.g. git status, dir, python script.py)\n"
            "- Read file: [ACTION: read_file(\"path/to/file\")]\n"
            "- Write file: [ACTION: write_file(\"path/to/file\", \"content\")]\n"
            "- List directory: [ACTION: list_directory(\"path\")]\n"
            "- Adjust volume: [ACTION: set_volume(\"up\" | \"down\" | \"mute\" | \"set to 50\")]\n"
            "- Screenshot: [ACTION: take_screenshot()]\n"
            "- Open app: [ACTION: open_app(\"notepad\" | \"chrome\" | \"vscode\" | \"calc\")]\n"
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

        # Open apps
        open_match = re.search(r"^(?:please\s+)?(?:open|launch|start)\s+([a-zA-Z0-9\s]+)$", msg)
        if open_match:
            app_target = open_match.group(1).strip()
            if app_target not in ["the door", "up", "a discussion", "settings"]:
                res = AssistantTools.open_application(app_target)
                return {"tool": "open_app", "param": app_target, "result": res}

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

        # 3. Trigger background memory extraction
        model_name = self.groq_client.model if self.provider == "groq" else self.ollama_model
        self.memory_mgr.trigger_background_extraction(
            user_message=user_message,
            ollama_url=self.chat_url,
            model=self.ollama_model
        )

        # 4. Check for fast-path direct tool execution
        fast_action = self._detect_fast_intent(user_message)
        tool_action_performed = None

        if fast_action:
            tool_action_performed = fast_action
            if on_tool:
                on_tool(fast_action)

        # 5. Build conversation history
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
