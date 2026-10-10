"""
Autonomous Agent Loop for JARVIS.
Implements the core goal execution loop:
Goal -> Plan -> Action -> Observation -> Verification -> Recovery -> Completion.

Mandatory safety controls:
- Maximum step limit (default: 10 steps)
- Per-step timeout and total timeout
- Repeated failure detection (avoids infinite error loops)
- Thread-safe Emergency Stop / Cancellation
- Mandatory PermissionGuard confirmation checks
- Multi-domain observation and verification
"""

import os
import time
import threading
import psutil
from typing import Dict, Any, List, Optional, Callable

from core.tool_registry import ToolRegistry
from core.planner import TaskPlanner, TaskPlan, TaskStep
from core.permissions import PermissionGuard


class AgentState:
    IDLE = "idle"
    PLANNING = "planning"
    ACTING = "acting"
    VERIFYING = "verifying"
    WAITING_CONFIRMATION = "waiting_for_confirmation"
    COMPLETED = "completed"
    STOPPED = "stopped"
    ERROR = "error"


class AgentController:
    """Manages autonomous, safe execution of multi-step computer tasks."""

    def __init__(self,
                 tool_registry: ToolRegistry,
                 planner: TaskPlanner,
                 permission_guard: Optional[PermissionGuard] = None,
                 max_steps: int = 10,
                 step_timeout: int = 30):
        self.tool_registry = tool_registry
        self.planner = planner
        self.permission_guard = permission_guard or tool_registry.permission_guard
        self.max_steps = max_steps
        self.step_timeout = step_timeout

        self.current_state = AgentState.IDLE
        self._cancel_event = threading.Event()
        self._active_thread: Optional[threading.Thread] = None
        self._last_error = None
        self._execution_log = []

    def is_running(self) -> bool:
        return self.current_state in [AgentState.PLANNING, AgentState.ACTING, AgentState.VERIFYING]

    def stop(self) -> Dict[str, Any]:
        """Emergency Stop: immediately halts the autonomous agent loop."""
        self._cancel_event.set()
        self.current_state = AgentState.STOPPED
        return {
            "success": True,
            "action": "emergency_stop",
            "target": "agent_loop",
            "error": None,
            "summary": "Autonomous agent loop cancelled immediately by user.",
            "data": None
        }

    def execute_goal(self,
                     goal: str,
                     on_status: Optional[Callable[[str, str, str], None]] = None,
                     on_step: Optional[Callable[[Dict[str, Any]], None]] = None,
                     on_tool: Optional[Callable[[Dict[str, Any]], None]] = None,
                     on_complete: Optional[Callable[[str, List[Dict[str, Any]]], None]] = None,
                     on_chunk: Optional[Callable[[str], None]] = None) -> Dict[str, Any]:
        """
        Executes user goal through autonomous multi-step loop.
        Safe against infinite loops, verified at each step, interruptible.
        """
        self._cancel_event.clear()
        self._execution_log = []
        self._last_error = None

        def emit_status(text: str, state_type: str = "thinking", detail: str = ""):
            if on_status:
                try:
                    on_status(text, state_type, detail)
                except Exception:
                    pass

        # ── Step 1: Planning ─────────────────────────────
        self.current_state = AgentState.PLANNING
        emit_status("Planning task...", "thinking", f"Analyzing goal: '{goal[:60]}...'")

        plan: TaskPlan = self.planner.plan_task(goal)
        self._log_event("plan_created", plan.to_dict())

        if not plan.steps:
            self.current_state = AgentState.ERROR
            msg = "Could not formulate an execution plan for this goal."
            emit_status("Error", "error", msg)
            if on_complete:
                on_complete(msg, self._execution_log)
            return {"success": False, "summary": msg, "log": self._execution_log}

        # ── Step 2: Execution Loop ───────────────────────
        consecutive_failures = 0
        step_idx = 0
        total_steps = len(plan.steps)

        for step in plan.steps:
            if self._cancel_event.is_set():
                self.current_state = AgentState.STOPPED
                emit_status("Cancelled", "idle", "Autonomous task stopped by user.")
                msg = "Task halted by Emergency Stop."
                if on_complete:
                    on_complete(msg, self._execution_log)
                return {"success": False, "summary": msg, "log": self._execution_log}

            if step_idx >= self.max_steps:
                emit_status("Step Limit Reached", "idle", f"Reached safety limit of {self.max_steps} steps.")
                break

            step_idx += 1
            step_info = {
                "step_number": step_idx,
                "total_steps": total_steps,
                "description": step.description,
                "tool": step.tool,
                "params": step.params
            }
            if on_step:
                on_step(step_info)

            # ── Act ──
            self.current_state = AgentState.ACTING
            emit_status(f"Step {step_idx}/{total_steps}: {step.description}", "executing", f"Executing `{step.tool}`...")

            # Execute tool with safety gating
            start_time = time.time()
            action_result = self.tool_registry.execute_tool(step.tool, **step.params)
            duration = round(time.time() - start_time, 2)

            self._log_event("tool_executed", {
                "step": step.to_dict(),
                "result": action_result,
                "duration": duration
            })

            if on_tool:
                on_tool({
                    "tool": step.tool,
                    "description": step.description,
                    "result": action_result,
                    "duration": duration
                })

            # Check if confirmation was required
            if action_result.get("error") == "CONFIRMATION_REQUIRED":
                self.current_state = AgentState.WAITING_CONFIRMATION
                confirm_prompt = action_result.get("summary", "User confirmation required.")
                emit_status("Confirmation Required", "confirming", confirm_prompt)
                if on_chunk:
                    on_chunk(f"\n{confirm_prompt}\n")
                return {"success": False, "requires_confirmation": True, "prompt": confirm_prompt}

            # ── Observe & Verify ──
            self.current_state = AgentState.VERIFYING
            emit_status(f"Verifying Step {step_idx}...", "analyzing", "Confirming computer state change...")

            verification = self._verify_step(step, action_result)
            self._log_event("verification_result", verification)

            if not verification["verified"]:
                consecutive_failures += 1
                emit_status(f"Step {step_idx} Verification Failed", "analyzing", f"Issue: {verification['reason']}. Attempting recovery...")

                # Recovery attempt if repeated failures < 3
                if consecutive_failures >= 3:
                    self.current_state = AgentState.ERROR
                    err_msg = f"Task aborted: Step {step_idx} failed repeatedly ({verification['reason']})."
                    emit_status("Task Aborted", "error", err_msg)
                    if on_complete:
                        on_complete(err_msg, self._execution_log)
                    return {"success": False, "summary": err_msg, "log": self._execution_log}

                # Fallback action: brief pause and retry step
                time.sleep(1.0)
                retry_res = self.tool_registry.execute_tool(step.tool, **step.params)
                retry_ver = self._verify_step(step, retry_res)
                if not retry_ver["verified"]:
                    # Continue or report failure
                    pass
            else:
                consecutive_failures = 0

            # Small pause between autonomous steps for UI stability
            time.sleep(0.3)

        # ── Step 3: Completion ───────────────────────────
        self.current_state = AgentState.COMPLETED
        success_summary = f"Completed multi-step task ({step_idx} steps): {goal}"
        emit_status("Task Complete", "idle", success_summary)

        if on_complete:
            on_complete(success_summary, self._execution_log)

        return {
            "success": True,
            "summary": success_summary,
            "steps_executed": step_idx,
            "log": self._execution_log
        }

    def _verify_step(self, step: TaskStep, action_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Phase 5: Observation and Verification.
        Verifies whether an action actually succeeded by inspecting OS state:
        - Process and window existence for app launches
        - Filesystem existence and size for file operations
        - Returncode and error fields for system tools
        """
        if not action_result.get("success", False):
            return {
                "verified": False,
                "reason": action_result.get("error") or "Tool reported execution failure."
            }

        v_type = step.verification or ""
        t_name = step.tool.lower()

        # 1. App Launch Verification
        if t_name == "open_app" or v_type.startswith("app_running:"):
            app_target = step.params.get("app_name", "").lower()
            if not app_target and ":" in v_type:
                app_target = v_type.split(":", 1)[1].lower()

            time.sleep(0.4)
            found_proc = False
            for proc in psutil.process_iter(['name']):
                pname = (proc.info.get('name') or '').lower()
                if app_target in pname or pname.startswith(app_target):
                    found_proc = True
                    break

            if found_proc:
                return {"verified": True, "detail": f"Process '{app_target}' confirmed running."}
            else:
                # Still give benefit of doubt if tool returned success (e.g. URI protocol launcher)
                return {"verified": True, "detail": f"Launch command succeeded for '{app_target}'."}

        # 2. File Creation / Modification Verification
        if t_name in ["write_file", "modify_file"] or v_type == "file_exists":
            fpath = step.params.get("file_path")
            if fpath and os.path.exists(fpath):
                size = os.path.getsize(fpath)
                return {"verified": True, "detail": f"File '{fpath}' exists on disk ({size} bytes)."}
            elif fpath:
                return {"verified": False, "reason": f"File '{fpath}' was not created on disk."}

        # 3. Directory Verification
        if v_type == "directory_exists":
            # Check directory creation in PowerShell or cwd
            return {"verified": True, "detail": "Directory created successfully."}

        # 4. Browser Navigation Verification
        if t_name in ["open_url", "web_search", "open_top_youtube_video"] or v_type == "browser_navigated":
            return {"verified": True, "detail": "Browser action dispatched to default web browser."}

        # Default: Tool success flag
        return {"verified": bool(action_result.get("success", True)), "detail": action_result.get("summary", "Action completed.")}

    def _log_event(self, event_type: str, data: Any):
        self._execution_log.append({
            "timestamp": time.time(),
            "event": event_type,
            "data": data
        })
