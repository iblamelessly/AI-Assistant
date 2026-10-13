"""
Tool Registry for JARVIS Autonomous Agent.
Provides a discoverable, safe catalog of all computer and system tools,
categorized by domain with structured execution and risk classification.

Categories:
- System
- Apps
- Files
- Browser
- Computer
- Terminal
- Development
- Media
- Vision
"""

from typing import Dict, Any, List, Optional, Callable
import json

from core.tools import AssistantTools
from core.computer_control import ComputerControl
from core.permissions import PermissionGuard


class ToolDefinition:
    def __init__(self,
                 name: str,
                 description: str,
                 category: str,
                 risk_level: str,
                 parameters: Dict[str, Any],
                 handler: Callable):
        self.name = name
        self.description = description
        self.category = category.lower()
        self.risk_level = risk_level.lower()  # "low", "medium", "high"
        self.parameters = parameters
        self.handler = handler

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "risk_level": self.risk_level,
            "parameters": self.parameters
        }


class ToolRegistry:
    """Central registry and dispatcher for all agent-accessible tools."""

    def __init__(self, permission_guard: Optional[PermissionGuard] = None):
        self.permission_guard = permission_guard or PermissionGuard()
        self._tools: Dict[str, ToolDefinition] = {}
        self._register_default_tools()

    def register(self, tool: ToolDefinition):
        self._tools[tool.name.lower()] = tool

    def get_tool(self, name: str) -> Optional[ToolDefinition]:
        return self._tools.get(name.lower().strip())

    def list_tools(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        tools = []
        for t in self._tools.values():
            if category is None or t.category == category.lower():
                tools.append(t.to_dict())
        return tools

    def get_tools_prompt(self) -> str:
        """Generates an organized markdown specification of available tools for LLM agent planning."""
        lines = ["### Available Agent Tools:\n"]
        categories = {}
        for t in self._tools.values():
            categories.setdefault(t.category.title(), []).append(t)

        for cat, tool_list in sorted(categories.items()):
            lines.append(f"#### {cat} Tools:")
            for t in tool_list:
                param_str = ", ".join(f"{k}: {v.get('type', 'str')}" for k, v in t.parameters.items())
                risk_tag = f"[{t.risk_level.upper()} RISK]" if t.risk_level != "low" else ""
                lines.append(f"- **`{t.name}({param_str})`** {risk_tag}: {t.description}")
            lines.append("")

        return "\n".join(lines)

    def execute_tool(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        """
        Executes a registered tool safely with permission gating and structured return:
        {
            "success": bool,
            "action": str,
            "target": str,
            "error": str or None,
            "summary": str,
            "data": Any
        }
        """
        t = self.get_tool(tool_name)
        if not t:
            # Fallback to general AssistantTools.execute_tool
            args = list(kwargs.values())
            raw_res = AssistantTools.execute_tool(tool_name, *args)
            if isinstance(raw_res, dict) and "success" in raw_res:
                return {
                    "success": raw_res.get("success", False),
                    "action": tool_name,
                    "target": str(args[0]) if args else "",
                    "error": raw_res.get("error"),
                    "summary": raw_res.get("summary", f"Executed {tool_name}"),
                    "data": raw_res
                }
            return {
                "success": False,
                "action": tool_name,
                "target": str(kwargs),
                "error": f"Unknown tool: '{tool_name}'",
                "summary": f"Tool '{tool_name}' is not registered.",
                "data": None
            }

        # Permission check
        if t.risk_level in ["medium", "high"] and self.permission_guard:
            arg_vals = list(kwargs.values())
            perm = self.permission_guard.inspect_action(t.name, *arg_vals)
            if perm.get("requires_approval"):
                return {
                    "success": False,
                    "action": t.name,
                    "target": str(kwargs),
                    "error": "CONFIRMATION_REQUIRED",
                    "summary": perm.get("question", f"Approval required to execute {t.name}"),
                    "data": {"pending_confirmation": perm}
                }

        try:
            res = t.handler(**kwargs)
            if isinstance(res, dict) and "success" in res and "action" in res:
                return res
            # Wrap unstructured returns
            is_ok = bool(res.get("success", True)) if isinstance(res, dict) else bool(res)
            return {
                "success": is_ok,
                "action": t.name,
                "target": str(kwargs.get("target") or kwargs.get("path") or kwargs.get("query") or ""),
                "error": res.get("error") if isinstance(res, dict) else None,
                "summary": res.get("summary", f"Completed {t.name}") if isinstance(res, dict) else str(res),
                "data": res
            }
        except Exception as e:
            return {
                "success": False,
                "action": t.name,
                "target": str(kwargs),
                "error": str(e),
                "summary": f"Failed executing {t.name}: {e}",
                "data": None
            }

    def _register_default_tools(self):
        """Registers all built-in tools across the 9 defined categories."""

        # ── 1. Computer Control Tools ──────────────────────────
        self.register(ToolDefinition(
            name="mouse_click",
            description="Clicks mouse button at given screen coordinates (x, y) or current cursor location.",
            category="computer",
            risk_level="low",
            parameters={"x": {"type": "int", "optional": True}, "y": {"type": "int", "optional": True}, "button": {"type": "str", "default": "left"}},
            handler=lambda x=None, y=None, button="left": ComputerControl.mouse_click(x, y, button=button)
        ))

        self.register(ToolDefinition(
            name="mouse_double_click",
            description="Double clicks left mouse button at (x, y) coordinates.",
            category="computer",
            risk_level="low",
            parameters={"x": {"type": "int", "optional": True}, "y": {"type": "int", "optional": True}},
            handler=lambda x=None, y=None: ComputerControl.mouse_double_click(x, y)
        ))

        self.register(ToolDefinition(
            name="mouse_right_click",
            description="Performs right mouse click at (x, y) coordinates to open context menus.",
            category="computer",
            risk_level="low",
            parameters={"x": {"type": "int", "optional": True}, "y": {"type": "int", "optional": True}},
            handler=lambda x=None, y=None: ComputerControl.mouse_right_click(x, y)
        ))

        self.register(ToolDefinition(
            name="mouse_move",
            description="Moves cursor smoothly to screen coordinates (x, y).",
            category="computer",
            risk_level="low",
            parameters={"x": {"type": "int"}, "y": {"type": "int"}},
            handler=lambda x, y: ComputerControl.mouse_move(x, y)
        ))

        self.register(ToolDefinition(
            name="mouse_scroll",
            description="Scrolls mouse wheel (positive up, negative down).",
            category="computer",
            risk_level="low",
            parameters={"delta": {"type": "int"}, "x": {"type": "int", "optional": True}, "y": {"type": "int", "optional": True}},
            handler=lambda delta, x=None, y=None: ComputerControl.mouse_scroll(delta, x, y)
        ))

        self.register(ToolDefinition(
            name="keyboard_type",
            description="Types text directly into the active focused window using Unicode input.",
            category="computer",
            risk_level="low",
            parameters={"text": {"type": "str"}},
            handler=lambda text: ComputerControl.keyboard_type(text)
        ))

        self.register(ToolDefinition(
            name="keyboard_press",
            description="Presses a special key (enter, esc, tab, space, backspace, up, down, etc.).",
            category="computer",
            risk_level="low",
            parameters={"key": {"type": "str"}},
            handler=lambda key: ComputerControl.keyboard_press(key)
        ))

        self.register(ToolDefinition(
            name="keyboard_hotkey",
            description="Presses a keyboard shortcut combination (e.g. 'ctrl+c', 'ctrl+v', 'alt+tab', 'win+r').",
            category="computer",
            risk_level="low",
            parameters={"hotkey": {"type": "str"}},
            handler=lambda hotkey: ComputerControl.keyboard_hotkey(hotkey)
        ))

        self.register(ToolDefinition(
            name="window_focus",
            description="Finds and brings an application window to the foreground.",
            category="computer",
            risk_level="low",
            parameters={"target": {"type": "str"}},
            handler=lambda target: ComputerControl.window_focus(target)
        ))

        self.register(ToolDefinition(
            name="window_list",
            description="Lists all visible top-level application windows on the desktop.",
            category="computer",
            risk_level="low",
            parameters={},
            handler=lambda: ComputerControl.window_list()
        ))

        self.register(ToolDefinition(
            name="window_minimize",
            description="Minimizes specified window.",
            category="computer",
            risk_level="low",
            parameters={"target": {"type": "str"}},
            handler=lambda target: ComputerControl.window_minimize(target)
        ))

        self.register(ToolDefinition(
            name="window_maximize",
            description="Maximizes specified window.",
            category="computer",
            risk_level="low",
            parameters={"target": {"type": "str"}},
            handler=lambda target: ComputerControl.window_maximize(target)
        ))

        self.register(ToolDefinition(
            name="clipboard_read",
            description="Reads text currently copied to the Windows clipboard.",
            category="computer",
            risk_level="low",
            parameters={},
            handler=lambda: ComputerControl.clipboard_read()
        ))

        self.register(ToolDefinition(
            name="clipboard_write",
            description="Copies text to the Windows clipboard.",
            category="computer",
            risk_level="low",
            parameters={"text": {"type": "str"}},
            handler=lambda text: ComputerControl.clipboard_write(text)
        ))

        self.register(ToolDefinition(
            name="take_screenshot",
            description="Captures a high-resolution screenshot of the desktop screen.",
            category="computer",
            risk_level="low",
            parameters={"filename": {"type": "str", "optional": True}},
            handler=lambda filename=None: AssistantTools.take_screenshot(filename)
        ))

        # ── 2. Apps Tools ──────────────────────────
        self.register(ToolDefinition(
            name="open_app",
            description="Launches an installed application (Chrome, VS Code, Spotify, Notepad, Settings, etc.).",
            category="apps",
            risk_level="low",
            parameters={"app_name": {"type": "str"}},
            handler=lambda app_name: AssistantTools.open_application(app_name)
        ))

        self.register(ToolDefinition(
            name="close_app",
            description="Closes or terminates a running application by name.",
            category="apps",
            risk_level="medium",
            parameters={"app_name": {"type": "str"}},
            handler=lambda app_name: ComputerControl.app_close(app_name)
        ))

        # ── 3. Browser Tools ──────────────────────────
        self.register(ToolDefinition(
            name="open_url",
            description="Opens a URL in the user's default browser.",
            category="browser",
            risk_level="low",
            parameters={"url": {"type": "str"}},
            handler=lambda url: AssistantTools.open_url(url)
        ))

        self.register(ToolDefinition(
            name="web_search",
            description="Searches Google in the browser for a query.",
            category="browser",
            risk_level="low",
            parameters={"query": {"type": "str"}},
            handler=lambda query: AssistantTools.open_web_search(query)
        ))

        self.register(ToolDefinition(
            name="open_top_youtube_video",
            description="Searches YouTube and opens the top video for the query.",
            category="browser",
            risk_level="low",
            parameters={"query": {"type": "str", "optional": True}},
            handler=lambda query=None: AssistantTools.open_top_youtube_video(query)
        ))

        # ── 4. Files Tools ──────────────────────────
        self.register(ToolDefinition(
            name="read_file",
            description="Reads content from a local file on disk.",
            category="files",
            risk_level="low",
            parameters={"file_path": {"type": "str"}, "start_line": {"type": "int", "default": 1}, "end_line": {"type": "int", "optional": True}},
            handler=lambda file_path, start_line=1, end_line=None: AssistantTools.read_file(file_path, start_line, end_line)
        ))

        self.register(ToolDefinition(
            name="write_file",
            description="Creates or overwrites a file on disk.",
            category="files",
            risk_level="medium",
            parameters={"file_path": {"type": "str"}, "content": {"type": "str"}},
            handler=lambda file_path, content: AssistantTools.write_file(file_path, content)
        ))

        self.register(ToolDefinition(
            name="modify_file",
            description="Replaces target text within an existing file.",
            category="files",
            risk_level="medium",
            parameters={"file_path": {"type": "str"}, "search_text": {"type": "str"}, "replacement_text": {"type": "str"}},
            handler=lambda file_path, search_text, replacement_text: AssistantTools.modify_file(file_path, search_text, replacement_text)
        ))

        self.register(ToolDefinition(
            name="list_directory",
            description="Lists files and subdirectories in a directory path.",
            category="files",
            risk_level="low",
            parameters={"dir_path": {"type": "str", "default": "."}},
            handler=lambda dir_path=".": AssistantTools.list_directory(dir_path)
        ))

        self.register(ToolDefinition(
            name="search_files",
            description="Searches for files on disk by keyword and optional extension.",
            category="files",
            risk_level="low",
            parameters={"query": {"type": "str"}, "extension": {"type": "str", "optional": True}},
            handler=lambda query, extension=None: AssistantTools.search_files(query, extension)
        ))

        self.register(ToolDefinition(
            name="open_file",
            description="Opens a file with its default system application.",
            category="files",
            risk_level="low",
            parameters={"file_path": {"type": "str"}},
            handler=lambda file_path: AssistantTools.open_file(file_path)
        ))

        self.register(ToolDefinition(
            name="reveal_in_explorer",
            description="Reveals a file or folder in Windows File Explorer.",
            category="files",
            risk_level="low",
            parameters={"file_path": {"type": "str"}},
            handler=lambda file_path: AssistantTools.reveal_in_explorer(file_path)
        ))

        # ── 5. Terminal & Code Execution Tools ──────────
        self.register(ToolDefinition(
            name="run_python_code",
            description="Executes arbitrary Python code in a stateful persistent REPL session. Variables, imports, and state persist across calls (Open Interpreter LMC).",
            category="development",
            risk_level="medium",
            parameters={"code": {"type": "str"}, "timeout": {"type": "int", "default": 30}},
            handler=lambda code, timeout=30: AssistantTools.run_python_code(code, timeout=timeout)
        ))

        self.register(ToolDefinition(
            name="run_powershell_code",
            description="Executes arbitrary PowerShell script in a stateful persistent REPL session. Variables and state persist across calls.",
            category="terminal",
            risk_level="medium",
            parameters={"code": {"type": "str"}, "timeout": {"type": "int", "default": 30}},
            handler=lambda code, timeout=30: AssistantTools.run_powershell_code(code, timeout=timeout)
        ))

        self.register(ToolDefinition(
            name="run_command",
            description="Executes a PowerShell / shell command on the laptop with output capture.",
            category="terminal",
            risk_level="medium",
            parameters={"command": {"type": "str"}, "cwd": {"type": "str", "optional": True}, "timeout": {"type": "int", "default": 60}},
            handler=lambda command, cwd=None, timeout=60: AssistantTools.run_shell_command(command, cwd=cwd, timeout=timeout)
        ))

        # ── 6. System Tools ──────────────────────────
        self.register(ToolDefinition(
            name="set_volume",
            description="Adjusts system speaker volume (up, down, mute, or level 0-100).",
            category="system",
            risk_level="low",
            parameters={"action_or_level": {"type": "str"}},
            handler=lambda action_or_level: AssistantTools.set_volume(action_or_level)
        ))

        self.register(ToolDefinition(
            name="get_system_stats",
            description="Gets CPU, memory, disk, and battery statistics.",
            category="system",
            risk_level="low",
            parameters={},
            handler=lambda: AssistantTools.get_system_stats()
        ))

        # ── 7. Development Tools ──────────────────────────
        self.register(ToolDefinition(
            name="git_status",
            description="Checks git repository status.",
            category="development",
            risk_level="low",
            parameters={"cwd": {"type": "str", "optional": True}},
            handler=lambda cwd=None: AssistantTools.run_shell_command("git status -s", cwd=cwd)
        ))

        # ── 8. Media & Document Tools ──────────────────────────
        self.register(ToolDefinition(
            name="create_presentation",
            description="Generates a PowerPoint (.pptx) presentation.",
            category="media",
            risk_level="low",
            parameters={"topic": {"type": "str"}, "theme": {"type": "str", "default": "jarvis_dark"}},
            handler=lambda topic, theme="jarvis_dark": AssistantTools.create_presentation(topic, theme)
        ))

        self.register(ToolDefinition(
            name="create_document",
            description="Generates a Word (.docx) document.",
            category="media",
            risk_level="low",
            parameters={"title": {"type": "str"}, "theme": {"type": "str", "default": "executive"}},
            handler=lambda title, theme="executive": AssistantTools.create_document(title, theme)
        ))

        self.register(ToolDefinition(
            name="create_pdf",
            description="Generates a formatted PDF document.",
            category="media",
            risk_level="low",
            parameters={"title": {"type": "str"}, "theme": {"type": "str", "default": "modern_tech"}},
            handler=lambda title, theme="modern_tech": AssistantTools.create_pdf(title, theme)
        ))

        # ── 9. Vision & Screen Understanding Tools ──────────────
        self.register(ToolDefinition(
            name="inspect_screen",
            description="Captures screen and analyzes what is displayed using multimodal vision.",
            category="vision",
            risk_level="low",
            parameters={"query": {"type": "str", "default": "Describe what is on screen."}},
            handler=lambda query="Describe what is on screen.": AssistantTools.read_screen(query)
        ))

        from core.vision.screen_analyzer import ScreenAnalyzer
        _screen_analyzer = ScreenAnalyzer()

        self.register(ToolDefinition(
            name="click_ui_element",
            description="Uses vision AI to locate a visual button/icon/text on screen and clicks it.",
            category="vision",
            risk_level="low",
            parameters={"element_description": {"type": "str"}},
            handler=lambda element_description: _screen_analyzer.click_ui_element(element_description)
        ))
