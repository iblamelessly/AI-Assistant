"""
Task Planner for JARVIS Autonomous Agent.
Decomposes complex, multi-step natural language user requests into
structured execution plans with tools, parameters, and verification requirements.
"""

import json
import re
from typing import List, Dict, Any, Optional

class TaskStep:
    def __init__(self,
                 step_id: int,
                 description: str,
                 tool: str,
                 params: Dict[str, Any],
                 verification: Optional[str] = None):
        self.step_id = step_id
        self.description = description
        self.tool = tool
        self.params = params
        self.verification = verification

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "description": self.description,
            "tool": self.tool,
            "params": self.params,
            "verification": self.verification
        }


class TaskPlan:
    def __init__(self, goal: str, is_multi_step: bool, steps: List[TaskStep]):
        self.goal = goal
        self.is_multi_step = is_multi_step
        self.steps = steps

    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal": self.goal,
            "is_multi_step": self.is_multi_step,
            "steps": [s.to_dict() for s in self.steps]
        }


class TaskPlanner:
    """Decomposes user commands into actionable step-by-step plans."""

    def __init__(self, tool_registry=None, groq_client=None, gemini_client=None):
        self.tool_registry = tool_registry
        self.groq_client = groq_client
        self.gemini_client = gemini_client

    def plan_task(self, user_goal: str, system_context: str = "") -> TaskPlan:
        """
        Plans execution for user goal.
        Uses fast heuristic decomposition for common workflows (Chrome + Search + Video,
        Project Setup, Volume, Screenshots), and falls back to LLM-guided planning for novel multi-step requests.
        """
        clean_goal = user_goal.strip()

        # Fast path heuristics
        heuristic_plan = self._try_heuristic_plan(clean_goal)
        if heuristic_plan:
            return heuristic_plan

        # LLM-assisted task decomposition
        llm_plan = self._llm_plan(clean_goal, system_context)
        if llm_plan:
            return llm_plan

        # Fallback single step
        return TaskPlan(
            goal=clean_goal,
            is_multi_step=False,
            steps=[
                TaskStep(
                    step_id=1,
                    description=f"Execute: {clean_goal}",
                    tool="run_command" if clean_goal.startswith(("$", "dir", "ls")) else "web_search",
                    params={"query": clean_goal} if not clean_goal.startswith(("$", "dir", "ls")) else {"command": clean_goal},
                    verification="execution_completed"
                )
            ]
        )

    def _try_heuristic_plan(self, goal: str) -> Optional[TaskPlan]:
        """Recognizes multi-step patterns like 'open chrome, search for X, open the first result'."""
        g = goal.lower()

        # Pattern: Chrome + Search + Open first video/link
        # e.g.: "open chrome, search for Python courses, open the first useful result"
        if ("open chrome" in g or "launch chrome" in g) and ("search" in g or "find" in g):
            # Extract query
            search_query = ""
            m = re.search(r"search\s+(?:for\s+)?([^,]+?)(?:,|\s+and\s+open|\s+and\s+tell|\s+and\s+play|$)", g, re.IGNORECASE)
            if m:
                search_query = m.group(1).strip()
            if not search_query:
                search_query = "latest news"

            steps = [
                TaskStep(1, "Open Google Chrome", "open_app", {"app_name": "chrome"}, verification="app_running:chrome"),
                TaskStep(2, f"Search web for '{search_query}'", "web_search", {"query": search_query}, verification="browser_navigated")
            ]

            if any(term in g for term in ["first result", "first video", "first link", "top video", "top result"]):
                if "youtube" in g or "video" in g:
                    steps.append(TaskStep(3, f"Open top video for '{search_query}'", "open_top_youtube_video", {"query": search_query}, verification="browser_navigated"))

            return TaskPlan(goal=goal, is_multi_step=True, steps=steps)

        # Pattern: YouTube direct query + first video
        if "youtube" in g and any(t in g for t in ["first", "top", "play", "open"]):
            qm = re.search(r"(?:search|play|find|open)\s+(?:for\s+)?([^,]+?)(?:on\s+youtube|in\s+youtube|$)", g)
            query = qm.group(1).strip() if qm else None
            return TaskPlan(
                goal=goal,
                is_multi_step=True,
                steps=[
                    TaskStep(1, f"Search YouTube and open top video for '{query or 'trending'}'", "open_top_youtube_video", {"query": query}, verification="browser_navigated")
                ]
            )

        # Pattern: Project creation (directories + file + launch VS Code)
        # e.g.: "create a data analyst project folder, make a script, open it in VS Code"
        if ("create" in g or "make" in g) and ("project" in g or "folder" in g) and ("vs code" in g or "vscode" in g or "code" in g):
            proj_name = "data_project"
            if "analyst" in g or "analysis" in g:
                proj_name = "data_analyst_project"
            elif "python" in g:
                proj_name = "python_project"

            return TaskPlan(
                goal=goal,
                is_multi_step=True,
                steps=[
                    TaskStep(1, f"Create project directory '{proj_name}'", "run_command", {"command": f"New-Item -ItemType Directory -Force -Path '{proj_name}'"}, verification="directory_exists"),
                    TaskStep(2, f"Create starter script in '{proj_name}'", "write_file", {"file_path": f"{proj_name}/main.py", "content": "# Autonomous starter script created by JARVIS\nprint('Project ready.')\n"}, verification="file_exists"),
                    TaskStep(3, f"Open project in VS Code", "open_app", {"app_name": "code"}, verification="app_running:code")
                ]
            )

        return None

    def _llm_plan(self, goal: str, context: str = "") -> Optional[TaskPlan]:
        """Uses fast Groq LLM to decompose arbitrary multi-step computer tasks into JSON steps."""
        if not self.groq_client or not self.groq_client.is_configured():
            return None

        tools_desc = self.tool_registry.get_tools_prompt() if self.tool_registry else ""

        prompt = f"""You are the JARVIS Autonomous Planning Engine.
User Goal: "{goal}"
Context: {context}

{tools_desc}

Analyze the user goal.
If it is a simple single-action request, respond with a 1-step plan.
If it requires multiple computer actions, break it down into sequential steps (maximum 6 steps).
Every step MUST use one of the available tools.

Return ONLY a valid JSON object with this exact structure:
{{
  "is_multi_step": true/false,
  "steps": [
    {{
      "step_id": 1,
      "description": "Short description of action",
      "tool": "registered_tool_name",
      "params": {{"param_name": "value"}},
      "verification": "app_running:name" OR "file_exists" OR "browser_navigated" OR "success"
    }}
  ]
}}
Do NOT output markdown fences or other text. Only raw JSON."""

        try:
            chunks = []
            res = self.groq_client.stream_chat(
                messages=[{"role": "user", "content": prompt}],
                on_chunk=lambda c: chunks.append(c),
                temperature=0.1,
                max_tokens=600,
                model_override="llama-3.3-70b-versatile",
                emit_errors=False
            )
            raw = "".join(chunks).strip()
            # Clean JSON markdown fences if present
            raw = re.sub(r"^```json\s*", "", raw, flags=re.IGNORECASE)
            raw = re.sub(r"^```\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw).strip()

            parsed = json.loads(raw)
            raw_steps = parsed.get("steps", [])
            steps = []
            for s in raw_steps:
                steps.append(TaskStep(
                    step_id=int(s.get("step_id", len(steps) + 1)),
                    description=s.get("description", "Execute step"),
                    tool=s.get("tool", "run_command"),
                    params=s.get("params", {}),
                    verification=s.get("verification")
                ))

            if steps:
                return TaskPlan(
                    goal=goal,
                    is_multi_step=bool(parsed.get("is_multi_step", len(steps) > 1)),
                    steps=steps
                )
        except Exception as e:
            print(f"[TaskPlanner] LLM decomposition error: {e}")

        return None
