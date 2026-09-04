import os
import subprocess
import webbrowser
import datetime
import shutil
import psutil

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

class AssistantTools:
    """Executes system automation tools for Jarvis AI Assistant."""

    @staticmethod
    def get_system_stats():
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
            battery_info = "Not available (Desktop)"
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
    def get_date_time():
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
    def open_application(app_name):
        """Open a local desktop application or tool."""
        app_key = app_name.lower().strip()
        command = APP_COMMANDS.get(app_key)

        try:
            if command:
                if command.startswith("start "):
                    subprocess.Popen(command, shell=True)
                else:
                    subprocess.Popen(command)
                return {"success": True, "action": f"Launched {app_name}"}
            else:
                # Attempt to launch via Windows start command
                subprocess.Popen(f"start {app_name}", shell=True)
                return {"success": True, "action": f"Attempted to launch {app_name}"}
        except Exception as e:
            return {"success": False, "error": str(e), "action": f"Failed to open {app_name}: {e}"}

    @staticmethod
    def open_web_search(query):
        """Open web browser with search query."""
        try:
            url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
            webbrowser.open(url)
            return {"success": True, "action": f"Opened web search for: '{query}'"}
        except Exception as e:
            return {"success": False, "error": str(e), "action": f"Failed to search web: {e}"}

    @staticmethod
    def open_url(url):
        """Open a specific URL in the default browser."""
        try:
            if not url.startswith("http://") and not url.startswith("https://"):
                url = "https://" + url
            webbrowser.open(url)
            return {"success": True, "action": f"Opened {url}"}
        except Exception as e:
            return {"success": False, "error": str(e), "action": f"Failed to open URL: {e}"}

    @classmethod
    def execute_tool(cls, tool_name, param=""):
        """Dispatcher for tool execution."""
        tool_name = tool_name.lower().strip()
        if tool_name in ["get_system_stats", "system_stats", "stats"]:
            return cls.get_system_stats()
        elif tool_name in ["get_date_time", "time", "date"]:
            return cls.get_date_time()
        elif tool_name in ["open_application", "open_app"]:
            return cls.open_application(param)
        elif tool_name in ["open_web_search", "web_search", "search"]:
            return cls.open_web_search(param)
        elif tool_name in ["open_url", "browse"]:
            return cls.open_url(param)
        else:
            return {"success": False, "error": f"Unknown tool: {tool_name}"}
