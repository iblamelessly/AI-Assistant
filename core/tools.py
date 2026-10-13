import os
import re
import subprocess
import webbrowser
import datetime
import shutil
import psutil
import ctypes
import time
from pathlib import Path

# Common Windows application shortcuts and commands
APP_COMMANDS = {
    "notepad": "notepad.exe",
    "notes": "notepad.exe",
    "calc": "calc.exe",
    "calculator": "calc.exe",
    "chrome": "start chrome",
    "google chrome": "start chrome",
    "edge": "start msedge",
    "microsoft edge": "start msedge",
    "spotify": "start spotify:",
    "vscode": "code",
    "vs code": "code",
    "visual studio code": "code",
    "terminal": "wt.exe",
    "powershell": "powershell.exe",
    "cmd": "cmd.exe",
    "command prompt": "cmd.exe",
    "explorer": "explorer.exe",
    "file explorer": "explorer.exe",
    "task manager": "taskmgr.exe",
    "taskmgr": "taskmgr.exe",
    "settings": "start ms-settings:",
    "word": "start winword",
    "excel": "start excel",
    "paint": "mspaint.exe",
}

# Windows Virtual-Key Codes for Volume Control
VK_VOLUME_MUTE = 0xAD
VK_VOLUME_DOWN = 0xAE
VK_VOLUME_UP   = 0xAF

class AssistantTools:
    """Executes full laptop and system automation tools for Jarvis AI Assistant."""

    _python_repl = None
    _powershell_repl = None

    @classmethod
    def get_python_repl(cls):
        """Returns or creates the stateful Python REPL instance."""
        if cls._python_repl is None or not cls._python_repl.is_alive():
            from core.repl_executor import PersistentREPL
            cls._python_repl = PersistentREPL(lang="python", timeout=30)
        return cls._python_repl

    @classmethod
    def get_powershell_repl(cls):
        """Returns or creates the stateful PowerShell REPL instance."""
        if cls._powershell_repl is None or not cls._powershell_repl.is_alive():
            from core.repl_executor import PersistentREPL
            cls._powershell_repl = PersistentREPL(lang="powershell", timeout=30)
        return cls._powershell_repl

    @classmethod
    def run_python_code(cls, code: str, timeout: int = 30) -> dict:
        """
        Executes arbitrary Python code in a stateful persistent REPL session (Open Interpreter LMC).
        Variables, functions, imports, and directory changes persist across calls.
        """
        if not code or not code.strip():
            return {"success": False, "error": "Empty code snippet provided"}
        try:
            repl = cls.get_python_repl()
            res = repl.execute(code, timeout=timeout)
            out = res.get("stdout", "").strip()
            err = res.get("stderr", "").strip()
            is_ok = res.get("success", False)
            summary = out or err or "Python code executed successfully with no output."
            return {
                "success": is_ok,
                "stdout": out,
                "stderr": err,
                "returncode": res.get("returncode", 0),
                "summary": f"Python Output:\n{summary}" if is_ok else f"Python Error:\n{err or summary}"
            }
        except Exception as e:
            return {"success": False, "error": str(e), "summary": f"Python REPL error: {e}"}

    @classmethod
    def run_powershell_code(cls, code: str, timeout: int = 30) -> dict:
        """
        Executes arbitrary PowerShell script in a stateful persistent REPL session.
        Variables, functions, and working directory state persist across calls.
        """
        if not code or not code.strip():
            return {"success": False, "error": "Empty PowerShell snippet provided"}
        try:
            repl = cls.get_powershell_repl()
            res = repl.execute(code, timeout=timeout)
            out = res.get("stdout", "").strip()
            err = res.get("stderr", "").strip()
            is_ok = res.get("success", False)
            summary = out or err or "PowerShell script executed successfully with no output."
            return {
                "success": is_ok,
                "stdout": out,
                "stderr": err,
                "returncode": res.get("returncode", 0),
                "summary": f"PowerShell Output:\n{summary}" if is_ok else f"PowerShell Error:\n{err or summary}"
            }
        except Exception as e:
            return {"success": False, "error": str(e), "summary": f"PowerShell REPL error: {e}"}

    @staticmethod
    def run_shell_command(command: str, cwd: str = None, timeout: int = 60) -> dict:
        """
        Executes a shell or PowerShell command on the laptop and captures output.
        Full access to git, python, file operations, system commands.
        """
        if not command or not command.strip():
            return {"success": False, "error": "Empty command provided"}

        command = command.strip()
        working_dir = cwd if cwd and os.path.exists(cwd) else os.getcwd()

        try:
            process = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
                capture_output=True,
                text=True,
                cwd=working_dir,
                timeout=timeout
            )

            stdout = process.stdout.strip()
            stderr = process.stderr.strip()

            # Limit output to prevent overwhelming model context
            max_len = 5000
            if len(stdout) > max_len:
                stdout = stdout[:max_len] + f"\n... [Output truncated. Total characters: {len(process.stdout)}]"
            if len(stderr) > max_len:
                stderr = stderr[:max_len] + f"\n... [Stderr truncated]"

            is_success = (process.returncode == 0)
            summary_msg = f"Command exited with code {process.returncode}."
            if stdout:
                summary_msg += f"\nOutput:\n{stdout}"
            if stderr:
                summary_msg += f"\nErrors:\n{stderr}"

            return {
                "success": is_success,
                "command": command,
                "exit_code": process.returncode,
                "stdout": stdout,
                "stderr": stderr,
                "summary": summary_msg
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "command": command,
                "error": f"Command timed out after {timeout} seconds.",
                "summary": f"Command timed out after {timeout}s: {command}"
            }
        except Exception as e:
            return {
                "success": False,
                "command": command,
                "error": str(e),
                "summary": f"Execution failed: {e}"
            }

    @staticmethod
    def read_file(file_path: str, start_line: int = 1, end_line: int = None) -> dict:
        """Reads content from a local file on the laptop."""
        try:
            path = Path(file_path).expanduser().resolve()
            if not path.exists():
                return {"success": False, "error": f"File not found: {path}", "summary": f"File not found: {path}"}

            with open(path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()

            total_lines = len(lines)
            s = max(1, int(start_line)) - 1
            e = min(total_lines, int(end_line)) if end_line else total_lines

            content = "".join(lines[s:e])
            return {
                "success": True,
                "path": str(path),
                "total_lines": total_lines,
                "content": content,
                "summary": f"Read {path.name} (lines {s+1}-{e} of {total_lines}):\n{content[:2000]}"
            }
        except Exception as e:
            return {"success": False, "error": str(e), "summary": f"Failed to read file: {e}"}

    @staticmethod
    def write_file(file_path: str, content: str) -> dict:
        """Creates or overwrites a file on the laptop."""
        try:
            path = Path(file_path).expanduser().resolve()
            path.parent.mkdir(parents=True, exist_ok=True)

            with open(path, "w", encoding="utf-8") as f:
                f.write(content)

            return {
                "success": True,
                "path": str(path),
                "bytes_written": len(content.encode("utf-8")),
                "summary": f"Successfully created/updated file: {path}"
            }
        except Exception as e:
            return {"success": False, "error": str(e), "summary": f"Failed to write file: {e}"}

    @staticmethod
    def modify_file(file_path: str, search_text: str, replacement_text: str) -> dict:
        """Replaces exact target content within a file."""
        try:
            path = Path(file_path).expanduser().resolve()
            if not path.exists():
                return {"success": False, "error": f"File not found: {path}"}

            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()

            if search_text not in content:
                return {"success": False, "error": f"Target content not found in {path.name}"}

            new_content = content.replace(search_text, replacement_text, 1)
            with open(path, "w", encoding="utf-8") as f:
                f.write(new_content)

            return {
                "success": True,
                "path": str(path),
                "summary": f"Successfully updated content in {path.name}."
            }
        except Exception as e:
            return {"success": False, "error": str(e), "summary": f"Failed to modify file: {e}"}

    @staticmethod
    def list_directory(dir_path: str = ".") -> dict:
        """Lists files and directories in a given folder."""
        try:
            path = Path(dir_path).expanduser().resolve()
            if not path.exists():
                return {"success": False, "error": f"Directory not found: {path}"}

            entries = []
            for item in sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
                try:
                    is_dir = item.is_dir()
                    size_kb = round(item.stat().st_size / 1024, 1) if not is_dir else "-"
                    entries.append(f"{'[DIR] ' if is_dir else '      '}{item.name} ({size_kb} KB)")
                except Exception:
                    continue

            summary_text = f"Contents of {path}:\n" + "\n".join(entries[:50])
            if len(entries) > 50:
                summary_text += f"\n... and {len(entries) - 50} more items."

            return {"success": True, "path": str(path), "items": entries, "summary": summary_text}
        except Exception as e:
            return {"success": False, "error": str(e), "summary": f"Failed to list directory: {e}"}

    @staticmethod
    def set_volume(action_or_level: str) -> dict:
        """Adjusts laptop master volume via Windows Core Audio API (pycaw)."""
        action = str(action_or_level).lower().strip()
        try:
            from pycaw.pycaw import AudioUtilities
            speakers = AudioUtilities.GetSpeakers()
            endpoint = speakers.EndpointVolume
            current_scalar = endpoint.GetMasterVolumeLevelScalar()

            # Parse numeric percentage (e.g. '50', '80%', 'set to 75')
            num_match = re.search(r"(\d+)", action)

            if "unmute" in action:
                endpoint.SetMute(0, None)
                return {"success": True, "action": "Unmuted laptop volume", "summary": "Unmuted audio."}
            elif "mute" in action:
                endpoint.SetMute(1, None)
                return {"success": True, "action": "Muted laptop volume", "summary": "Muted audio."}
            elif num_match and ("to" in action or "at" in action or len(action) <= 4):
                target_pct = max(0, min(100, int(num_match.group(1))))
                endpoint.SetMasterVolumeLevelScalar(target_pct / 100.0, None)
                endpoint.SetMute(0, None)
                return {
                    "success": True,
                    "action": f"Set master volume to {target_pct}%",
                    "summary": f"Master volume set to {target_pct}%."
                }
            elif "down" in action or "lower" in action or "quieter" in action:
                new_scalar = max(0.0, current_scalar - 0.10)
                endpoint.SetMasterVolumeLevelScalar(new_scalar, None)
                new_pct = round(new_scalar * 100)
                return {
                    "success": True,
                    "action": f"Lowered volume to {new_pct}%",
                    "summary": f"Lowered volume by 10% (now at {new_pct}%)."
                }
            else:
                # Default / 'up' / 'higher' / 'louder'
                new_scalar = min(1.0, current_scalar + 0.10)
                endpoint.SetMasterVolumeLevelScalar(new_scalar, None)
                endpoint.SetMute(0, None)
                new_pct = round(new_scalar * 100)
                return {
                    "success": True,
                    "action": f"Raised volume to {new_pct}%",
                    "summary": f"Raised volume by 10% (now at {new_pct}%)."
                }
        except Exception as e:
            # Fallback to keybd_event if pycaw encounters an error
            try:
                if "mute" in action:
                    ctypes.windll.user32.keybd_event(VK_VOLUME_MUTE, 0, 0, 0)
                    ctypes.windll.user32.keybd_event(VK_VOLUME_MUTE, 0, 2, 0)
                elif "down" in action:
                    for _ in range(5):
                        ctypes.windll.user32.keybd_event(VK_VOLUME_DOWN, 0, 0, 0)
                        ctypes.windll.user32.keybd_event(VK_VOLUME_DOWN, 0, 2, 0)
                else:
                    for _ in range(5):
                        ctypes.windll.user32.keybd_event(VK_VOLUME_UP, 0, 0, 0)
                        ctypes.windll.user32.keybd_event(VK_VOLUME_UP, 0, 2, 0)
                return {"success": True, "action": "Adjusted volume via key simulation", "summary": "Volume adjusted."}
            except Exception as e2:
                return {"success": False, "error": str(e), "summary": f"Failed to adjust volume: {e}"}

    @staticmethod
    def take_screenshot(filename: str = None) -> dict:
        """Captures a high-resolution screenshot of the laptop screen using Win32 GDI BitBlt with fallbacks."""
        screenshot_dir = Path(os.getcwd()) / "screenshots"
        screenshot_dir.mkdir(parents=True, exist_ok=True)

        if not filename:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"screenshot_{timestamp}.png"

        save_path = screenshot_dir / filename
        captured = False
        last_error = ""

        # 1. Primary: Win32 GDI BitBlt via ctypes (handles high DPI, multi-monitor, and avoids Pillow screen grab failed)
        try:
            import ctypes
            from ctypes import wintypes
            from PIL import Image

            user32 = ctypes.windll.user32
            gdi32 = ctypes.windll.gdi32

            try:
                ctypes.windll.shcore.SetProcessDpiAwareness(2)
            except Exception:
                try:
                    user32.SetProcessDPIAware()
                except Exception:
                    pass

            w = user32.GetSystemMetrics(0)
            h = user32.GetSystemMetrics(1)
            hdesktop = user32.GetDesktopWindow()
            desktop_dc = user32.GetWindowDC(hdesktop)
            mem_dc = gdi32.CreateCompatibleDC(desktop_dc)
            bitmap = gdi32.CreateCompatibleBitmap(desktop_dc, w, h)
            old_bitmap = gdi32.SelectObject(mem_dc, bitmap)

            # SRCCOPY = 0x00CC0020, CAPTUREBLT = 0x40000000
            gdi32.BitBlt(mem_dc, 0, 0, w, h, desktop_dc, 0, 0, 0x00CC0020 | 0x40000000)

            class BITMAPINFOHEADER(ctypes.Structure):
                _fields_ = [
                    ('biSize', wintypes.DWORD),
                    ('biWidth', wintypes.LONG),
                    ('biHeight', wintypes.LONG),
                    ('biPlanes', wintypes.WORD),
                    ('biBitCount', wintypes.WORD),
                    ('biCompression', wintypes.DWORD),
                    ('biSizeImage', wintypes.DWORD),
                    ('biXPelsPerMeter', wintypes.LONG),
                    ('biYPelsPerMeter', wintypes.LONG),
                    ('biClrUsed', wintypes.DWORD),
                    ('biClrImportant', wintypes.DWORD)
                ]

            bmi = BITMAPINFOHEADER()
            bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
            bmi.biWidth = w
            bmi.biHeight = -h  # top-down
            bmi.biPlanes = 1
            bmi.biBitCount = 32
            bmi.biCompression = 0

            buf = ctypes.create_string_buffer(w * h * 4)
            gdi32.GetDIBits(mem_dc, bitmap, 0, h, buf, ctypes.byref(bmi), 0)

            gdi32.SelectObject(mem_dc, old_bitmap)
            gdi32.DeleteObject(bitmap)
            gdi32.DeleteDC(mem_dc)
            user32.ReleaseDC(hdesktop, desktop_dc)

            img = Image.frombuffer('RGBA', (w, h), buf, 'raw', 'BGRA', 0, 1)
            img = img.convert('RGB')
            img.save(save_path, 'PNG')
            captured = True
        except Exception as e:
            last_error = f"Win32 GDI error: {e}"

        # 2. Secondary fallback: PIL ImageGrab
        if not captured or not save_path.exists() or save_path.stat().st_size == 0:
            try:
                from PIL import ImageGrab
                img = ImageGrab.grab(all_screens=True)
                img.save(save_path)
                captured = True
            except Exception as e:
                last_error = f"{last_error} | ImageGrab error: {e}"

        # 3. Tertiary fallback: PowerShell .NET Graphics.CopyFromScreen
        if not captured or not save_path.exists() or save_path.stat().st_size == 0:
            try:
                escaped_target = str(save_path.resolve()).replace("'", "''")
                ps_script = (
                    "Add-Type -AssemblyName System.Windows.Forms; Add-Type -AssemblyName System.Drawing; "
                    "$b = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds; "
                    "$bmp = New-Object System.Drawing.Bitmap($b.Width, $b.Height); "
                    "$g = [System.Drawing.Graphics]::FromImage($bmp); "
                    "$g.CopyFromScreen($b.Location, [System.Drawing.Point]::Empty, $b.Size); "
                    f"$bmp.Save('{escaped_target}', [System.Drawing.Imaging.ImageFormat]::Png); "
                    "$g.Dispose(); $bmp.Dispose();"
                )
                subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], capture_output=True, timeout=15)
                if save_path.exists() and save_path.stat().st_size > 0:
                    captured = True
            except Exception as e:
                last_error = f"{last_error} | PowerShell error: {e}"

        if captured and save_path.exists() and save_path.stat().st_size > 0:
            return {
                "success": True,
                "path": str(save_path.resolve()),
                "output_path": str(save_path.resolve()),
                "filename": filename,
                "summary": f"Captured screenshot: '{filename}' saved to screenshots folder."
            }
        return {"success": False, "error": last_error or "Unable to capture screen", "summary": f"Failed to take screenshot: {last_error}"}

    @staticmethod
    def read_screen(prompt: str = "") -> dict:
        """Captures active laptop screen and prepares it for multimodal AI vision analysis."""
        shot_res = AssistantTools.take_screenshot()
        if not shot_res.get("success") or not shot_res.get("output_path"):
            return {
                "success": False,
                "error": shot_res.get("error", "Failed to capture screen"),
                "summary": "I could not capture your screen right now, sir."
            }
        shot_path = shot_res["output_path"]
        return {
            "success": True,
            "action": "read_screen",
            "screenshot_path": shot_path,
            "output_path": shot_path,
            "summary": f"Screen captured. Analyzing visible display. [MEDIA: {shot_path}]"
        }

    @staticmethod
    def kill_process(process_name: str) -> dict:
        """Terminates a process by name."""
        proc = process_name.strip()
        if not proc.endswith(".exe"):
            proc += ".exe"
        try:
            subprocess.run(["taskkill", "/IM", proc, "/F"], capture_output=True, text=True)
            return {"success": True, "action": f"Terminated process {proc}", "summary": f"Killed process {proc}."}
        except Exception as e:
            return {"success": False, "error": str(e), "summary": f"Failed to kill process: {e}"}

    @staticmethod
    def get_system_stats() -> dict:
        """Retrieve CPU, RAM, disk, and battery metrics."""
        try:
            cpu_percent = psutil.cpu_percent(interval=0.2)
            cpu_count = psutil.cpu_count(logical=True)

            memory = psutil.virtual_memory()
            ram_used_gb = round(memory.used / (1024 ** 3), 2)
            ram_total_gb = round(memory.total / (1024 ** 3), 2)
            ram_percent = memory.percent

            disk = psutil.disk_usage("C:\\")
            disk_free_gb = round(disk.free / (1024 ** 3), 1)
            disk_total_gb = round(disk.total / (1024 ** 3), 1)
            disk_percent = disk.percent

            battery = psutil.sensors_battery()
            battery_info = "Desktop / AC Power"
            if battery:
                plugged = "Plugged in" if battery.power_plugged else "On battery"
                battery_info = f"{battery.percent}% ({plugged})"

            return {
                "success": True,
                "cpu": f"{cpu_percent}% ({cpu_count} cores)",
                "ram": f"{ram_used_gb} GB / {ram_total_gb} GB ({ram_percent}%)",
                "disk": f"{disk_free_gb} GB free / {disk_total_gb} GB ({disk_percent}% used)",
                "battery": battery_info,
                "summary": f"CPU: {cpu_percent}% | RAM: {ram_used_gb}/{ram_total_gb} GB ({ram_percent}%) | Disk C: {disk_free_gb} GB free | Battery: {battery_info}"
            }
        except Exception as e:
            return {"success": False, "error": str(e), "summary": f"Failed to get system stats: {e}"}

    @staticmethod
    def get_date_time() -> dict:
        """Return the current local date, time, and day."""
        now = datetime.datetime.now()
        time_str = now.strftime("%I:%M %p")
        date_str = now.strftime("%A, %B %d, %Y")
        return {
            "success": True,
            "time": time_str,
            "date": date_str,
            "summary": f"The current time is {time_str} on {date_str}."
        }

    @staticmethod
    def open_application(app_name: str) -> dict:
        """Open a local desktop application with intelligent fuzzy search and ambiguity detection."""
        from .app_launcher import app_launcher
        return app_launcher.resolve_and_launch(app_name)

    @staticmethod
    def open_web_search(query: str) -> dict:
        """Open web browser with search query."""
        try:
            url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
            webbrowser.open(url)
            return {"success": True, "action": f"Opened web search for: '{query}'", "summary": f"Searching Google for: '{query}'"}
        except Exception as e:
            return {"success": False, "error": str(e), "summary": f"Failed to search web: {e}"}

    @staticmethod
    def open_top_youtube_video(query: str = None) -> dict:
        """Opens the first video matching query (or last searched YouTube query) directly in browser."""
        from .app_launcher import app_launcher
        return app_launcher.open_top_youtube_video(query)

    @staticmethod
    def open_url(url: str) -> dict:
        """Open a specific URL in the default browser."""
        try:
            if not url.startswith("http://") and not url.startswith("https://"):
                url = "https://" + url
            webbrowser.open(url)
            return {"success": True, "action": f"Opened {url}", "summary": f"Opened {url} in browser."}
        except Exception as e:
            return {"success": False, "error": str(e), "summary": f"Failed to open URL: {e}"}

    @staticmethod
    def search_files(query: str, extension: str = None) -> dict:
        """Searches for files on the laptop matching a query or extension."""
        from .file_search import file_search_engine
        exts = [extension] if extension else None
        matches = file_search_engine.search_files(query, extensions=exts)
        if not matches:
            return {"success": False, "query": query, "matches": [], "summary": f"No files found matching '{query}'."}

        lines = [f"- {m['name']} (in {m['parent']}, {m['size_kb']} KB) -> `{m['path']}`" for m in matches]
        summary = f"Found {len(matches)} files matching '{query}':\n" + "\n".join(lines)
        return {"success": True, "query": query, "count": len(matches), "matches": matches, "summary": summary}

    @staticmethod
    def search_folders(query: str) -> dict:
        """Searches for folders on the laptop matching a query."""
        from .file_search import file_search_engine
        matches = file_search_engine.search_folders(query)
        if not matches:
            return {"success": False, "query": query, "matches": [], "summary": f"No folders found matching '{query}'."}

        lines = [f"- {m['name']} (in {m['parent']}) -> `{m['path']}`" for m in matches]
        summary = f"Found {len(matches)} folders matching '{query}':\n" + "\n".join(lines)
        return {"success": True, "query": query, "count": len(matches), "matches": matches, "summary": summary}

    @staticmethod
    def open_file(file_path: str) -> dict:
        """Opens a local file in its default registered application with automatic fuzzy resolution."""
        from .file_search import file_search_engine
        p = Path(file_path).expanduser()
        if p.exists() and p.is_file():
            return file_search_engine.open_file(str(p))

        # If not a direct file path, search and resolve it
        res = file_search_engine.resolve_and_handle(f"open {file_path}")
        if res.get("status") == "found":
            return res.get("action_result", file_search_engine.open_file(res["match"]["path"]))
        elif res.get("status") == "doubt":
            return {
                "success": False,
                "doubt": True,
                "file_doubt": True,
                "query": res["query"],
                "type": "file",
                "matches": res["matches"],
                "summary": f"Multiple files found matching '{file_path}'."
            }
        return {"success": False, "error": f"File not found: {file_path}", "summary": f"Could not find file '{file_path}'."}

    @staticmethod
    def open_folder(folder_path: str) -> dict:
        """Opens a local directory in Windows File Explorer with automatic fuzzy resolution."""
        from .file_search import file_search_engine
        p = Path(folder_path).expanduser()
        if p.exists() and p.is_dir():
            return file_search_engine.open_folder(str(p))

        # If not a direct folder path, search and resolve it
        res = file_search_engine.resolve_and_handle(f"folder {folder_path}")
        if res.get("status") == "found":
            return res.get("action_result", file_search_engine.open_folder(res["match"]["path"]))
        elif res.get("status") == "doubt":
            return {
                "success": False,
                "doubt": True,
                "file_doubt": True,
                "query": res["query"],
                "type": "folder",
                "matches": res["matches"],
                "summary": f"Multiple folders found matching '{folder_path}'."
            }
        return {"success": False, "error": f"Folder not found: {folder_path}", "summary": f"Could not find folder '{folder_path}'."}

    @staticmethod
    def reveal_in_explorer(file_path: str) -> dict:
        """Reveals a file highlighted in Windows File Explorer with automatic resolution."""
        from .file_search import file_search_engine
        p = Path(file_path).expanduser()
        if p.exists():
            return file_search_engine.reveal_in_explorer(str(p))

        res = file_search_engine.resolve_and_handle(f"reveal {file_path}")
        if res.get("status") == "found":
            return res.get("action_result", file_search_engine.reveal_in_explorer(res["match"]["path"]))
        return file_search_engine.reveal_in_explorer(file_path)

    @classmethod
    def edit_image(cls, image_path: str, operation: str = "info", *params) -> dict:
        """
        Edits an image on the laptop using MediaEditor.
        Operations:
        - 'resize': params = [width, height (optional)]
        - 'crop': params = [left, top, right, bottom]
        - 'rotate': params = [degrees] (e.g. 90, 180, -90)
        - 'flip': params = [direction] ('horizontal' or 'vertical')
        - 'filter': params = [filter_name] ('grayscale', 'sepia', 'blur', 'sharpen', 'edge_enhance', 'contour', 'invert')
        - 'adjust': params = [brightness, contrast, saturation, sharpness]
        - 'watermark': params = [text, position (optional), color (optional)]
        - 'convert': params = [target_format] ('png', 'jpg', 'webp')
        """
        from .media_editor import media_editor
        op = operation.lower().strip()
        p = Path(image_path).expanduser()
        if not p.exists():
            from .file_search import file_search_engine
            f_res = file_search_engine.search_files(image_path)
            if f_res:
                p = Path(f_res[0]["path"])

        if not p.exists():
            return {"success": False, "error": f"Image file not found: {image_path}", "summary": f"Could not find image: {image_path}"}

        img_str = str(p)
        if op == "resize":
            w = int(params[0]) if len(params) > 0 else 800
            h = int(params[1]) if len(params) > 1 and params[1] else None
            return media_editor.resize_image(img_str, w, h)
        elif op == "crop":
            l = int(params[0]) if len(params) > 0 else 0
            t = int(params[1]) if len(params) > 1 else 0
            r = int(params[2]) if len(params) > 2 else 500
            b = int(params[3]) if len(params) > 3 else 500
            return media_editor.crop_image(img_str, l, t, r, b)
        elif op == "rotate":
            deg = float(params[0]) if len(params) > 0 else 90.0
            return media_editor.rotate_image(img_str, deg)
        elif op == "flip":
            d = str(params[0]) if len(params) > 0 else "horizontal"
            return media_editor.flip_image(img_str, d)
        elif op in ["filter", "apply_filter"]:
            f_name = str(params[0]) if len(params) > 0 else "grayscale"
            return media_editor.apply_filter(img_str, f_name)
        elif op in ["adjust", "color"]:
            b = float(params[0]) if len(params) > 0 else 1.0
            c = float(params[1]) if len(params) > 1 else 1.0
            s = float(params[2]) if len(params) > 2 else 1.0
            sh = float(params[3]) if len(params) > 3 else 1.0
            return media_editor.adjust_image(img_str, b, c, s, sh)
        elif op in ["watermark", "add_watermark", "text"]:
            txt = str(params[0]) if len(params) > 0 else "JARVIS AI"
            pos = str(params[1]) if len(params) > 1 else "bottom-right"
            col = str(params[2]) if len(params) > 2 else "white"
            return media_editor.add_watermark(img_str, txt, position=pos, color=col)
        elif op in ["convert", "format"]:
            fmt = str(params[0]) if len(params) > 0 else "png"
            return media_editor.convert_image(img_str, fmt)
        else:
            return media_editor.inspect_media(img_str)

    @classmethod
    def edit_video(cls, video_path: str, operation: str = "info", *params) -> dict:
        """
        Edits a video on the laptop using MediaEditor.
        Operations:
        - 'trim': params = [start_time, end_time] (e.g. '00:00:05', '00:00:20')
        - 'resize': params = [width] (e.g. 720, 1080)
        - 'extract_audio': params = [format] ('mp3' or 'wav')
        - 'mute': params = []
        - 'snapshot' / 'extract_frame': params = [timestamp_sec]
        - 'convert': params = [target_format] ('mp4', 'gif', 'webm')
        - 'speed': params = [speed_multiplier] (e.g. 1.5, 2.0, 0.5)
        """
        from .media_editor import media_editor
        op = operation.lower().strip()
        p = Path(video_path).expanduser()
        if not p.exists():
            from .file_search import file_search_engine
            f_res = file_search_engine.search_files(video_path)
            if f_res:
                p = Path(f_res[0]["path"])

        if not p.exists():
            return {"success": False, "error": f"Video file not found: {video_path}", "summary": f"Could not find video: {video_path}"}

        vid_str = str(p)
        if op == "trim":
            start_t = str(params[0]) if len(params) > 0 else "0"
            end_t = str(params[1]) if len(params) > 1 else "10"
            return media_editor.trim_video(vid_str, start_t, end_t)
        elif op == "resize":
            w = int(params[0]) if len(params) > 0 else 720
            return media_editor.resize_video(vid_str, w)
        elif op in ["extract_audio", "audio"]:
            fmt = str(params[0]) if len(params) > 0 else "mp3"
            return media_editor.extract_audio(vid_str, fmt)
        elif op in ["mute", "remove_audio", "silence"]:
            return media_editor.mute_video(vid_str)
        elif op in ["snapshot", "extract_frame", "thumbnail"]:
            t_sec = float(params[0]) if len(params) > 0 else 0.0
            return media_editor.extract_frame(vid_str, t_sec)
        elif op in ["convert", "format"]:
            fmt = str(params[0]) if len(params) > 0 else "mp4"
            return media_editor.convert_video(vid_str, fmt)
        elif op in ["speed", "playback_speed"]:
            sp = float(params[0]) if len(params) > 0 else 2.0
            return media_editor.adjust_video_speed(vid_str, sp)
        else:
            return media_editor.inspect_media(vid_str)

    @classmethod
    def inspect_media(cls, media_path: str) -> dict:
        """Inspects media returning dimensions, file format, and size."""
        from .media_editor import media_editor
        p = Path(media_path).expanduser()
        if not p.exists():
            from .file_search import file_search_engine
            f_res = file_search_engine.search_files(media_path)
            if f_res:
                p = Path(f_res[0]["path"])
        return media_editor.inspect_media(str(p))

    _groq_client = None

    @classmethod
    def set_groq_client(cls, groq_client):
        """Registers the active GroqClient for AI document structure synthesis."""
        cls._groq_client = groq_client
        from .document_generator import document_generator
        document_generator.set_groq_client(groq_client)

    @classmethod
    def create_presentation(cls, topic: str, theme: str = "jarvis_dark", output_path: str = None) -> dict:
        """Creates a professional 16:9 widescreen PowerPoint (.pptx) presentation with AI content synthesis."""
        from .document_generator import document_generator
        from .groq_client import usage_tracker
        res = document_generator.create_presentation(topic, theme_name=theme or "jarvis_dark", output_path=output_path, groq_client=cls._groq_client)
        if res.get("success"):
            usage_tracker.record_document()
        return res

    @classmethod
    def create_document(cls, title: str, theme: str = "executive", output_path: str = None) -> dict:
        """Creates a professional Word (.docx) document with custom styling, callouts, and tables."""
        from .document_generator import document_generator
        from .groq_client import usage_tracker
        res = document_generator.create_document(title, theme_name=theme or "executive", output_path=output_path, groq_client=cls._groq_client)
        if res.get("success"):
            usage_tracker.record_document()
        return res

    @classmethod
    def create_pdf(cls, title: str, theme: str = "modern_tech", output_path: str = None) -> dict:
        """Creates a publication-quality PDF (.pdf) report with executive layout and dynamic footers."""
        from .document_generator import document_generator
        from .groq_client import usage_tracker
        res = document_generator.create_pdf(title, theme_name=theme or "modern_tech", output_path=output_path, groq_client=cls._groq_client)
        if res.get("success"):
            usage_tracker.record_document()
        return res

    @classmethod
    def generate_ai_image(cls, prompt: str, style: str = "") -> dict:
        """Generates an AI image from a text prompt with optional style using FLUX/Pollinations."""
        from .ai_image import ai_image_engine
        from .groq_client import usage_tracker
        res = ai_image_engine.generate_image(prompt, style=style)
        if res.get("success"):
            usage_tracker.record_image()
        return res

    @classmethod
    def alter_ai_image(cls, image_path: str, instruction: str) -> dict:
        """Alters an existing image using AI style transfer, neural filters, and color grading."""
        from .ai_image import ai_image_engine
        from .groq_client import usage_tracker
        res = ai_image_engine.alter_image(image_path, instruction)
        if res.get("success"):
            usage_tracker.record_image()
        return res

    @classmethod
    def generate_ai_video(cls, prompt: str, seconds_per_scene: int = 3) -> dict:
        """Generates an AI multi-scene video from text prompt with FLUX frames and neural voiceover."""
        from .ai_video import ai_video_engine
        from .groq_client import usage_tracker
        res = ai_video_engine.generate_video(prompt, seconds_per_scene=seconds_per_scene, groq_client=cls._groq_client)
        if res.get("success"):
            usage_tracker.record_video()
        return res

    @classmethod
    def execute_tool(cls, tool_name: str, *args) -> dict:
        """Unified dispatcher for tool execution."""
        t = tool_name.lower().strip()
        arg0 = args[0] if len(args) > 0 else ""
        arg1 = args[1] if len(args) > 1 else ""

        if t in ["generate_ai_image", "generate_image", "create_image", "ai_image", "text_to_image"]:
            return cls.generate_ai_image(arg0, arg1)
        elif t in ["alter_ai_image", "alter_image", "style_transfer", "ai_filter"]:
            return cls.alter_ai_image(arg0, arg1)
        elif t in ["generate_ai_video", "generate_video", "create_video", "ai_video", "text_to_video"]:
            return cls.generate_ai_video(arg0)

        if t in ["run_python_code", "python_code", "run_python", "python", "py"]:
            return cls.run_python_code(arg0)
        elif t in ["run_powershell_code", "powershell_code", "run_pwsh", "pwsh"]:
            return cls.run_powershell_code(arg0)
        elif t in ["run_command", "run_shell_command", "terminal", "bash", "powershell", "shell"]:
            return cls.run_shell_command(arg0)
        elif t in ["read_file", "view_file"]:
            return cls.read_file(arg0)
        elif t in ["write_file", "create_file"]:
            return cls.write_file(arg0, arg1)
        elif t in ["modify_file", "edit_file"]:
            arg2 = args[2] if len(args) > 2 else ""
            return cls.modify_file(arg0, arg1, arg2)
        elif t in ["list_directory", "list_dir", "ls", "dir"]:
            return cls.list_directory(arg0 or ".")
        elif t in ["search_files", "search_file", "find_file", "find_files"]:
            return cls.search_files(arg0, arg1 or None)
        elif t in ["search_folders", "search_folder", "find_folder"]:
            return cls.search_folders(arg0)
        elif t in ["open_file", "launch_file"]:
            return cls.open_file(arg0)
        elif t in ["open_folder", "launch_folder"]:
            return cls.open_folder(arg0)
        elif t in ["reveal_in_explorer", "reveal_file", "locate_file", "show_in_folder"]:
            return cls.reveal_in_explorer(arg0)
        elif t in ["edit_image", "image_edit", "modify_image", "resize_image", "crop_image", "filter_image"]:
            return cls.edit_image(arg0, arg1, *args[2:])
        elif t in ["edit_video", "video_edit", "trim_video", "resize_video", "extract_audio", "mute_video"]:
            return cls.edit_video(arg0, arg1, *args[2:])
        elif t in ["inspect_media", "media_info", "image_info", "video_info"]:
            return cls.inspect_media(arg0)
        elif t in ["create_presentation", "create_ppt", "create_pptx", "generate_ppt", "make_ppt", "make_presentation"]:
            return cls.create_presentation(arg0, arg1 or "jarvis_dark")
        elif t in ["create_document", "create_word", "create_docx", "generate_word", "make_word", "make_document"]:
            return cls.create_document(arg0, arg1 or "executive")
        elif t in ["create_pdf", "generate_pdf", "make_pdf"]:
            return cls.create_pdf(arg0, arg1 or "modern_tech")
        elif t in ["set_volume", "volume"]:
            return cls.set_volume(arg0)
        elif t in ["take_screenshot", "screenshot"]:
            return cls.take_screenshot(arg0 or None)
        elif t in ["kill_process", "kill", "close_app"]:
            return cls.kill_process(arg0)
        elif t in ["get_system_stats", "system_stats", "stats"]:
            return cls.get_system_stats()
        elif t in ["get_date_time", "time", "date"]:
            return cls.get_date_time()
        elif t in ["open_application", "open_app"]:
            return cls.open_application(arg0)
        elif t in ["open_web_search", "web_search", "search"]:
            return cls.open_web_search(arg0)
        elif t in ["open_top_youtube_video", "play_youtube", "first_youtube_link", "youtube_top_video"]:
            return cls.open_top_youtube_video(arg0)
        elif t in ["open_url", "browse"]:
            return cls.open_url(arg0)
        elif t in ["mouse_click", "click"]:
            from core.computer_control import ComputerControl
            return ComputerControl.mouse_click(arg0 or None, arg1 or None)
        elif t in ["mouse_double_click", "double_click"]:
            from core.computer_control import ComputerControl
            return ComputerControl.mouse_double_click(arg0 or None, arg1 or None)
        elif t in ["mouse_right_click", "right_click"]:
            from core.computer_control import ComputerControl
            return ComputerControl.mouse_right_click(arg0 or None, arg1 or None)
        elif t in ["mouse_move", "move_mouse"]:
            from core.computer_control import ComputerControl
            return ComputerControl.mouse_move(arg0, arg1)
        elif t in ["mouse_scroll", "scroll"]:
            from core.computer_control import ComputerControl
            return ComputerControl.mouse_scroll(int(arg0 or 1))
        elif t in ["keyboard_type", "type_text", "type"]:
            from core.computer_control import ComputerControl
            return ComputerControl.keyboard_type(str(arg0))
        elif t in ["keyboard_press", "press_key", "key"]:
            from core.computer_control import ComputerControl
            return ComputerControl.keyboard_press(str(arg0))
        elif t in ["keyboard_hotkey", "hotkey"]:
            from core.computer_control import ComputerControl
            return ComputerControl.keyboard_hotkey(*args)
        elif t in ["window_focus", "focus_window", "switch_to_window"]:
            from core.computer_control import ComputerControl
            return ComputerControl.window_focus(arg0)
        elif t in ["window_list", "list_windows"]:
            from core.computer_control import ComputerControl
            return ComputerControl.window_list()
        elif t in ["window_minimize"]:
            from core.computer_control import ComputerControl
            return ComputerControl.window_minimize(arg0)
        elif t in ["window_maximize"]:
            from core.computer_control import ComputerControl
            return ComputerControl.window_maximize(arg0)
        elif t in ["clipboard_read", "read_clipboard"]:
            from core.computer_control import ComputerControl
            return ComputerControl.clipboard_read()
        elif t in ["clipboard_write", "copy_to_clipboard"]:
            from core.computer_control import ComputerControl
            return ComputerControl.clipboard_write(str(arg0))
        elif t in ["inspect_screen", "read_screen", "analyze_screen"]:
            return cls.read_screen(arg0 or "What is on my screen?")
        elif t in ["click_ui_element", "click_element"]:
            from core.vision.screen_analyzer import ScreenAnalyzer
            return ScreenAnalyzer().click_ui_element(str(arg0))
        else:
            return {"success": False, "error": f"Unknown tool: {tool_name}"}
