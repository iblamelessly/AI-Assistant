"""
Computer Control Layer for JARVIS AI Assistant.
Provides controlled, structured OS automation tools for Windows:
mouse control, keyboard typing/hotkeys, window management,
clipboard read/write, application launching, and screen metrics.

All tools return standardized structured data:
{
    "success": bool,
    "action": str,
    "target": str,
    "error": str or None,
    "summary": str,
    "data": dict or list or None
}
"""

import os
import sys
import time
import ctypes
from ctypes import wintypes
from typing import Optional, List, Dict, Any, Union
import psutil

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# Input structures for SendInput
ULONG_PTR = ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong

class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR)
    ]

class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR)
    ]

class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD)
    ]

class INPUT_UNION(ctypes.Union):
    _fields_ = [
        ("mi", MOUSEINPUT),
        ("ki", KEYBDINPUT),
        ("hi", HARDWAREINPUT)
    ]

class INPUT(ctypes.Structure):
    _fields_ = [
        ("type", wintypes.DWORD),
        ("u", INPUT_UNION)
    ]

# Win32 Constants
INPUT_MOUSE = 0
INPUT_KEYBOARD = 1

MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_WHEEL = 0x0800
MOUSEEVENTF_ABSOLUTE = 0x8000

KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
KEYEVENTF_SCANCODE = 0x0008

# Virtual Key mapping
VK_MAP = {
    "enter": 0x0D,
    "return": 0x0D,
    "esc": 0x1B,
    "escape": 0x1B,
    "tab": 0x09,
    "space": 0x20,
    "backspace": 0x08,
    "delete": 0x2E,
    "del": 0x2E,
    "insert": 0x2D,
    "home": 0x24,
    "end": 0x23,
    "pageup": 0x21,
    "pagedown": 0x22,
    "up": 0x26,
    "down": 0x28,
    "left": 0x25,
    "right": 0x27,
    "ctrl": 0x11,
    "control": 0x11,
    "alt": 0x12,
    "shift": 0x10,
    "win": 0x5B,
    "windows": 0x5B,
    "capslock": 0x14,
    "numlock": 0x90,
    "f1": 0x70, "f2": 0x71, "f3": 0x72, "f4": 0x73,
    "f5": 0x74, "f6": 0x75, "f7": 0x76, "f8": 0x77,
    "f9": 0x78, "f10": 0x79, "f11": 0x7A, "f12": 0x7B
}


def _send_input(inputs: List[INPUT]) -> int:
    """Helper to dispatch SendInput array."""
    n = len(inputs)
    arr = (INPUT * n)(*inputs)
    return user32.SendInput(n, arr, ctypes.sizeof(INPUT))


class ComputerControl:
    """Provides high-level, safe Windows OS automation tools."""

    # ──────────────── MOUSE CONTROL ────────────────

    @staticmethod
    def get_screen_resolution() -> Dict[str, int]:
        """Returns primary display resolution."""
        w = user32.GetSystemMetrics(0)
        h = user32.GetSystemMetrics(1)
        return {"width": w, "height": h}

    @staticmethod
    def get_mouse_position() -> Dict[str, Any]:
        """Returns current mouse cursor coordinates."""
        pt = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        return {
            "success": True,
            "action": "get_mouse_position",
            "target": f"({pt.x}, {pt.y})",
            "error": None,
            "summary": f"Mouse cursor at X={pt.x}, Y={pt.y}",
            "data": {"x": pt.x, "y": pt.y}
        }

    @classmethod
    def mouse_move(cls, x: int, y: int) -> Dict[str, Any]:
        """Moves mouse cursor to specified coordinates."""
        try:
            res = cls.get_screen_resolution()
            x = max(0, min(int(x), res["width"] - 1))
            y = max(0, min(int(y), res["height"] - 1))
            user32.SetCursorPos(x, y)
            return {
                "success": True,
                "action": "mouse_move",
                "target": f"({x}, {y})",
                "error": None,
                "summary": f"Moved mouse to ({x}, {y})",
                "data": {"x": x, "y": y}
            }
        except Exception as e:
            return {
                "success": False,
                "action": "mouse_move",
                "target": f"({x}, {y})",
                "error": str(e),
                "summary": f"Failed to move mouse: {e}",
                "data": None
            }

    @classmethod
    def mouse_click(cls, x: Optional[int] = None, y: Optional[int] = None, button: str = "left", count: int = 1) -> Dict[str, Any]:
        """Clicks specified mouse button (left/right/middle) at given (or current) coordinates."""
        try:
            if x is not None and y is not None:
                cls.mouse_move(x, y)
                time.sleep(0.04)

            btn = button.lower().strip()
            if btn in ["right", "r"]:
                down_flag, up_flag = MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP
            elif btn in ["middle", "m"]:
                down_flag, up_flag = MOUSEEVENTF_MIDDLEDOWN, MOUSEEVENTF_MIDDLEUP
            else:
                down_flag, up_flag = MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP

            for _ in range(max(1, count)):
                user32.mouse_event(down_flag, 0, 0, 0, 0)
                time.sleep(0.03)
                user32.mouse_event(up_flag, 0, 0, 0, 0)
                if count > 1:
                    time.sleep(0.08)

            pos = cls.get_mouse_position()["data"]
            return {
                "success": True,
                "action": "mouse_click",
                "target": f"{btn} click at ({pos['x']}, {pos['y']}) x{count}",
                "error": None,
                "summary": f"Performed {btn} click x{count} at ({pos['x']}, {pos['y']})",
                "data": {"x": pos["x"], "y": pos["y"], "button": btn, "count": count}
            }
        except Exception as e:
            return {
                "success": False,
                "action": "mouse_click",
                "target": f"{button} at ({x}, {y})",
                "error": str(e),
                "summary": f"Click failed: {e}",
                "data": None
            }

    @classmethod
    def mouse_double_click(cls, x: Optional[int] = None, y: Optional[int] = None) -> Dict[str, Any]:
        """Performs a double click with the left mouse button."""
        res = cls.mouse_click(x, y, button="left", count=2)
        res["action"] = "mouse_double_click"
        return res

    @classmethod
    def mouse_right_click(cls, x: Optional[int] = None, y: Optional[int] = None) -> Dict[str, Any]:
        """Performs a right click."""
        return cls.mouse_click(x, y, button="right", count=1)

    @classmethod
    def mouse_drag(cls, x1: int, y1: int, x2: int, y2: int, duration_sec: float = 0.4) -> Dict[str, Any]:
        """Drags mouse from (x1, y1) to (x2, y2)."""
        try:
            cls.mouse_move(x1, y1)
            time.sleep(0.05)
            user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
            time.sleep(0.05)

            steps = 15
            step_pause = duration_sec / steps
            for i in range(1, steps + 1):
                cur_x = int(x1 + (x2 - x1) * (i / steps))
                cur_y = int(y1 + (y2 - y1) * (i / steps))
                cls.mouse_move(cur_x, cur_y)
                time.sleep(step_pause)

            user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
            return {
                "success": True,
                "action": "mouse_drag",
                "target": f"from ({x1}, {y1}) to ({x2}, {y2})",
                "error": None,
                "summary": f"Dragged mouse from ({x1}, {y1}) to ({x2}, {y2})",
                "data": {"from": (x1, y1), "to": (x2, y2)}
            }
        except Exception as e:
            user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
            return {
                "success": False,
                "action": "mouse_drag",
                "target": f"({x1},{y1}) -> ({x2},{y2})",
                "error": str(e),
                "summary": f"Drag failed: {e}",
                "data": None
            }

    @classmethod
    def mouse_scroll(cls, delta: int, x: Optional[int] = None, y: Optional[int] = None) -> Dict[str, Any]:
        """Scrolls mouse wheel vertically. Positive delta scrolls up, negative down."""
        try:
            if x is not None and y is not None:
                cls.mouse_move(x, y)
                time.sleep(0.03)
            # WHEEL_DELTA is typically 120 per click
            scroll_amount = int(delta * 120) if abs(delta) < 50 else int(delta)
            user32.mouse_event(MOUSEEVENTF_WHEEL, 0, 0, scroll_amount, 0)
            return {
                "success": True,
                "action": "mouse_scroll",
                "target": f"scroll {delta}",
                "error": None,
                "summary": f"Scrolled mouse wheel by {delta}",
                "data": {"delta": delta}
            }
        except Exception as e:
            return {
                "success": False,
                "action": "mouse_scroll",
                "target": f"scroll {delta}",
                "error": str(e),
                "summary": f"Scroll failed: {e}",
                "data": None
            }

    # ──────────────── KEYBOARD CONTROL ────────────────

    @staticmethod
    def keyboard_type(text: str) -> Dict[str, Any]:
        """Types string using Unicode SendInput for full fidelity (all characters, symbols, and languages)."""
        if not text:
            return {
                "success": True,
                "action": "keyboard_type",
                "target": "",
                "error": None,
                "summary": "No text to type.",
                "data": None
            }
        try:
            inputs = []
            for char in text:
                code = ord(char)
                # Key down
                inp_down = INPUT()
                inp_down.type = INPUT_KEYBOARD
                inp_down.u.ki.wVk = 0
                inp_down.u.ki.wScan = code
                inp_down.u.ki.dwFlags = KEYEVENTF_UNICODE
                inp_down.u.ki.time = 0
                inp_down.u.ki.dwExtraInfo = 0
                inputs.append(inp_down)

                # Key up
                inp_up = INPUT()
                inp_up.type = INPUT_KEYBOARD
                inp_up.u.ki.wVk = 0
                inp_up.u.ki.wScan = code
                inp_up.u.ki.dwFlags = KEYEVENTF_UNICODE | KEYEVENTF_KEYUP
                inp_up.u.ki.time = 0
                inp_up.u.ki.dwExtraInfo = 0
                inputs.append(inp_up)

            _send_input(inputs)
            return {
                "success": True,
                "action": "keyboard_type",
                "target": text,
                "error": None,
                "summary": f"Typed text ({len(text)} characters): '{text[:40]}{'...' if len(text) > 40 else ''}'",
                "data": {"length": len(text)}
            }
        except Exception as e:
            return {
                "success": False,
                "action": "keyboard_type",
                "target": text,
                "error": str(e),
                "summary": f"Typing failed: {e}",
                "data": None
            }

    @staticmethod
    def keyboard_press(key: str) -> Dict[str, Any]:
        """Presses and releases a single special key (e.g., enter, esc, tab, space, backspace, up, down)."""
        k = key.lower().strip()
        vk = VK_MAP.get(k)
        if not vk:
            if len(k) == 1:
                return ComputerControl.keyboard_type(key)
            return {
                "success": False,
                "action": "keyboard_press",
                "target": key,
                "error": f"Unknown key: {key}",
                "summary": f"Unknown key '{key}'",
                "data": None
            }

        try:
            user32.keybd_event(vk, 0, 0, 0)
            time.sleep(0.04)
            user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
            return {
                "success": True,
                "action": "keyboard_press",
                "target": key,
                "error": None,
                "summary": f"Pressed key '{key}'",
                "data": {"key": key, "vk": vk}
            }
        except Exception as e:
            return {
                "success": False,
                "action": "keyboard_press",
                "target": key,
                "error": str(e),
                "summary": f"Key press failed: {e}",
                "data": None
            }

    @staticmethod
    def keyboard_hotkey(*keys) -> Dict[str, Any]:
        """
        Presses a key combination (e.g. 'ctrl', 'c' or 'ctrl+shift+esc' or 'alt', 'tab').
        """
        try:
            # Flatten in case user passed a string with '+'
            parsed = []
            for item in keys:
                if isinstance(item, str) and "+" in item:
                    parsed.extend([p.strip().lower() for p in item.split("+") if p.strip()])
                elif isinstance(item, str):
                    parsed.append(item.strip().lower())

            if not parsed:
                return {"success": False, "action": "keyboard_hotkey", "target": "", "error": "No keys specified", "summary": "Empty hotkey", "data": None}

            vks = []
            for k in parsed:
                if k in VK_MAP:
                    vks.append(VK_MAP[k])
                elif len(k) == 1:
                    # Character key virtual code
                    vks.append(ord(k.upper()))
                else:
                    return {"success": False, "action": "keyboard_hotkey", "target": "+".join(parsed), "error": f"Unknown key in combo: {k}", "summary": f"Unknown key in hotkey: {k}", "data": None}

            # Press all down
            for vk in vks:
                user32.keybd_event(vk, 0, 0, 0)
                time.sleep(0.02)

            time.sleep(0.05)

            # Release in reverse order
            for vk in reversed(vks):
                user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
                time.sleep(0.02)

            combo_name = "+".join(parsed)
            return {
                "success": True,
                "action": "keyboard_hotkey",
                "target": combo_name,
                "error": None,
                "summary": f"Pressed hotkey combo: {combo_name}",
                "data": {"keys": parsed}
            }
        except Exception as e:
            return {
                "success": False,
                "action": "keyboard_hotkey",
                "target": str(keys),
                "error": str(e),
                "summary": f"Hotkey execution failed: {e}",
                "data": None
            }

    # ──────────────── WINDOW MANAGEMENT ────────────────

    @staticmethod
    def window_list() -> Dict[str, Any]:
        """Enumerates visible top-level application windows on desktop."""
        try:
            import win32gui
            import win32process

            windows = []

            def _enum_handler(hwnd, _):
                if win32gui.IsWindowVisible(hwnd):
                    text = win32gui.GetWindowText(hwnd).strip()
                    if text and text not in ["Program Manager", "Default IME", "MSCTFIME UI"]:
                        rect = win32gui.GetWindowRect(hwnd)
                        w = rect[2] - rect[0]
                        h = rect[3] - rect[1]
                        if w > 30 and h > 30:
                            _, pid = win32process.GetWindowThreadProcessId(hwnd)
                            pname = ""
                            try:
                                pname = psutil.Process(pid).name()
                            except Exception:
                                pass
                            windows.append({
                                "hwnd": hwnd,
                                "title": text,
                                "process": pname,
                                "pid": pid,
                                "rect": {"x": rect[0], "y": rect[1], "width": w, "height": h}
                            })
                return True

            win32gui.EnumWindows(_enum_handler, None)
            return {
                "success": True,
                "action": "window_list",
                "target": f"{len(windows)} windows",
                "error": None,
                "summary": f"Found {len(windows)} visible windows.",
                "data": windows
            }
        except Exception as e:
            return {
                "success": False,
                "action": "window_list",
                "target": "",
                "error": str(e),
                "summary": f"Failed to list windows: {e}",
                "data": []
            }

    @classmethod
    def window_find(cls, query: str) -> Dict[str, Any]:
        """Finds top-level window matching title or process name query."""
        all_wins = cls.window_list()
        if not all_wins["success"]:
            return all_wins

        q = query.lower().strip()
        matches = []
        for w in all_wins["data"]:
            if q in w["title"].lower() or (w["process"] and q in w["process"].lower()):
                matches.append(w)

        if matches:
            best = matches[0]
            return {
                "success": True,
                "action": "window_find",
                "target": best["title"],
                "error": None,
                "summary": f"Found window: '{best['title']}' ({best['process']})",
                "data": best
            }
        return {
            "success": False,
            "action": "window_find",
            "target": query,
            "error": f"No window found matching '{query}'",
            "summary": f"No window matching '{query}'",
            "data": None
        }

    @classmethod
    def window_focus(cls, target: Union[str, int]) -> Dict[str, Any]:
        """Brings the specified window to foreground and restores if minimized."""
        try:
            import win32gui
            import win32con

            hwnd = None
            title = ""
            if isinstance(target, int):
                hwnd = target
                title = win32gui.GetWindowText(hwnd)
            else:
                found = cls.window_find(str(target))
                if found["success"] and found["data"]:
                    hwnd = found["data"]["hwnd"]
                    title = found["data"]["title"]

            if not hwnd or not win32gui.IsWindow(hwnd):
                return {
                    "success": False,
                    "action": "window_focus",
                    "target": str(target),
                    "error": f"Window not found: {target}",
                    "summary": f"Cannot focus: window '{target}' not found.",
                    "data": None
                }

            # Un-minimize if iconic
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)

            # Bring to foreground safely (Win32 attach thread workaround)
            cur_tid = kernel32.GetCurrentThreadId()
            fg_hwnd = win32gui.GetForegroundWindow()
            fg_tid = user32.GetWindowThreadProcessId(fg_hwnd, None) if fg_hwnd else 0

            if fg_tid and fg_tid != cur_tid:
                user32.AttachThreadInput(cur_tid, fg_tid, True)
                win32gui.SetForegroundWindow(hwnd)
                user32.AttachThreadInput(cur_tid, fg_tid, False)
            else:
                win32gui.SetForegroundWindow(hwnd)

            time.sleep(0.08)
            return {
                "success": True,
                "action": "window_focus",
                "target": title or str(hwnd),
                "error": None,
                "summary": f"Focused window: '{title or hwnd}'",
                "data": {"hwnd": hwnd, "title": title}
            }
        except Exception as e:
            return {
                "success": False,
                "action": "window_focus",
                "target": str(target),
                "error": str(e),
                "summary": f"Failed to focus window: {e}",
                "data": None
            }

    @classmethod
    def window_minimize(cls, target: Union[str, int]) -> Dict[str, Any]:
        """Minimizes specified window."""
        try:
            import win32gui
            import win32con

            hwnd = target if isinstance(target, int) else (cls.window_find(str(target)).get("data") or {}).get("hwnd")
            if not hwnd or not win32gui.IsWindow(hwnd):
                return {"success": False, "action": "window_minimize", "target": str(target), "error": "Window not found", "summary": f"Window '{target}' not found.", "data": None}

            win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
            return {"success": True, "action": "window_minimize", "target": str(target), "error": None, "summary": f"Minimized window '{target}'", "data": {"hwnd": hwnd}}
        except Exception as e:
            return {"success": False, "action": "window_minimize", "target": str(target), "error": str(e), "summary": f"Failed to minimize window: {e}", "data": None}

    @classmethod
    def window_maximize(cls, target: Union[str, int]) -> Dict[str, Any]:
        """Maximizes specified window."""
        try:
            import win32gui
            import win32con

            hwnd = target if isinstance(target, int) else (cls.window_find(str(target)).get("data") or {}).get("hwnd")
            if not hwnd or not win32gui.IsWindow(hwnd):
                return {"success": False, "action": "window_maximize", "target": str(target), "error": "Window not found", "summary": f"Window '{target}' not found.", "data": None}

            win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
            return {"success": True, "action": "window_maximize", "target": str(target), "error": None, "summary": f"Maximized window '{target}'", "data": {"hwnd": hwnd}}
        except Exception as e:
            return {"success": False, "action": "window_maximize", "target": str(target), "error": str(e), "summary": f"Failed to maximize window: {e}", "data": None}

    @classmethod
    def window_close(cls, target: Union[str, int]) -> Dict[str, Any]:
        """Sends WM_CLOSE message to close specified window cleanly."""
        try:
            import win32gui
            import win32con

            hwnd = target if isinstance(target, int) else (cls.window_find(str(target)).get("data") or {}).get("hwnd")
            if not hwnd or not win32gui.IsWindow(hwnd):
                return {"success": False, "action": "window_close", "target": str(target), "error": "Window not found", "summary": f"Window '{target}' not found.", "data": None}

            win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
            return {"success": True, "action": "window_close", "target": str(target), "error": None, "summary": f"Closed window '{target}'", "data": {"hwnd": hwnd}}
        except Exception as e:
            return {"success": False, "action": "window_close", "target": str(target), "error": str(e), "summary": f"Failed to close window: {e}", "data": None}

    @classmethod
    def window_resize(cls, target: Union[str, int], width: int, height: int) -> Dict[str, Any]:
        """Resizes the specified window to given dimensions."""
        try:
            import win32gui

            hwnd = target if isinstance(target, int) else (cls.window_find(str(target)).get("data") or {}).get("hwnd")
            if not hwnd or not win32gui.IsWindow(hwnd):
                return {"success": False, "action": "window_resize", "target": str(target), "error": "Window not found", "summary": f"Window '{target}' not found.", "data": None}

            rect = win32gui.GetWindowRect(hwnd)
            win32gui.MoveWindow(hwnd, rect[0], rect[1], int(width), int(height), True)
            return {"success": True, "action": "window_resize", "target": str(target), "error": None, "summary": f"Resized window '{target}' to {width}x{height}", "data": {"width": width, "height": height}}
        except Exception as e:
            return {"success": False, "action": "window_resize", "target": str(target), "error": str(e), "summary": f"Failed to resize window: {e}", "data": None}

    @classmethod
    def window_move(cls, target: Union[str, int], x: int, y: int) -> Dict[str, Any]:
        """Moves window to top-left coordinate (x, y)."""
        try:
            import win32gui

            hwnd = target if isinstance(target, int) else (cls.window_find(str(target)).get("data") or {}).get("hwnd")
            if not hwnd or not win32gui.IsWindow(hwnd):
                return {"success": False, "action": "window_move", "target": str(target), "error": "Window not found", "summary": f"Window '{target}' not found.", "data": None}

            rect = win32gui.GetWindowRect(hwnd)
            w = rect[2] - rect[0]
            h = rect[3] - rect[1]
            win32gui.MoveWindow(hwnd, int(x), int(y), w, h, True)
            return {"success": True, "action": "window_move", "target": str(target), "error": None, "summary": f"Moved window '{target}' to ({x}, {y})", "data": {"x": x, "y": y}}
        except Exception as e:
            return {"success": False, "action": "window_move", "target": str(target), "error": str(e), "summary": f"Failed to move window: {e}", "data": None}

    # ──────────────── CLIPBOARD MANAGEMENT ────────────────

    @staticmethod
    def clipboard_read() -> Dict[str, Any]:
        """Reads plain text from Windows clipboard."""
        try:
            import win32clipboard
            import win32con

            win32clipboard.OpenClipboard()
            text = ""
            if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
                text = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
            win32clipboard.CloseClipboard()

            return {
                "success": True,
                "action": "clipboard_read",
                "target": "clipboard",
                "error": None,
                "summary": f"Read {len(text)} characters from clipboard.",
                "data": {"text": text}
            }
        except Exception as e:
            try:
                import win32clipboard
                win32clipboard.CloseClipboard()
            except Exception:
                pass
            return {
                "success": False,
                "action": "clipboard_read",
                "target": "clipboard",
                "error": str(e),
                "summary": f"Failed to read clipboard: {e}",
                "data": None
            }

    @staticmethod
    def clipboard_write(text: str) -> Dict[str, Any]:
        """Copies plain text to Windows clipboard."""
        try:
            import win32clipboard
            import win32con

            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, str(text))
            win32clipboard.CloseClipboard()

            return {
                "success": True,
                "action": "clipboard_write",
                "target": f"{len(text)} characters",
                "error": None,
                "summary": f"Copied {len(text)} characters to clipboard.",
                "data": {"length": len(text)}
            }
        except Exception as e:
            try:
                import win32clipboard
                win32clipboard.CloseClipboard()
            except Exception:
                pass
            return {
                "success": False,
                "action": "clipboard_write",
                "target": "clipboard",
                "error": str(e),
                "summary": f"Failed to write to clipboard: {e}",
                "data": None
            }

    # ──────────────── APPLICATION MANAGEMENT ────────────────

    @staticmethod
    def app_launch(app_name: str, args: str = "") -> Dict[str, Any]:
        """Launches an application and verifies process launch."""
        from core.app_launcher import AppLauncher
        try:
            res = AppLauncher.launch_app(app_name)
            return {
                "success": res.get("status") == "success",
                "action": "app_launch",
                "target": app_name,
                "error": None if res.get("status") == "success" else res.get("message"),
                "summary": res.get("message", f"Launched {app_name}"),
                "data": res
            }
        except Exception as e:
            return {
                "success": False,
                "action": "app_launch",
                "target": app_name,
                "error": str(e),
                "summary": f"Failed to launch {app_name}: {e}",
                "data": None
            }

    @staticmethod
    def app_close(app_name: str) -> Dict[str, Any]:
        """Closes all processes belonging to an application name."""
        q = app_name.lower().replace(".exe", "").strip()
        killed = 0
        try:
            for proc in psutil.process_iter(['pid', 'name']):
                pname = (proc.info.get('name') or '').lower()
                if q in pname or pname.startswith(q):
                    try:
                        proc.terminate()
                        killed += 1
                    except Exception:
                        pass
            return {
                "success": killed > 0,
                "action": "app_close",
                "target": app_name,
                "error": None if killed > 0 else f"No running process matching '{app_name}'",
                "summary": f"Terminated {killed} process(es) for '{app_name}'" if killed > 0 else f"No active process found for '{app_name}'",
                "data": {"terminated_count": killed}
            }
        except Exception as e:
            return {
                "success": False,
                "action": "app_close",
                "target": app_name,
                "error": str(e),
                "summary": f"Failed to close {app_name}: {e}",
                "data": None
            }

    @staticmethod
    def app_list_running() -> Dict[str, Any]:
        """Lists active running application processes on system."""
        apps = set()
        try:
            for proc in psutil.process_iter(['name']):
                name = proc.info.get('name')
                if name and not name.lower().startswith(('svchost', 'system', 'registry', 'smss', 'csrss')):
                    apps.add(name)
            sorted_apps = sorted(list(apps))
            return {
                "success": True,
                "action": "app_list_running",
                "target": f"{len(sorted_apps)} apps",
                "error": None,
                "summary": f"Found {len(sorted_apps)} running processes.",
                "data": sorted_apps
            }
        except Exception as e:
            return {
                "success": False,
                "action": "app_list_running",
                "target": "",
                "error": str(e),
                "summary": f"Failed to list processes: {e}",
                "data": []
            }
