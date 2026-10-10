import re
import os
from pathlib import Path

class PermissionGuard:
    """
    Human-like permission, confirmation, and ambiguity guard for Jarvis.
    Ensures Jarvis never performs destructive actions or accesses personal
    data without explicit human-like confirmation and clarification.
    """

    DESTRUCTIVE_PATTERNS = [
        r"\b(?:rm|del|delete|remove|erase|wipe|unlink|drop|destroy)\b",
        r"\bgit\s+(?:reset\s+--hard|clean\s+-f|checkout\s+\.|branch\s+-D|push\s+--force)\b",
        r"\btaskkill\b|\bkill\b",
        r"\bformat\b|\bshutil\.rmtree\b"
    ]

    PERSONAL_DATA_KEYWORDS = [
        "my name", "my career", "career goal", "my education", "my degree",
        "who am i", "my personal data", "my profile", "my skills", "what do you know about me"
    ]

    def __init__(self, require_destructive_confirm=True, require_privacy_confirm=True):
        self.require_destructive_confirm = require_destructive_confirm
        self.require_privacy_confirm = require_privacy_confirm
        self.pending_confirmation = None

    def has_pending(self) -> bool:
        return self.pending_confirmation is not None

    def get_pending(self) -> dict:
        return self.pending_confirmation

    def clear_pending(self):
        self.pending_confirmation = None

    def is_destructive_command(self, command: str) -> bool:
        """Checks if a terminal command or action is potentially destructive."""
        cmd = command.lower().strip()
        for pattern in self.DESTRUCTIVE_PATTERNS:
            if re.search(pattern, cmd):
                return True
        return False

    def is_personal_data_query(self, text: str) -> bool:
        """Checks if the query requests sensitive personal memory details."""
        lower = text.lower().strip()
        return any(k in lower for k in self.PERSONAL_DATA_KEYWORDS)

    def detect_ambiguity_or_duplicates(self, user_message: str, target_name: str = None) -> str:
        """
        Checks if a deletion or modification target has duplicates (e.g. backup, copy, original)
        and crafts an intelligent human-like clarifying question.
        """
        lower = user_message.lower()

        # If user asks to delete something without specifying which copy
        if any(w in lower for w in ["delete", "remove", "erase", "trash"]):
            # Check local directory for duplicate/backup files
            if target_name:
                base = Path(target_name).stem
                cwd = Path(os.getcwd())
                candidates = list(cwd.glob(f"*{base}*"))
                if len(candidates) > 1:
                    names = [c.name for c in candidates]
                    return (
                        f"Sir, I found multiple matching files ({', '.join(names)}). "
                        "To be safe: do you want me to delete the original file, the backup/duplicate copy, or cancel?"
                    )

            # General human-like clarification on generic deletion
            if not any(w in lower for w in ["original", "backup", "duplicate", "copy", "both", "all"]):
                return (
                    "Before I delete anything, sir: could you specify whether you mean the original file, "
                    "a duplicate/backup copy, or should I list what matches first?"
                )

        return None

    def inspect_action(self, tool_name: str, *args) -> dict:
        """
        Inspects an upcoming autonomous tool call.
        Returns {'requires_approval': True, 'question': '...', 'action_info': ...} if permission needed.
        """
        if not self.require_destructive_confirm:
            return {"requires_approval": False}

        t = tool_name.lower().strip()
        arg0 = args[0] if len(args) > 0 else ""

        # Shell command safety check
        if t in ["run_command", "run_shell_command"]:
            # High-risk: shutdown / restart / formatting
            if re.search(r"\b(?:shutdown|restart-computer|stop-computer|diskpart|format\s+[a-z]:)\b", str(arg0).lower()):
                question = f"🛑 HIGH RISK ACTION: You are about to execute a system command (`{arg0}`). This will reboot, shutdown, or alter disk partitions! Confirm explicitly? [Yes / No]"
                self.pending_confirmation = {
                    "tool": tool_name,
                    "args": args,
                    "question": question
                }
                return {"requires_approval": True, "question": question, "action_info": arg0}

            if self.is_destructive_command(arg0):
                question = f"⚠️ Confirmation required, sir: You are about to run a destructive command (`{arg0}`). Proceed? [Yes / No]"
                self.pending_confirmation = {
                    "tool": tool_name,
                    "args": args,
                    "question": question
                }
                return {"requires_approval": True, "question": question, "action_info": arg0}

        # Process termination safety check
        if t in ["kill_process", "kill", "close_app"]:
            question = f"⚠️ Caution: Are you sure you want me to terminate process '{arg0}'? [Yes / No]"
            self.pending_confirmation = {
                "tool": tool_name,
                "args": args,
                "question": question
            }
            return {"requires_approval": True, "question": question, "action_info": f"Kill {arg0}"}

        # File write over existing file check
        if t in ["write_file", "create_file"]:
            target_file = Path(arg0)
            if target_file.exists() and target_file.stat().st_size > 0:
                question = f"⚠️ File '{target_file.name}' already exists on disk. Do you want to overwrite the original or keep a backup? [Overwrite / Cancel]"
                self.pending_confirmation = {
                    "tool": tool_name,
                    "args": args,
                    "question": question
                }
                return {"requires_approval": True, "question": question, "action_info": f"Overwrite {target_file.name}"}

        return {"requires_approval": False}

    def evaluate_user_reply(self, reply: str) -> dict:
        """
        Evaluates user's response to a pending confirmation.
        Returns {'confirmed': True/False, 'action': ..., 'clarification': ...}
        """
        if not self.pending_confirmation:
            return {"has_pending": False}

        clean = reply.lower().strip()
        positive_tokens = ["yes", "y", "proceed", "sure", "do it", "confirm", "go ahead", "overwrite", "original", "yes proceed"]
        negative_tokens = ["no", "n", "cancel", "abort", "stop", "don't", "dont", "nevermind"]

        if any(token == clean or clean.startswith(token) for token in positive_tokens):
            action_data = self.pending_confirmation
            self.clear_pending()
            return {"has_pending": True, "confirmed": True, "action": action_data}
        elif any(token == clean or clean.startswith(token) for token in negative_tokens):
            self.clear_pending()
            return {"has_pending": True, "confirmed": False, "message": "Operation cancelled as requested, sir."}
        else:
            return {
                "has_pending": True,
                "confirmed": None,
                "clarification": f"Please reply 'Yes' to proceed, or 'No' to cancel: {self.pending_confirmation['question']}"
            }
