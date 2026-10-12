"""
System Tray & Global Hotkey Manager for JARVIS AI Assistant.
Provides native Windows notification area (System Tray) icon with:
- Show JARVIS / Restore Window
- Floating Mini Robot Mode
- Voice Listening Trigger
- Settings
- Exit
- Global Alt+J Hotkey Listener
- Windows Startup (Run key) management
"""

import os
import sys
import time
import winreg
import threading
import ctypes
from ctypes import wintypes
from typing import Callable, Optional

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

RUN_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_RUN_NAME = "JARVIS_Assistant"

class SystemTrayManager:
    """Manages the Windows notification tray icon and global hotkey loop."""

    def __init__(self,
                 on_show: Optional[Callable] = None,
                 on_mini: Optional[Callable] = None,
                 on_voice: Optional[Callable] = None,
                 on_settings: Optional[Callable] = None,
                 on_exit: Optional[Callable] = None):
        self.on_show = on_show
        self.on_mini = on_mini
        self.on_voice = on_voice
        self.on_settings = on_settings
        self.on_exit = on_exit

        self._hwnd = None
        self._thread = None
        self._running = False
        self._hotkey_id = 1001
        self._voice_hotkey_id = 1002

    @staticmethod
    def is_startup_enabled() -> bool:
        """Checks if JARVIS is configured to start with Windows."""
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0, winreg.KEY_READ) as key:
                val, _ = winreg.QueryValueEx(key, APP_RUN_NAME)
                return bool(val)
        except Exception:
            return False

    @staticmethod
    def set_startup_enabled(enabled: bool) -> bool:
        """Enables or disables automatic startup with Windows."""
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0, winreg.KEY_SET_VALUE) as key:
                if enabled:
                    py_exe = sys.executable
                    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                    run_cmd = f'"{py_exe}" "{os.path.join(base_dir, "main.py")}"'
                    winreg.SetValueEx(key, APP_RUN_NAME, 0, winreg.REG_SZ, run_cmd)
                else:
                    try:
                        winreg.DeleteValue(key, APP_RUN_NAME)
                    except FileNotFoundError:
                        pass
            return True
        except Exception as e:
            print(f"[SystemTrayManager] set_startup_enabled error: {e}")
            return False

    def start(self):
        """Starts the background tray message loop and global hotkey."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_tray_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Removes the tray icon and cleans up."""
        self._running = False
        if self._hwnd:
            try:
                import win32gui
                import win32con
                win32gui.PostMessage(self._hwnd, win32con.WM_CLOSE, 0, 0)
            except Exception:
                pass

    def _run_tray_loop(self):
        """Runs native Win32 window message loop for Tray and Hotkey."""
        try:
            import win32gui
            import win32con

            WM_TRAY_CALLBACK = win32con.WM_USER + 20

            # Register hidden helper window class
            wc = win32gui.WNDCLASS()
            wc.hInstance = kernel32.GetModuleHandleW(None)
            wc.lpszClassName = "JARVIS_Tray_Helper_Class"

            def _wndproc(hwnd, msg, wparam, lparam):
                if msg == WM_TRAY_CALLBACK:
                    if lparam == win32con.WM_RBUTTONUP:
                        # Show context menu
                        menu = win32gui.CreatePopupMenu()
                        win32gui.AppendMenu(menu, win32con.MF_STRING, 101, "🚀 Open JARVIS")
                        win32gui.AppendMenu(menu, win32con.MF_STRING, 102, "🤖 Floating Mini Robot")
                        win32gui.AppendMenu(menu, win32con.MF_STRING, 103, "🎙️ Voice Listening")
                        win32gui.AppendMenu(menu, win32con.MF_SEPARATOR, 0, "")
                        win32gui.AppendMenu(menu, win32con.MF_STRING, 104, "⚙️ Settings")
                        win32gui.AppendMenu(menu, win32con.MF_STRING, 105, "❌ Exit")

                        pt = wintypes.POINT()
                        user32.GetCursorPos(ctypes.byref(pt))
                        user32.SetForegroundWindow(hwnd)
                        cmd = win32gui.TrackPopupMenu(
                            menu,
                            win32con.TPM_RETURNCMD | win32con.TPM_NONOTIFY,
                            pt.x, pt.y, 0, hwnd, None
                        )
                        win32gui.DestroyMenu(menu)

                        if cmd == 101 and self.on_show:
                            self.on_show()
                        elif cmd == 102 and self.on_mini:
                            self.on_mini()
                        elif cmd == 103 and self.on_voice:
                            self.on_voice()
                        elif cmd == 104 and self.on_settings:
                            self.on_settings()
                        elif cmd == 105 and self.on_exit:
                            self.on_exit()
                        return 0

                    elif lparam in (win32con.WM_LBUTTONUP, win32con.WM_LBUTTONDBLCLK):
                        # Left click toggles show / mini
                        if self.on_show:
                            self.on_show()
                        return 0

                elif msg == win32con.WM_HOTKEY:
                    if wparam == self._hotkey_id:
                        # Global Alt+J triggered anywhere in Windows: toggles Mini HUD / window
                        if self.on_mini:
                            self.on_mini()
                        elif self.on_show:
                            self.on_show()
                    elif wparam == self._voice_hotkey_id:
                        # Global Ctrl+J triggered anywhere in Windows: toggles Voice Listening on/off
                        if self.on_voice:
                            self.on_voice()
                    return 0

                elif msg == win32con.WM_DESTROY:
                    # Remove notification icon
                    try:
                        nid = (hwnd, 0)
                        win32gui.Shell_NotifyIcon(win32gui.NIM_DELETE, nid)
                    except Exception:
                        pass
                    user32.UnregisterHotKey(hwnd, self._hotkey_id)
                    user32.UnregisterHotKey(hwnd, self._voice_hotkey_id)
                    win32gui.PostQuitMessage(0)
                    return 0

                return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

            wc.lpfnWndProc = _wndproc
            try:
                class_atom = win32gui.RegisterClass(wc)
            except Exception:
                class_atom = win32gui.GetClassInfo(wc.hInstance, wc.lpszClassName)

            self._hwnd = win32gui.CreateWindow(
                wc.lpszClassName,
                "JARVIS_Tray_Window",
                0, 0, 0, 0, 0, 0, 0, wc.hInstance, None
            )

            # Register Global Hotkey Alt+J (Mini HUD toggle)
            # MOD_ALT = 0x0001, MOD_NOREPEAT = 0x4000, 'J' = 0x4A
            user32.RegisterHotKey(self._hwnd, self._hotkey_id, 0x0001 | 0x4000, 0x4A)

            # Register Global Hotkey Ctrl+J (Voice Listening toggle)
            # MOD_CONTROL = 0x0002, MOD_NOREPEAT = 0x4000, 'J' = 0x4A
            user32.RegisterHotKey(self._hwnd, self._voice_hotkey_id, 0x0002 | 0x4000, 0x4A)

            # Add Tray Icon
            hicon = win32gui.LoadIcon(0, win32con.IDI_APPLICATION)
            nid = (
                self._hwnd,
                0,
                win32gui.NIF_ICON | win32gui.NIF_MESSAGE | win32gui.NIF_TIP,
                WM_TRAY_CALLBACK,
                hicon,
                "JARVIS AI Assistant"
            )
            win32gui.Shell_NotifyIcon(win32gui.NIM_ADD, nid)

            # Message pump
            win32gui.PumpMessages()

        except Exception as e:
            print(f"[SystemTrayManager] Tray loop error: {e}")
