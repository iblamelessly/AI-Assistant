import os
import json
import re
import requests
from .tools import AssistantTools
from .voice import VoiceEngine

DEFAULT_MODEL = "qwen3:1.7b"
DEFAULT_OLLAMA_URL = "http://localhost:11434"

class AssistantEngine:
    """Manages autonomous agent conversations, dynamic prompt building, tool calling, and streaming with Ollama."""

    def __init__(self, memory_mgr, history_mgr, voice_engine=None, model=DEFAULT_MODEL, ollama_url=DEFAULT_OLLAMA_URL):
        self.memory_mgr = memory_mgr
        self.history_mgr = history_mgr
        self.voice_engine = voice_engine if voice_engine else VoiceEngine()
        self.model = model
        self.ollama_url = ollama_url.rstrip("/")
        self.chat_url = f"{self.ollama_url}/api/chat"

    def get_installed_models(self):
        """Fetch models installed in local Ollama instance."""
        try:
            r = requests.get(f"{self.ollama_url}/api/tags", timeout=3)
            if r.status_code == 200:
                data = r.json()
                return [m["name"] for m in data.get("models", [])]
        except Exception:
            pass
        return [self.model]

    def set_model(self, model_name):
        self.model = model_name

    def build_system_prompt(self):
        """Build dynamic system prompt giving Jarvis autonomous laptop control and awareness."""
        memory_json = self.memory_mgr.get_formatted_summary()
        current_time_info = AssistantTools.get_date_time()["summary"]
        current_dir = os.getcwd()

        return (
            "You are JARVIS, an autonomous personal AI assistant with FULL ACCESS AND CONTROL "
            "over the user's laptop, files, terminal, and development environment (inspired by Iron Man).\n\n"
            f"SYSTEM ENVIRONMENT:\n"
            f"- {current_time_info}\n"
            f"- Active Working Directory: {current_dir}\n"
            f"- OS: Windows\n\n"
            f"PERMANENT USER PROFILE:\n"
            f"{memory_json}\n\n"
            "AUTONOMOUS ACTIONS & LAPTOP TOOLS:\n"
            "You have full permissions to operate the laptop. When asked to perform tasks, "
            "include the corresponding [ACTION: ...] tag in your response so the system executes it:\n\n"
            "1. Terminal & Command Execution:\n"
            "   - [ACTION: run_command(\"powershell_or_git_command\")]\n"
            "     Examples: [ACTION: run_command(\"git status\")], [ACTION: run_command(\"python main.py\")], [ACTION: run_command(\"dir\")]\n\n"
            "2. File System Operations:\n"
            "   - [ACTION: read_file(\"path/to/file\")]\n"
            "   - [ACTION: write_file(\"path/to/file\", \"content\")]\n"
            "   - [ACTION: list_directory(\"folder_path\")]\n\n"
            "3. Hardware & Laptop Controls:\n"
            "   - [ACTION: set_volume(\"up\" | \"down\" | \"mute\")]\n"
            "   - [ACTION: take_screenshot()]\n"
            "   - [ACTION: open_app(\"notepad\" | \"chrome\" | \"vscode\" | \"calc\" | \"spotify\")]\n"
            "   - [ACTION: kill_process(\"process_name\")]\n"
            "   - [ACTION: get_system_stats()]\n"
            "   - [ACTION: web_search(\"query\")]\n\n"
            "RULES:\n"
            "1. When the user asks you to check git, run code, edit a file, or adjust laptop settings, EXECUTE IT IMMEDIATELY using the action tag.\n"
            "2. Address the user with respectful, intelligent confidence (like JARVIS addressing Tony Stark).\n"
            "3. Seamlessly remember user facts from their profile.\n"
            "4. Keep explanations concise, professional, and clear."
        )

    def _detect_fast_intent(self, user_message: str):
        """Fast-path detector for immediate direct user commands."""
        msg = user_message.lower().strip()

        # Git status / git commands
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
        if any(phrase in msg for phrase in ["system stats", "cpu usage", "ram usage", "battery level", "pc performance", "hardware metrics"]):
            res = AssistantTools.get_system_stats()
            return {"tool": "get_system_stats", "result": res}

        # Open apps
        open_match = re.search(r"^(?:please\s+)?(?:open|launch|start)\s+([a-zA-Z0-9\s]+)$", msg)
        if open_match:
            app_target = open_match.group(1).strip()
            if app_target not in ["the door", "up", "a discussion", "settings"]:
                res = AssistantTools.open_application(app_target)
                return {"tool": "open_app", "param": app_target, "result": res}

        # Web search
        search_match = re.search(r"^(?:search\s+(?:web\s+for|google\s+for|for)?|google)\s+(.+)$", msg)
        if search_match:
            query = search_match.group(1).strip()
            res = AssistantTools.open_web_search(query)
            return {"tool": "web_search", "param": query, "result": res}

        return None

    def stream_chat(self, session_id: str, user_message: str, on_chunk, on_complete, on_tool=None):
        """
        Processes a conversation turn with autonomous tool execution, token streaming,
        and optional neural voice synthesis.
        """
        # 1. Background memory extraction
        self.memory_mgr.trigger_background_extraction(
            user_message=user_message,
            ollama_url=self.chat_url,
            model=self.model
        )

        # 2. Check for fast-path direct tool execution
        fast_action = self._detect_fast_intent(user_message)
        tool_action_performed = None

        if fast_action:
            tool_action_performed = fast_action
            if on_tool:
                on_tool(fast_action)

        # 3. Retrieve conversation history
        session = self.history_mgr.get_session(session_id)
        conversation_messages = []

        conversation_messages.append({
            "role": "system",
            "content": self.build_system_prompt()
        })

        if session and "messages" in session:
            for m in session["messages"][-16:]:
                conversation_messages.append({
                    "role": m["role"],
                    "content": m["content"]
                })

        user_prompt_content = user_message
        if fast_action and fast_action.get("result"):
            action_desc = fast_action["result"].get("summary") or fast_action["result"].get("action")
            user_prompt_content += f"\n\n[System Notification: Automatically executed {fast_action['tool']}. Result: {action_desc}]"

        conversation_messages.append({
            "role": "user",
            "content": user_prompt_content
        })

        # 4. Stream response from Ollama
        full_response = ""
        try:
            response = requests.post(
                self.chat_url,
                json={
                    "model": self.model,
                    "messages": conversation_messages,
                    "stream": True,
                    "think": False
                },
                stream=True,
                timeout=60
            )

            if response.status_code != 200:
                err_msg = f"Ollama error (HTTP {response.status_code}): {response.text}"
                on_chunk(err_msg)
                on_complete(err_msg, None, None)
                return

            for line in response.iter_lines():
                if line:
                    try:
                        chunk_json = json.loads(line)
                        content_piece = chunk_json.get("message", {}).get("content", "")
                        if content_piece:
                            full_response += content_piece
                            on_chunk(content_piece)
                    except Exception:
                        continue

            # 5. Parse any [ACTION: ...] or [TOOL: ...] tags emitted by model
            action_pattern = re.compile(r"\[(?:ACTION|TOOL):\s*(\w+)\((.*?)\)\]")
            for match in action_pattern.finditer(full_response):
                t_name = match.group(1).strip()
                raw_args = match.group(2).strip()

                # Parse arguments safely (handling single or multiple quoted strings)
                args = []
                for a in re.findall(r'"([^"]*)"|\'([^\']*)\'|([^,]+)', raw_args):
                    val = a[0] or a[1] or a[2]
                    args.append(val.strip())

                t_result = AssistantTools.execute_tool(t_name, *args)
                tool_action_performed = {
                    "tool": t_name,
                    "param": args[0] if args else "",
                    "result": t_result
                }
                if on_tool:
                    on_tool(tool_action_performed)

            # Clean response for display
            clean_display_response = action_pattern.sub("", full_response).strip()
            if not clean_display_response and tool_action_performed:
                clean_display_response = tool_action_performed.get("result", {}).get("summary") or tool_action_performed.get("result", {}).get("action", "Action completed, sir.")

            # 6. Generate Neural Audio if voice enabled
            audio_b64 = None
            if self.voice_engine.is_enabled():
                try:
                    audio_b64 = self.voice_engine.generate_speech_base64(clean_display_response)
                except Exception as e:
                    print(f"[AssistantEngine] Voice generation error: {e}")

            # 7. Save to history
            self.history_mgr.add_message(session_id, "user", user_message)
            self.history_mgr.add_message(session_id, "assistant", clean_display_response, tool_info=tool_action_performed)

            on_complete(clean_display_response, tool_action_performed, audio_b64)

        except requests.exceptions.ConnectionError:
            err_msg = "❌ Error: Could not connect to Ollama. Please ensure Ollama is running (`ollama serve`)."
            on_chunk(err_msg)
            on_complete(err_msg, None, None)
        except Exception as e:
            err_msg = f"❌ An error occurred: {str(e)}"
            on_chunk(err_msg)
            on_complete(err_msg, None, None)
