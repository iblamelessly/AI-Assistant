import os
import json
import re
import requests
from .tools import AssistantTools

DEFAULT_MODEL = "qwen3:1.7b"
DEFAULT_OLLAMA_URL = "http://localhost:11434"

class AssistantEngine:
    """Manages conversations, dynamic prompt building, tool calling, and streaming with Ollama."""

    def __init__(self, memory_mgr, history_mgr, model=DEFAULT_MODEL, ollama_url=DEFAULT_OLLAMA_URL):
        self.memory_mgr = memory_mgr
        self.history_mgr = history_mgr
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
        """Build dynamic system prompt with up-to-date memory and tool definitions."""
        memory_json = self.memory_mgr.get_formatted_summary()
        current_time_info = AssistantTools.get_date_time()["summary"]

        return (
            "You are Jarvis, an intelligent, helpful, and concise personal AI assistant for your user.\n\n"
            "CURRENT SYSTEM CONTEXT:\n"
            f"- {current_time_info}\n\n"
            "PERMANENT USER MEMORY (What you know about the user):\n"
            f"{memory_json}\n\n"
            "CAPABILITIES & TOOLS:\n"
            "You have access to desktop system tools. When the user asks you to perform a system action, "
            "include the corresponding tool tag in your response so the system can execute it:\n"
            "- Launch apps: [TOOL: open_app(\"app_name\")] (e.g. notepad, calc, chrome, spotify, vscode, terminal, explorer)\n"
            "- System metrics: [TOOL: get_system_stats()]\n"
            "- Web search: [TOOL: web_search(\"search query\")]\n"
            "- Date and time: [TOOL: get_date_time()]\n\n"
            "RULES:\n"
            "1. Seamlessly use information from permanent user memory when answering or offering recommendations.\n"
            "2. Be concise, friendly, professional, and helpful.\n"
            "3. If performing an action, briefly state what you're doing and include the [TOOL: ...] tag.\n"
            "4. Never invent or hallucinate personal details not present in memory."
        )

    def _detect_fast_intent(self, user_message):
        """Detect direct user command intents like opening apps or checking stats."""
        msg = user_message.lower().strip()

        # Check stats
        if any(phrase in msg for phrase in ["system stats", "cpu usage", "ram usage", "battery level", "pc stats", "pc performance"]):
            res = AssistantTools.get_system_stats()
            return {"tool": "get_system_stats", "result": res}

        # Open apps
        open_match = re.search(r"^(?:please\s+)?(?:open|launch|start)\s+([a-zA-Z0-9\s]+)$", msg)
        if open_match:
            app_target = open_match.group(1).strip()
            # Ignore common conversational queries
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

    def stream_chat(self, session_id, user_message, on_chunk, on_complete, on_tool=None):
        """
        Processes a chat turn with streaming response.
        - Triggers non-blocking background memory extraction.
        - Streams tokens to on_chunk(token).
        - Executes any detected tools.
        - Saves to history and calls on_complete(full_text, tool_info).
        """
        # 1. Trigger background memory extraction immediately (non-blocking)
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

        # Start with dynamic system prompt
        conversation_messages.append({
            "role": "system",
            "content": self.build_system_prompt()
        })

        if session and "messages" in session:
            # Include recent chat history (last 16 messages to prevent unbounded context growth)
            for m in session["messages"][-16:]:
                conversation_messages.append({
                    "role": m["role"],
                    "content": m["content"]
                })

        # Append current user message (with fast tool result context if applicable)
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
                on_complete(err_msg, None)
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

            # 5. Check if model generated any [TOOL: ...] tags
            tool_pattern = re.compile(r"\[TOOL:\s*(\w+)\((.*?)\)\]")
            for match in tool_pattern.finditer(full_response):
                t_name = match.group(1).strip()
                t_arg = match.group(2).strip().strip('"').strip("'")
                t_result = AssistantTools.execute_tool(t_name, t_arg)
                tool_action_performed = {
                    "tool": t_name,
                    "param": t_arg,
                    "result": t_result
                }
                if on_tool:
                    on_tool(tool_action_performed)

            # Clean response for display/history
            clean_display_response = tool_pattern.sub("", full_response).strip()
            if not clean_display_response and tool_action_performed:
                clean_display_response = tool_action_performed.get("result", {}).get("action", "Action completed.")

            # 6. Save message history
            self.history_mgr.add_message(session_id, "user", user_message)
            self.history_mgr.add_message(session_id, "assistant", clean_display_response, tool_info=tool_action_performed)

            on_complete(clean_display_response, tool_action_performed)

        except requests.exceptions.ConnectionError:
            err_msg = "❌ Error: Could not connect to Ollama. Please ensure Ollama is running (`ollama serve`)."
            on_chunk(err_msg)
            on_complete(err_msg, None)
        except Exception as e:
            err_msg = f"❌ An error occurred: {str(e)}"
            on_chunk(err_msg)
            on_complete(err_msg, None)
