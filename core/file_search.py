import os
import re
import time
import difflib
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional

class FileSearchEngine:
    """
    High-performance Windows file and folder searcher and launcher for Jarvis.
    Features:
    - Lightning-fast scoped recursive search (<0.3s) across active projects, Desktop, Documents, Downloads.
    - Safe directory pruning (skips node_modules, .git, AppData, venv, system folders).
    - Intelligent file extension recognition (e.g. 'python file' -> .py, 'word doc' -> .docx).
    - Case-insensitive, stem, substring, and fuzzy matching with difflib.
    - Ambiguity and doubt detection: asks user for clarification with suggestions if multiple files match.
    - Opens files in default registered applications, opens folders in File Explorer, or reveals files highlighted.
    """

    # Common directory names to skip during recursive scan for speed and security
    IGNORED_DIRS = {
        "node_modules", ".git", "__pycache__", "venv", ".venv", "env", ".env",
        "appdata", "application data", "local settings", "temp", "tmp",
        ".vscode", ".idea", ".pytest_cache", ".mypy_cache", "site-packages",
        "dist", "build", ".next", ".nuxt", "$recycle.bin", "system volume information",
        "windows", "program files", "program files (x86)"
    }

    # Friendly aliases for file types and extensions
    TYPE_EXTENSIONS = {
        "python": [".py", ".pyw"],
        "py": [".py"],
        "script": [".py", ".bat", ".ps1", ".sh", ".js"],
        "javascript": [".js", ".jsx", ".mjs"],
        "typescript": [".ts", ".tsx"],
        "html": [".html", ".htm"],
        "css": [".css", ".scss"],
        "json": [".json"],
        "text": [".txt", ".md", ".log"],
        "txt": [".txt"],
        "markdown": [".md"],
        "pdf": [".pdf"],
        "word": [".docx", ".doc"],
        "doc": [".docx", ".doc"],
        "excel": [".xlsx", ".xls", ".csv"],
        "spreadsheet": [".xlsx", ".xls", ".csv"],
        "csv": [".csv"],
        "powerpoint": [".pptx", ".ppt"],
        "ppt": [".pptx", ".ppt"],
        "image": [".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg"],
        "picture": [".png", ".jpg", ".jpeg", ".gif", ".webp"],
        "photo": [".png", ".jpg", ".jpeg", ".webp"],
        "video": [".mp4", ".mkv", ".avi", ".mov", ".wmv", ".webm"],
        "movie": [".mp4", ".mkv", ".avi", ".mov"],
        "audio": [".mp3", ".wav", ".m4a", ".flac", ".aac", ".ogg"],
        "sound": [".mp3", ".wav", ".m4a"],
        "song": [".mp3", ".wav", ".m4a", ".flac"],
        "music": [".mp3", ".wav", ".m4a", ".flac"],
        "zip": [".zip", ".rar", ".7z", ".tar", ".gz"],
        "archive": [".zip", ".rar", ".7z", ".tar", ".gz"]
    }

    # Standard Windows user folders
    FOLDER_ALIASES = {
        "downloads": "Downloads",
        "download": "Downloads",
        "desktop": "Desktop",
        "documents": "Documents",
        "document": "Documents",
        "docs": "Documents",
        "pictures": "Pictures",
        "photos": "Pictures",
        "videos": "Videos",
        "movies": "Videos",
        "music": "Music",
        "songs": "Music",
        "home": ""
    }

    def __init__(self):
        self.pending_file_selection: Optional[Dict[str, Any]] = None

    def get_search_roots(self) -> List[Path]:
        """Gathers key user roots for fast searching without crawling full C:\\ drive."""
        user_home = Path(os.environ.get("USERPROFILE", Path.home()))
        roots = []

        # 1. Current working directory & workspace
        try:
            cwd = Path.cwd()
            roots.append(cwd)
            if cwd.parent and cwd.parent.exists() and cwd.parent != user_home:
                roots.append(cwd.parent)
        except Exception:
            pass

        # 2. Desktop (both standard and OneDrive)
        for d in [user_home / "OneDrive" / "Desktop", user_home / "Desktop"]:
            if d.exists() and d not in roots:
                roots.append(d)

        # 3. Documents
        for d in [user_home / "OneDrive" / "Documents", user_home / "Documents"]:
            if d.exists() and d not in roots:
                roots.append(d)

        # 4. Downloads
        dl = user_home / "Downloads"
        if dl.exists() and dl not in roots:
            roots.append(dl)

        # 5. Media Folders
        for media_dir in ["Pictures", "Videos", "Music"]:
            for d in [user_home / "OneDrive" / media_dir, user_home / media_dir]:
                if d.exists() and d not in roots:
                    roots.append(d)

        # 6. Top-level user folders (e.g. Projects, Code, Repos)
        try:
            for item in user_home.iterdir():
                if item.is_dir() and not item.name.startswith(".") and item.name.lower() not in self.IGNORED_DIRS:
                    if item not in roots:
                        roots.append(item)
        except Exception:
            pass

        # Return deduplicated valid roots
        seen = set()
        deduped = []
        for r in roots:
            try:
                real_r = r.resolve()
                if real_r not in seen and real_r.exists():
                    seen.add(real_r)
                    deduped.append(real_r)
            except Exception:
                continue

        return deduped

    def parse_query(self, raw_query: str) -> Dict[str, Any]:
        """
        Parses user's file or folder query, determining intent (search/open),
        mode (file/folder/any), target name, and target file extensions.
        """
        q = raw_query.strip()
        q_lower = q.lower()

        # Clean conversational prefixes
        q_clean = re.sub(r"^(?:hey\s+)?(?:jarvis,?\s*)?", "", q_lower, flags=re.IGNORECASE)
        q_clean = re.sub(r"^(?:please\s+|can\s+you\s+|could\s+you\s+|kindly\s+)?", "", q_clean, flags=re.IGNORECASE)

        action = "search"
        if re.search(r"^(?:open|launch|run|bring\s+up|show|view)\b", q_clean):
            action = "open"
        elif re.search(r"^(?:reveal|locate|where\s+is)\b", q_clean):
            action = "reveal"

        # Remove action verbs
        q_clean = re.sub(r"^(?:open|launch|run|bring\s+up|show|view|find|search\s+for|search|look\s+for|locate|where\s+is)\s+", "", q_clean, flags=re.IGNORECASE).strip()

        # Remove "my" / "the" / "a"
        q_clean = re.sub(r"^(?:my|the|a|an)\s+", "", q_clean, flags=re.IGNORECASE).strip()

        # Check if user specifically requested a folder
        is_folder = False
        if "folder" in q_clean or "directory" in q_clean or "dir" in q_clean:
            is_folder = True
            q_clean = re.sub(r"\b(?:folder|directory|dir)\b", "", q_clean).strip()

        # 1. Detect explicit dot extension (e.g. "main.py", "resume.pdf")
        target_exts = []
        dot_ext_match = re.search(r"\.([a-zA-Z0-9]+)$", q_clean)
        if dot_ext_match:
            explicit_ext = f".{dot_ext_match.group(1).lower()}"
            target_exts.append(explicit_ext)

        # 2. Detect and strip natural language file type / extension in query (e.g. "python file", "word doc")
        for type_name, exts in self.TYPE_EXTENSIONS.items():
            pattern = r"\b" + re.escape(type_name) + r"(?:\s+(?:files?|documents?|scripts?|presentations?|sheets?|data))?\b"
            if re.search(pattern, q_clean):
                if not target_exts:
                    target_exts.extend(exts)
                subbed = re.sub(pattern, "", q_clean).strip()
                if subbed:
                    q_clean = subbed
                break

        q_clean = q_clean.strip(" '\"`.")
        if q_clean in ["files", "file", "all files", "scripts", "script", "docs", "doc"]:
            q_clean = ""

        return {
            "action": action,
            "is_folder": is_folder,
            "target": q_clean,
            "extensions": target_exts,
            "raw": raw_query
        }

    def search_files(
        self,
        query: str,
        extensions: Optional[List[str]] = None,
        roots: Optional[List[Path]] = None,
        max_results: int = 6,
        depth: int = 4
    ) -> List[Dict[str, Any]]:
        """
        Recursively searches for files matching query and optional extensions.
        Uses intelligent ranking: exact match > stem match > startswith > substring > fuzzy.
        """
        search_roots = roots if roots else self.get_search_roots()
        q = query.lower().strip()
        matches = []
        seen_paths = set()

        # Normalize extensions
        ext_set = set(e.lower() for e in extensions) if extensions else None

        for root in search_roots:
            if not root.exists():
                continue

            for parent, dirs, files in os.walk(str(root)):
                # Prune noisy directories in place
                dirs[:] = [
                    d for d in dirs
                    if d.lower() not in self.IGNORED_DIRS and not d.startswith(".")
                ]

                # Check depth
                try:
                    rel_parts = Path(parent).relative_to(root).parts
                    if len(rel_parts) >= depth:
                        dirs.clear()
                except Exception:
                    pass

                for f in files:
                    f_lower = f.lower()
                    f_path = os.path.join(parent, f)

                    # Check extension filter if supplied
                    if ext_set:
                        _, f_ext = os.path.splitext(f_lower)
                        if f_ext not in ext_set:
                            continue

                    # Normalized realpath deduplication
                    real_p = os.path.normcase(os.path.realpath(f_path))
                    if real_p in seen_paths:
                        continue

                    stem_lower = Path(f).stem.lower()

                    # Scoring logic
                    score = 0
                    if not q:
                        # User just asked for e.g. "python files" without a specific name
                        score = 50
                    elif f_lower == q:
                        score = 100 # Exact full filename match
                    elif stem_lower == q:
                        score = 95  # Exact stem match (e.g. 'main' == 'main.py')
                    elif stem_lower.startswith(q):
                        score = 80  # Stem starts with query
                    elif q in stem_lower:
                        score = 70  # Query inside stem
                    elif q in f_lower:
                        score = 65  # Query inside full filename
                    else:
                        # Fuzzy match check
                        ratio = difflib.SequenceMatcher(None, q, stem_lower).ratio()
                        if ratio >= 0.70:
                            score = int(ratio * 70)

                    if score > 0:
                        seen_paths.add(real_p)
                        try:
                            st = os.stat(f_path)
                            size_kb = round(st.st_size / 1024, 1)
                            mtime = st.st_mtime
                            # Small recency boost for recently modified files (last 7 days)
                            if (time.time() - mtime) < 7 * 86400:
                                score += 5
                        except Exception:
                            size_kb = 0
                            mtime = 0

                        # Determine friendly parent directory name for display
                        parent_path = Path(parent)
                        display_parent = parent_path.name if parent_path.name else str(parent_path)

                        matches.append({
                            "name": f,
                            "path": f_path,
                            "parent": display_parent,
                            "full_parent": str(parent_path),
                            "display": f"{f} (in {display_parent})",
                            "size_kb": size_kb,
                            "mtime": mtime,
                            "score": score
                        })

        # Sort matches by score descending, then by modification time descending
        matches.sort(key=lambda m: (m["score"], m["mtime"]), reverse=True)
        return matches[:max_results]

    def search_folders(
        self,
        query: str,
        roots: Optional[List[Path]] = None,
        max_results: int = 5,
        depth: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Searches for directories/folders matching the query across user roots.
        """
        q = query.lower().strip()
        search_roots = roots if roots else self.get_search_roots()
        matches = []
        seen_paths = set()

        # Check standard user folder aliases first
        if q in self.FOLDER_ALIASES:
            alias_name = self.FOLDER_ALIASES[q]
            user_home = Path(os.environ.get("USERPROFILE", Path.home()))
            candidates = [
                user_home / "OneDrive" / alias_name,
                user_home / alias_name
            ]
            for cand in candidates:
                if cand.exists():
                    real_p = os.path.normcase(os.path.realpath(str(cand)))
                    if real_p not in seen_paths:
                        seen_paths.add(real_p)
                        matches.append({
                            "name": cand.name,
                            "path": str(cand),
                            "parent": cand.parent.name,
                            "display": f"{cand.name} ({cand.parent.name})",
                            "score": 100
                        })
                        return matches

        for root in search_roots:
            if not root.exists():
                continue

            # Check if root itself matches
            if q and (root.name.lower() == q or q in root.name.lower()):
                real_p = os.path.normcase(os.path.realpath(str(root)))
                if real_p not in seen_paths:
                    seen_paths.add(real_p)
                    matches.append({
                        "name": root.name,
                        "path": str(root),
                        "parent": root.parent.name,
                        "display": f"{root.name} ({root.parent.name})",
                        "score": 95 if root.name.lower() == q else 75
                    })

            for parent, dirs, files in os.walk(str(root)):
                dirs[:] = [
                    d for d in dirs
                    if d.lower() not in self.IGNORED_DIRS and not d.startswith(".")
                ]

                try:
                    rel_parts = Path(parent).relative_to(root).parts
                    if len(rel_parts) >= depth:
                        dirs.clear()
                except Exception:
                    pass

                for d in dirs:
                    d_lower = d.lower()
                    d_path = os.path.join(parent, d)
                    real_p = os.path.normcase(os.path.realpath(d_path))
                    if real_p in seen_paths:
                        continue

                    score = 0
                    if d_lower == q:
                        score = 100
                    elif d_lower.startswith(q):
                        score = 80
                    elif q in d_lower:
                        score = 70
                    else:
                        ratio = difflib.SequenceMatcher(None, q, d_lower).ratio()
                        if ratio >= 0.75:
                            score = int(ratio * 70)

                    if score > 0:
                        seen_paths.add(real_p)
                        parent_name = Path(parent).name
                        matches.append({
                            "name": d,
                            "path": d_path,
                            "parent": parent_name,
                            "display": f"{d} (in {parent_name})",
                            "score": score
                        })

        matches.sort(key=lambda m: m["score"], reverse=True)
        return matches[:max_results]

    def open_file(self, file_path: str) -> Dict[str, Any]:
        """Opens a local file in its default registered Windows application."""
        p = Path(file_path).expanduser().resolve()
        if not p.exists() or not p.is_file():
            return {"success": False, "error": f"File not found: {file_path}", "summary": f"Could not find file: {file_path}"}

        try:
            os.startfile(str(p))
            return {
                "success": True,
                "path": str(p),
                "name": p.name,
                "summary": f"Opened file **{p.name}** in its default application."
            }
        except Exception as e:
            try:
                subprocess.Popen(f'start "" "{p}"', shell=True)
                return {
                    "success": True,
                    "path": str(p),
                    "name": p.name,
                    "summary": f"Opened file **{p.name}**."
                }
            except Exception as e2:
                return {
                    "success": False,
                    "error": str(e2),
                    "summary": f"Failed to open file {p.name}: {e2}"
                }

    def open_folder(self, folder_path: str) -> Dict[str, Any]:
        """Opens a local directory in Windows File Explorer."""
        p = Path(folder_path).expanduser().resolve()
        if not p.exists() or not p.is_dir():
            return {"success": False, "error": f"Folder not found: {folder_path}", "summary": f"Could not find folder: {folder_path}"}

        try:
            os.startfile(str(p))
            return {
                "success": True,
                "path": str(p),
                "name": p.name,
                "summary": f"Opened folder **{p.name}** in File Explorer."
            }
        except Exception as e:
            try:
                subprocess.Popen(["explorer.exe", str(p)])
                return {
                    "success": True,
                    "path": str(p),
                    "name": p.name,
                    "summary": f"Opened folder **{p.name}** in File Explorer."
                }
            except Exception as e2:
                return {
                    "success": False,
                    "error": str(e2),
                    "summary": f"Failed to open folder {p.name}: {e2}"
                }

    def reveal_in_explorer(self, file_path: str) -> Dict[str, Any]:
        """Opens File Explorer with the specific file selected/highlighted."""
        p = Path(file_path).expanduser().resolve()
        if not p.exists():
            return {"success": False, "error": f"Path not found: {file_path}", "summary": f"Path not found: {file_path}"}

        try:
            subprocess.Popen(f'explorer.exe /select,"{p}"')
            return {
                "success": True,
                "path": str(p),
                "name": p.name,
                "summary": f"Revealed **{p.name}** in File Explorer."
            }
        except Exception as e:
            return {"success": False, "error": str(e), "summary": f"Failed to reveal in Explorer: {e}"}

    def resolve_and_handle(self, raw_query: str) -> Dict[str, Any]:
        """
        Unified resolution method:
        1. Parses intent, target name, and extensions.
        2. Executes folder or file search.
        3. If exactly 1 match: opens or reveals based on intent.
        4. If multiple matches: returns 'doubt' status with candidates for user selection.
        5. If no matches: returns 'not_found' status.
        """
        parsed = self.parse_query(raw_query)
        target = parsed["target"]
        action = parsed["action"]
        is_folder = parsed["is_folder"]
        extensions = parsed["extensions"]

        if not target and not extensions and not is_folder:
            return {"status": "not_found", "query": raw_query, "summary": "Empty file or folder target specified."}

        # 1. Search folders if requested or if target matches folder aliases
        if is_folder or (target.lower() in self.FOLDER_ALIASES and not extensions):
            folder_matches = self.search_folders(target)
            if len(folder_matches) == 1:
                chosen = folder_matches[0]
                if action in ["open", "reveal"]:
                    res = self.open_folder(chosen["path"])
                    res["matched"] = chosen
                    return {"status": "found", "type": "folder", "match": chosen, "action_result": res}
                else:
                    return {
                        "status": "found",
                        "type": "folder",
                        "match": chosen,
                        "summary": f"Found folder **{chosen['name']}** at `{chosen['path']}`."
                    }
            elif len(folder_matches) > 1:
                self.pending_file_selection = {
                    "query": target,
                    "action": action,
                    "type": "folder",
                    "matches": folder_matches
                }
                return {
                    "status": "doubt",
                    "query": target,
                    "type": "folder",
                    "matches": folder_matches,
                    "summary": f"Found multiple folders matching '{target}'."
                }

        # 2. Search files
        file_matches = self.search_files(query=target, extensions=extensions)

        # If no files found and not explicitly marked as file, try folders as fallback
        if not file_matches and not is_folder and not extensions:
            folder_matches = self.search_folders(target)
            if len(folder_matches) == 1:
                chosen = folder_matches[0]
                res = self.open_folder(chosen["path"])
                return {"status": "found", "type": "folder", "match": chosen, "action_result": res}
            elif len(folder_matches) > 1:
                self.pending_file_selection = {
                    "query": target,
                    "action": action,
                    "type": "folder",
                    "matches": folder_matches
                }
                return {
                    "status": "doubt",
                    "query": target,
                    "type": "folder",
                    "matches": folder_matches,
                    "summary": f"Found multiple folders matching '{target}'."
                }

        if len(file_matches) == 1:
            chosen = file_matches[0]
            if action == "open":
                res = self.open_file(chosen["path"])
                return {"status": "found", "type": "file", "match": chosen, "action_result": res}
            elif action == "reveal":
                res = self.reveal_in_explorer(chosen["path"])
                return {"status": "found", "type": "file", "match": chosen, "action_result": res}
            else:
                return {
                    "status": "found",
                    "type": "file",
                    "match": chosen,
                    "summary": f"Found file **{chosen['name']}** at `{chosen['path']}` (Size: {chosen['size_kb']} KB)."
                }

        elif len(file_matches) > 1:
            # Check if there is a single decisive exact match with score >= 100 while others are lower
            if file_matches[0]["score"] == 100 and file_matches[1]["score"] < 95 and action == "open":
                chosen = file_matches[0]
                res = self.open_file(chosen["path"])
                return {"status": "found", "type": "file", "match": chosen, "action_result": res}

            self.pending_file_selection = {
                "query": target if target else (extensions[0] if extensions else "file"),
                "action": action,
                "type": "file",
                "matches": file_matches
            }
            return {
                "status": "doubt",
                "query": target if target else "files",
                "type": "file",
                "matches": file_matches,
                "summary": f"Found multiple files matching '{target}'."
            }

        return {
            "status": "not_found",
            "query": target or raw_query,
            "summary": f"Could not find any file or folder matching '{target or raw_query}'."
        }

    def evaluate_selection_reply(self, reply: str) -> Optional[Dict[str, Any]]:
        """
        Evaluates user's choice when replying to a file or folder doubt.
        Supports:
        - Digits ("1", "2")
        - Ordinals ("first", "second", "1st")
        - Path / folder name clues ("desktop", "ai-assistant")
        - Exact or partial filename
        - Cancellation ("cancel", "no", "stop")
        """
        if not self.pending_file_selection:
            return None

        matches = self.pending_file_selection.get("matches", [])
        action = self.pending_file_selection.get("action", "open")
        sel_type = self.pending_file_selection.get("type", "file")

        if not matches:
            self.pending_file_selection = None
            return None

        r = reply.lower().strip()

        # Cancellation
        if r in ["cancel", "no", "stop", "nevermind", "exit", "neither", "none", "don't open"]:
            self.pending_file_selection = None
            return {"status": "cancel", "summary": "Operation cancelled, sir."}

        chosen_match = None

        # 1. Digits: "1", "2", "3"
        digit_match = re.search(r"\b([1-9])\b", r)
        if digit_match:
            idx = int(digit_match.group(1)) - 1
            if 0 <= idx < len(matches):
                chosen_match = matches[idx]

        # 2. Ordinals: "first", "second", "third"
        if not chosen_match:
            ordinals = {"first": 0, "second": 1, "third": 2, "fourth": 3, "fifth": 4, "1st": 0, "2nd": 1, "3rd": 2}
            for word, idx in ordinals.items():
                if word in r and idx < len(matches):
                    chosen_match = matches[idx]
                    break

        # 3. Matching by parent folder name or full path substring
        if not chosen_match:
            for m in matches:
                p_lower = m["path"].lower()
                parent_lower = m["parent"].lower()
                name_lower = m["name"].lower()

                if parent_lower in r or name_lower in r or r in p_lower:
                    chosen_match = m
                    break

        # 4. Matching chip format e.g. "1. AI-Assistant/main.py"
        if not chosen_match:
            for i, m in enumerate(matches):
                chip_txt = f"{i+1}. {m['parent']}/{m['name']}".lower()
                if chip_txt in r or m["display"].lower() in r:
                    chosen_match = m
                    break

        if chosen_match:
            self.pending_file_selection = None
            target_path = chosen_match["path"]

            if sel_type == "folder":
                action_res = self.open_folder(target_path)
            elif action == "reveal":
                action_res = self.reveal_in_explorer(target_path)
            else:
                action_res = self.open_file(target_path)

            return {
                "status": "selected",
                "match": chosen_match,
                "action_result": action_res
            }

        return None

# Global singleton
file_search_engine = FileSearchEngine()
