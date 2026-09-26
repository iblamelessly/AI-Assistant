import os
import sys
import re
import time
import winreg
import difflib
import subprocess
import webbrowser
from pathlib import Path

class AppLauncher:
    """
    Intelligent application scanner, searcher, and launcher for Windows.
    Features:
    - Case-insensitive, fuzzy, and alias matching for all installed Windows apps.
    - Scans Start Menu (.lnk), Desktops, LocalAppData, and Registry App Paths.
    - Disambiguation and human-like doubt handling when multiple apps match.
    - Fallback suggestion to open web apps/services if not installed locally.
    """

    WEB_SERVICES = {
        "netflix": "https://www.netflix.com",
        "youtube": "https://www.youtube.com",
        "whatsapp": "https://web.whatsapp.com",
        "instagram": "https://www.instagram.com",
        "twitter": "https://x.com",
        "x": "https://x.com",
        "reddit": "https://www.reddit.com",
        "linkedin": "https://www.linkedin.com",
        "gmail": "https://mail.google.com",
        "amazon": "https://www.amazon.com",
        "chatgpt": "https://chatgpt.com",
        "gemini": "https://gemini.google.com",
        "github": "https://github.com",
        "spotify": "https://open.spotify.com",
        "facebook": "https://www.facebook.com",
        "canva": "https://www.canva.com",
        "figma": "https://www.figma.com",
        "notion": "https://www.notion.so"
    }

    APP_ALIASES = {
        "chrome": ["Google Chrome", "chrome"],
        "google chrome": ["Google Chrome"],
        "browser": ["Google Chrome", "Microsoft Edge"],
        "internet": ["Google Chrome", "Microsoft Edge"],
        "edge": ["Microsoft Edge", "msedge"],
        "microsoft edge": ["Microsoft Edge"],
        "vscode": ["Visual Studio Code", "Code"],
        "vs code": ["Visual Studio Code"],
        "code": ["Visual Studio Code"],
        "visual studio code": ["Visual Studio Code"],
        "chatgpt": ["ChatGPT"],
        "chat gpt": ["ChatGPT"],
        "gemini": ["Google Gemini"],
        "google gemini": ["Google Gemini"],
        "telegram": ["Telegram"],
        "telegram desktop": ["Telegram"],
        "steam": ["Steam"],
        "roblox": ["Roblox Player", "Roblox Studio"],
        "roblox player": ["Roblox Player"],
        "roblox studio": ["Roblox Studio"],
        "groww": ["Groww"],
        "netmirror": ["Netmirror"],
        "github desktop": ["GitHub Desktop"],
        "git bash": ["Git Bash"],
        "git gui": ["Git GUI"],
        "notepad": ["Notepad"],
        "notes": ["Notepad"],
        "calc": ["Calculator"],
        "calculator": ["Calculator"],
        "paint": ["Paint"],
        "mspaint": ["Paint"],
        "files": ["File Explorer"],
        "explorer": ["File Explorer"],
        "file explorer": ["File Explorer"],
        "task manager": ["Task Manager"],
        "taskmgr": ["Task Manager"],
        "terminal": ["Windows Terminal", "Terminal", "PowerShell"],
        "powershell": ["PowerShell"],
        "cmd": ["Command Prompt"],
        "command prompt": ["Command Prompt"],
        "settings": ["Windows Settings"],
        "control panel": ["Control Panel"],
        "word": ["Word"],
        "excel": ["Excel"],
        "powerpoint": ["PowerPoint"],
        "teams": ["Microsoft Teams"],
        "spotify": ["Spotify"],
        "vlc": ["VLC media player"]
    }

    def __init__(self):
        self._apps_cache = {}
        self._last_scan_time = 0
        self.pending_app_selection = None
        self.pending_web_suggestion = None

    def get_installed_apps(self, force_refresh: bool = False) -> dict:
        """Returns cached installed applications, refreshing if older than 5 minutes."""
        now = time.time()
        if not self._apps_cache or force_refresh or (now - self._last_scan_time > 300):
            self._apps_cache = self.scan_installed_apps()
            self._last_scan_time = now
        return self._apps_cache

    def scan_installed_apps(self) -> dict:
        """Thoroughly scans Windows for all desktop shortcuts, programs, and registry paths."""
        apps = {}

        # 1. Start Menu & Desktop Folders
        scan_dirs = [
            Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
            Path(os.environ.get("PROGRAMDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
            Path(os.environ.get("USERPROFILE", "")) / "Desktop",
            Path(os.environ.get("USERPROFILE", "")) / "OneDrive" / "Desktop",
            Path("C:/Users/Public/Desktop"),
            Path(os.environ.get("LOCALAPPDATA", "")) / "Programs"
        ]

        ignored_keywords = ["uninstall", "help", "readme", "documentation", "release notes", "manual", "install"]

        for d in scan_dirs:
            if d.exists():
                try:
                    for p in d.rglob("*.lnk"):
                        stem = p.stem.strip()
                        stem_lower = stem.lower()
                        if stem and not any(ign in stem_lower for ign in ignored_keywords):
                            if stem_lower not in apps:
                                apps[stem_lower] = {
                                    "name": stem,
                                    "path": str(p),
                                    "type": "lnk"
                                }
                except Exception:
                    pass

        # 2. Registry App Paths
        for root in [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]:
            try:
                with winreg.OpenKey(root, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths") as key:
                    for i in range(winreg.QueryInfoKey(key)[0]):
                        try:
                            sub = winreg.EnumKey(key, i)
                            with winreg.OpenKey(key, sub) as sk:
                                val, _ = winreg.QueryValueEx(sk, "")
                                if val and os.path.exists(val):
                                    stem = Path(sub).stem.strip()
                                    stem_lower = stem.lower()
                                    if stem_lower not in apps:
                                        apps[stem_lower] = {
                                            "name": stem,
                                            "path": val,
                                            "type": "exe"
                                        }
                        except Exception:
                            pass
            except Exception:
                pass

        # 3. Built-in Windows System Utilities
        system_tools = {
            "notepad": {"name": "Notepad", "path": "notepad.exe", "type": "cmd"},
            "calculator": {"name": "Calculator", "path": "calc.exe", "type": "cmd"},
            "calc": {"name": "Calculator", "path": "calc.exe", "type": "cmd"},
            "file explorer": {"name": "File Explorer", "path": "explorer.exe", "type": "cmd"},
            "explorer": {"name": "File Explorer", "path": "explorer.exe", "type": "cmd"},
            "task manager": {"name": "Task Manager", "path": "taskmgr.exe", "type": "cmd"},
            "taskmgr": {"name": "Task Manager", "path": "taskmgr.exe", "type": "cmd"},
            "windows settings": {"name": "Windows Settings", "path": "start ms-settings:", "type": "uri"},
            "settings": {"name": "Windows Settings", "path": "start ms-settings:", "type": "uri"},
            "paint": {"name": "Paint", "path": "mspaint.exe", "type": "cmd"},
            "mspaint": {"name": "Paint", "path": "mspaint.exe", "type": "cmd"},
            "snipping tool": {"name": "Snipping Tool", "path": "snippingtool.exe", "type": "cmd"},
            "command prompt": {"name": "Command Prompt", "path": "cmd.exe", "type": "cmd"},
            "cmd": {"name": "Command Prompt", "path": "cmd.exe", "type": "cmd"},
            "powershell": {"name": "PowerShell", "path": "powershell.exe", "type": "cmd"},
            "windows terminal": {"name": "Windows Terminal", "path": "wt.exe", "type": "cmd"},
            "terminal": {"name": "Windows Terminal", "path": "wt.exe", "type": "cmd"},
            "control panel": {"name": "Control Panel", "path": "control.exe", "type": "cmd"}
        }

        for k, v in system_tools.items():
            if k not in apps:
                apps[k] = v

        return apps

    def find_app(self, raw_query: str) -> dict:
        """
        Intelligently resolves application query using:
        1. Query cleanup (case normalization, removing polite prefixes)
        2. Alias resolution
        3. Substring matching with ambiguity detection
        4. Fuzzy matching with difflib
        5. Web service fallback suggestion
        """
        # Clean query
        q = raw_query.strip().lower()
        q = re.sub(r"^(?:hey\s+)?(?:jarvis,?\s*)?", "", q)
        q = re.sub(r"^(?:please\s+|can\s+you\s+|could\s+you\s+|kindly\s+)?", "", q)
        q = re.sub(r"^(?:open|launch|start|run|bring\s+up|show)\s+(?:the\s+|an\s+|a\s+)?", "", q)
        q = re.sub(r"\s+app(?:lication)?$", "", q).strip()

        if not q:
            return {"status": "not_found", "query": raw_query}

        apps = self.get_installed_apps()

        # 1. Exact match in installed apps (case-insensitive)
        if q in apps:
            return {"status": "found", "app": apps[q]}

        # 2. Check Aliases
        if q in self.APP_ALIASES:
            alias_targets = self.APP_ALIASES[q]
            matching_from_alias = []
            for target_name in alias_targets:
                target_lower = target_name.lower()
                if target_lower in apps:
                    matching_from_alias.append(apps[target_lower])
                else:
                    # Check substring match for alias target
                    for k, v in apps.items():
                        if target_lower in k or k in target_lower:
                            if v not in matching_from_alias:
                                matching_from_alias.append(v)

            if len(matching_from_alias) == 1:
                return {"status": "found", "app": matching_from_alias[0]}
            elif len(matching_from_alias) > 1:
                return {
                    "status": "doubt",
                    "query": q,
                    "matches": [a["name"] for a in matching_from_alias[:4]]
                }

        # 3. Substring matches across installed apps
        substring_matches = []
        exact_word_matches = []

        for k, v in apps.items():
            if q in k:
                substring_matches.append(v)
                if re.search(r"\b" + re.escape(q) + r"\b", k):
                    exact_word_matches.append(v)

        target_pool = exact_word_matches if exact_word_matches else substring_matches

        if len(target_pool) == 1:
            return {"status": "found", "app": target_pool[0]}
        elif len(target_pool) > 1:
            # Multiple apps match! Ask for clarification
            names = []
            for a in target_pool:
                if a["name"] not in names:
                    names.append(a["name"])
            return {
                "status": "doubt",
                "query": q,
                "matches": names[:4]
            }

        # 4. Fuzzy matching via difflib
        app_keys = list(apps.keys())
        close_keys = difflib.get_close_matches(q, app_keys, n=3, cutoff=0.55)

        if len(close_keys) == 1:
            return {"status": "found", "app": apps[close_keys[0]]}
        elif len(close_keys) > 1:
            return {
                "status": "doubt",
                "query": q,
                "matches": [apps[k]["name"] for k in close_keys]
            }

        # 5. Check if query is a well-known web service (Fallback suggestion)
        for ws_name, ws_url in self.WEB_SERVICES.items():
            if ws_name in q or q in ws_name:
                return {
                    "status": "web_suggestion",
                    "name": ws_name.title(),
                    "url": ws_url,
                    "query": q
                }

        return {"status": "not_found", "query": q}

    def launch(self, app_info: dict) -> dict:
        """Launches the specified application cleanly on Windows."""
        try:
            app_name = app_info.get("name", "Application")
            path = app_info.get("path", "")
            app_type = app_info.get("type", "")

            if app_type == "uri":
                if path.startswith("start "):
                    subprocess.Popen(path, shell=True)
                else:
                    os.startfile(path)
                return {
                    "success": True,
                    "app": app_name,
                    "summary": f"Launched {app_name}."
                }

            if app_type in ["lnk", "exe"]:
                if os.path.exists(path):
                    os.startfile(path)
                    return {
                        "success": True,
                        "app": app_name,
                        "summary": f"Launched {app_name}."
                    }
                else:
                    # Try system start
                    subprocess.Popen(f'start "" "{path}"', shell=True)
                    return {
                        "success": True,
                        "app": app_name,
                        "summary": f"Launched {app_name}."
                    }

            if app_type == "cmd":
                subprocess.Popen(path, shell=True)
                return {
                    "success": True,
                    "app": app_name,
                    "summary": f"Launched {app_name}."
                }

            # Generic fallback
            os.startfile(path)
            return {"success": True, "app": app_name, "summary": f"Launched {app_name}."}

        except Exception as e:
            # Fallback to shell start
            try:
                subprocess.Popen(f'start "" "{app_info.get("path", "")}"', shell=True)
                return {"success": True, "app": app_info.get("name", "App"), "summary": f"Launched {app_info.get('name')}."}
            except Exception as e2:
                return {"success": False, "error": str(e), "summary": f"Failed to launch {app_info.get('name')}: {e}"}

    def resolve_and_launch(self, raw_query: str) -> dict:
        """
        Primary interface:
        - Resolves query to found app, doubt, web suggestion, or not found.
        - Launches app immediately if found without ambiguity.
        """
        resolution = self.find_app(raw_query)
        status = resolution.get("status")

        if status == "found":
            app = resolution["app"]
            launch_res = self.launch(app)
            launch_res["matched_app"] = app["name"]
            return launch_res

        elif status == "doubt":
            self.pending_app_selection = {
                "query": resolution["query"],
                "matches": resolution["matches"]
            }
            return {
                "success": False,
                "doubt": True,
                "query": resolution["query"],
                "matches": resolution["matches"],
                "summary": f"Multiple applications found for '{resolution['query']}'."
            }

        elif status == "web_suggestion":
            self.pending_web_suggestion = {
                "name": resolution["name"],
                "url": resolution["url"]
            }
            return {
                "success": False,
                "web_suggestion": True,
                "name": resolution["name"],
                "url": resolution["url"],
                "summary": f"'{resolution['name']}' not found locally. Web version available."
            }

        else:
            return {
                "success": False,
                "not_found": True,
                "query": resolution.get("query", raw_query),
                "summary": f"Could not find application '{raw_query}' on this laptop."
            }

    def evaluate_selection_reply(self, reply: str) -> str | None:
        """
        Evaluates user's choice when replying to an app doubt.
        Supports digits ("1", "2"), ordinals ("first", "second"), or partial names.
        """
        if not self.pending_app_selection:
            return None

        matches = self.pending_app_selection.get("matches", [])
        if not matches:
            return None

        r = reply.lower().strip()

        # Cancellation
        if r in ["cancel", "no", "stop", "nevermind", "exit", "neither", "none"]:
            self.pending_app_selection = None
            return "CANCEL"

        # Digits: "1", "2", "3"
        digit_match = re.search(r"\b([1-9])\b", r)
        if digit_match:
            idx = int(digit_match.group(1)) - 1
            if 0 <= idx < len(matches):
                chosen = matches[idx]
                self.pending_app_selection = None
                return chosen

        # Ordinals
        ordinals = {"first": 0, "second": 1, "third": 2, "fourth": 3, "1st": 0, "2nd": 1, "3rd": 2}
        for word, idx in ordinals.items():
            if word in r and idx < len(matches):
                chosen = matches[idx]
                self.pending_app_selection = None
                return chosen

        # Substring / partial name matching against choices
        for m in matches:
            if m.lower() in r or r in m.lower():
                self.pending_app_selection = None
                return m
            for part in m.lower().split():
                if len(part) > 2 and part in r:
                    self.pending_app_selection = None
                    return m

        return None

    def evaluate_web_reply(self, reply: str) -> str | None:
        """Evaluates user reply to open web app suggestion."""
        if not self.pending_web_suggestion:
            return None

        r = reply.lower().strip()
        url = self.pending_web_suggestion.get("url")
        name = self.pending_web_suggestion.get("name")

        if any(w in r for w in ["yes", "open", "browser", "sure", "ok", "go ahead", "please"]):
            self.pending_web_suggestion = None
            try:
                webbrowser.open(url)
                return f"Opened {name} in your default browser."
            except Exception as e:
                return f"Failed to open browser: {e}"

        if any(w in r for w in ["no", "cancel", "stop", "nevermind", "don't"]):
            self.pending_web_suggestion = None
            return "CANCEL"

        return None

# Global singleton
app_launcher = AppLauncher()
