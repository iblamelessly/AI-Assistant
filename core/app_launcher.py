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

    # Platforms that support deep search URLs (query appended to URL)
    SEARCHABLE_WEB_SERVICES = {
        "youtube":   "https://www.youtube.com/results?search_query={query}",
        "google":    "https://www.google.com/search?q={query}",
        "bing":      "https://www.bing.com/search?q={query}",
        "reddit":    "https://www.reddit.com/search/?q={query}",
        "github":    "https://github.com/search?q={query}",
        "amazon":    "https://www.amazon.com/s?k={query}",
        "linkedin":  "https://www.linkedin.com/search/results/all/?keywords={query}",
        "spotify":   "https://open.spotify.com/search/{query}",
        "twitter":   "https://twitter.com/search?q={query}",
        "x":         "https://x.com/search?q={query}",
        "instagram": "https://www.instagram.com/explore/search/?q={query}",
        "pinterest": "https://www.pinterest.com/search/pins/?q={query}",
        "stackoverflow": "https://stackoverflow.com/search?q={query}",
        "wikipedia": "https://en.wikipedia.org/wiki/Special:Search?search={query}",
        "flipkart":  "https://www.flipkart.com/search?q={query}",
        "myntra":    "https://www.myntra.com/{query}",
    }

    # Aliases for platform names in natural speech
    SEARCH_PLATFORM_ALIASES = {
        "you tube": "youtube",  "yt": "youtube",  "utube": "youtube",
        "goog": "google",  "googl": "google",
        "git hub": "github",  "gh": "github",
        "stack overflow": "stackoverflow",  "stackoverflow": "stackoverflow",  "stack": "stackoverflow",
        "wiki": "wikipedia",  "wikipedia": "wikipedia",
        "amz": "amazon",
        "insta": "instagram",
        "pinterest": "pinterest",  "pin": "pinterest",
        "twit": "twitter",  "tw": "twitter",
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
        "file manager": ["File Explorer"],
        "files": ["File Explorer"],
        "my files": ["File Explorer"],
        "explorer": ["File Explorer"],
        "file explorer": ["File Explorer"],
        "task manager": ["Task Manager"],
        "taskmgr": ["Task Manager"],
        "terminal": ["Windows Terminal", "Terminal", "PowerShell"],
        "powershell": ["PowerShell"],
        "cmd": ["Command Prompt"],
        "command prompt": ["Command Prompt"],
        "settings": ["Windows Settings"],
        "windows settings": ["Windows Settings"],
        "sound settings": ["Sound Settings"],
        "audio settings": ["Sound Settings"],
        "bluetooth settings": ["Bluetooth Settings"],
        "bluetooth": ["Bluetooth Settings"],
        "wifi settings": ["Wi-Fi Settings"],
        "wifi": ["Wi-Fi Settings"],
        "network settings": ["Network Settings"],
        "display settings": ["Display Settings"],
        "downloads": ["Downloads"],
        "documents": ["Documents"],
        "desktop": ["Desktop"],
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
        self.last_youtube_query = None

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
            "file manager": {"name": "File Explorer", "path": "explorer.exe", "type": "cmd"},
            "explorer": {"name": "File Explorer", "path": "explorer.exe", "type": "cmd"},
            "files": {"name": "File Explorer", "path": "explorer.exe", "type": "cmd"},
            "my files": {"name": "File Explorer", "path": "explorer.exe", "type": "cmd"},
            "task manager": {"name": "Task Manager", "path": "taskmgr.exe", "type": "cmd"},
            "taskmgr": {"name": "Task Manager", "path": "taskmgr.exe", "type": "cmd"},
            "windows settings": {"name": "Windows Settings", "path": "start ms-settings:", "type": "uri"},
            "settings": {"name": "Windows Settings", "path": "start ms-settings:", "type": "uri"},
            "microphone settings": {"name": "Microphone Settings", "path": "start ms-settings:privacy-microphone", "type": "uri"},
            "mic settings": {"name": "Microphone Settings", "path": "start ms-settings:privacy-microphone", "type": "uri"},
            "sound settings": {"name": "Sound Settings", "path": "start ms-settings:sound", "type": "uri"},
            "audio settings": {"name": "Sound Settings", "path": "start ms-settings:sound", "type": "uri"},
            "volume settings": {"name": "Sound Settings", "path": "start ms-settings:sound", "type": "uri"},
            "bluetooth settings": {"name": "Bluetooth Settings", "path": "start ms-settings:bluetooth", "type": "uri"},
            "bluetooth": {"name": "Bluetooth Settings", "path": "start ms-settings:bluetooth", "type": "uri"},
            "wifi settings": {"name": "Wi-Fi Settings", "path": "start ms-settings:network-wifi", "type": "uri"},
            "wifi": {"name": "Wi-Fi Settings", "path": "start ms-settings:network-wifi", "type": "uri"},
            "network settings": {"name": "Network Settings", "path": "start ms-settings:network", "type": "uri"},
            "display settings": {"name": "Display Settings", "path": "start ms-settings:display", "type": "uri"},
            "downloads": {"name": "Downloads", "path": str(Path.home() / "Downloads"), "type": "dir"},
            "documents": {"name": "Documents", "path": str(Path.home() / "Documents"), "type": "dir"},
            "desktop": {"name": "Desktop", "path": str(Path.home() / "Desktop"), "type": "dir"},
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

        # 0. Instant Fast-Path for Common Daily Applications (Zero filesystem lag, < 0.001s)
        COMMON_FAST_APPS = {
            "chrome": {"name": "Google Chrome", "path": "chrome.exe", "type": "cmd"},
            "google chrome": {"name": "Google Chrome", "path": "chrome.exe", "type": "cmd"},
            "edge": {"name": "Microsoft Edge", "path": "msedge.exe", "type": "cmd"},
            "msedge": {"name": "Microsoft Edge", "path": "msedge.exe", "type": "cmd"},
            "microsoft edge": {"name": "Microsoft Edge", "path": "msedge.exe", "type": "cmd"},
            "brave": {"name": "Brave Browser", "path": "brave.exe", "type": "cmd"},
            "firefox": {"name": "Mozilla Firefox", "path": "firefox.exe", "type": "cmd"},
            "notepad": {"name": "Notepad", "path": "notepad.exe", "type": "cmd"},
            "calc": {"name": "Calculator", "path": "calc.exe", "type": "cmd"},
            "calculator": {"name": "Calculator", "path": "calc.exe", "type": "cmd"},
            "file explorer": {"name": "File Explorer", "path": "explorer.exe", "type": "cmd"},
            "explorer": {"name": "File Explorer", "path": "explorer.exe", "type": "cmd"},
            "files": {"name": "File Explorer", "path": "explorer.exe", "type": "cmd"},
            "vscode": {"name": "Visual Studio Code", "path": "code.cmd", "type": "cmd"},
            "vs code": {"name": "Visual Studio Code", "path": "code.cmd", "type": "cmd"},
            "code": {"name": "Visual Studio Code", "path": "code.cmd", "type": "cmd"},
            "cmd": {"name": "Command Prompt", "path": "cmd.exe", "type": "cmd"},
            "command prompt": {"name": "Command Prompt", "path": "cmd.exe", "type": "cmd"},
            "terminal": {"name": "Windows Terminal", "path": "wt.exe", "type": "cmd"},
            "task manager": {"name": "Task Manager", "path": "taskmgr.exe", "type": "cmd"},
            "taskmgr": {"name": "Task Manager", "path": "taskmgr.exe", "type": "cmd"},
            "paint": {"name": "Paint", "path": "mspaint.exe", "type": "cmd"},
            "snipping tool": {"name": "Snipping Tool", "path": "snippingtool.exe", "type": "cmd"}
        }
        if q in COMMON_FAST_APPS:
            return {"status": "found", "app": COMMON_FAST_APPS[q]}

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

            if app_type == "dir":
                os.startfile(path)
                return {
                    "success": True,
                    "app": app_name,
                    "summary": f"Opened {app_name} folder in File Explorer."
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
                cmd_to_run = path if path.startswith("start ") else f'start "" "{path}"'
                subprocess.Popen(cmd_to_run, shell=True)
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

    def build_search_url(self, platform: str, query: str) -> str:
        """Builds a direct search URL for the given platform and query."""
        from urllib.parse import quote_plus
        p = platform.lower().strip()
        # Resolve aliases
        p = self.SEARCH_PLATFORM_ALIASES.get(p, p)
        url_template = self.SEARCHABLE_WEB_SERVICES.get(p)
        if not url_template:
            return ""
        return url_template.replace("{query}", quote_plus(query))

    def resolve_and_search(self, platform: str, query: str) -> dict:
        """
        Opens the given platform with the search query directly.
        Returns a result dict with success/summary.
        """
        from urllib.parse import quote_plus
        p = platform.lower().strip()
        # Resolve aliases
        p = self.SEARCH_PLATFORM_ALIASES.get(p, p)
        url_template = self.SEARCHABLE_WEB_SERVICES.get(p)
        if not url_template:
            return {
                "success": False,
                "summary": f"Platform '{platform}' does not support direct search.",
                "action": "web_search"
            }
        search_url = url_template.replace("{query}", quote_plus(query))
        if p == "youtube" and query:
            self.last_youtube_query = query.strip()
        try:
            webbrowser.open(search_url)
            platform_title = p.replace("_", " ").title()
            return {
                "success": True,
                "platform": platform_title,
                "query": query,
                "url": search_url,
                "action": "web_search",
                "summary": f"Searching **{platform_title}** for **\"{query}\"** — opened in browser."
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "summary": f"Failed to open search in {platform}: {e}"
            }

    def get_top_youtube_video(self, query: str = None) -> str | None:
        """Fetches the URL of the first video matching query on YouTube via fast HTML scraping."""
        try:
            import requests
            from urllib.parse import quote_plus
            target_q = (query or getattr(self, "last_youtube_query", None) or "").strip()
            if not target_q:
                return None
            search_url = f"https://www.youtube.com/results?search_query={quote_plus(target_q)}"
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            r = requests.get(search_url, headers=headers, timeout=5)
            if r.status_code == 200:
                vids = []
                for vid in re.findall(r'/watch\?v=([a-zA-Z0-9_-]{11})', r.text):
                    if vid not in vids:
                        vids.append(vid)
                if vids:
                    return f"https://www.youtube.com/watch?v={vids[0]}"
        except Exception as e:
            print(f"[AppLauncher] Error extracting top YouTube video: {e}")
        return None

    def open_top_youtube_video(self, query: str = None) -> dict:
        """Opens the first video matching query (or the last searched YouTube query) directly in browser."""
        target_q = (query or getattr(self, "last_youtube_query", None) or "").strip()
        if not target_q:
            target_q = "trending"
        top_url = self.get_top_youtube_video(target_q)
        if top_url:
            self.last_youtube_query = target_q
            try:
                webbrowser.open(top_url)
                return {
                    "success": True,
                    "url": top_url,
                    "query": target_q,
                    "action": "open_url",
                    "summary": f"Opening the first YouTube video for **\"{target_q}\"** in your browser."
                }
            except Exception as e:
                return {"success": False, "error": str(e), "summary": f"Failed to open video: {e}"}
        else:
            return self.resolve_and_search("youtube", target_q)

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
