"""
Persistent Stateful REPL Execution Engine for JARVIS.

Maintains long-running interactive subprocesses for Python and PowerShell,
allowing variables, imports, functions, and working directory state to persist
across multiple sequential execution calls.
"""

import os
import sys
import re
import time
import uuid
import tempfile
import threading
import subprocess
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

SENTINEL_MARKER = "__JARVIS_EXEC_DONE__"
MAX_OUTPUT_LENGTH = 8000


def _peek_pipe(stream) -> int:
    """
    Checks how many bytes are currently available to read from the pipe without blocking.
    Uses Win32 PeekNamedPipe on Windows, and select on POSIX systems.
    """
    if stream is None or stream.closed:
        return 0
    try:
        fd = stream.fileno()
    except Exception:
        return 0

    if sys.platform == "win32":
        try:
            import msvcrt
            import ctypes
            from ctypes import wintypes

            handle = msvcrt.get_osfhandle(fd)
            avail = wintypes.DWORD()
            success = ctypes.windll.kernel32.PeekNamedPipe(
                wintypes.HANDLE(handle),
                None,
                0,
                None,
                ctypes.byref(avail),
                None
            )
            return avail.value if success else 0
        except Exception:
            return 0
    else:
        try:
            import select
            r, _, _ = select.select([fd], [], [], 0)
            return 65536 if r else 0
        except Exception:
            return 0


def _truncate_output(text: str, max_len: int = MAX_OUTPUT_LENGTH) -> str:
    """Truncates output to max_len characters with a notice if exceeded."""
    if not text:
        return ""
    if len(text) > max_len:
        suffix = "\n... [Output truncated to 8000 characters]"
        if max_len > len(suffix):
            return text[:max_len - len(suffix)] + suffix
        return text[:max_len]
    return text


class PersistentREPL:
    """
    Maintains a long-running interactive subprocess for Python or PowerShell.

    Attributes:
        lang: Target language ('python' or 'powershell').
        timeout: Default execution timeout in seconds.
    """

    def __init__(self, lang: str = "python", timeout: int = 30):
        """
        Initializes the persistent REPL session.

        Args:
            lang: Language choice ('python' or 'powershell').
            timeout: Default timeout in seconds for execution calls.
        """
        lang_normalized = lang.lower().strip()
        if lang_normalized not in ("python", "powershell"):
            raise ValueError(f"Unsupported language '{lang}'. Must be 'python' or 'powershell'.")

        self.lang = lang_normalized
        self.timeout = timeout
        self._lock = threading.RLock()
        self._proc: Optional[subprocess.Popen] = None
        self._seq = 0
        self._session_id = uuid.uuid4().hex[:8]
        self._start_process()

    def _start_process(self):
        """Spawns the interactive subprocess and consumes any startup banner."""
        with self._lock:
            self._kill_process()

            env = os.environ.copy()
            if self.lang == "python":
                env["PYTHONUNBUFFERED"] = "1"
                env["PYTHONIOENCODING"] = "utf-8"
                cmd = [sys.executable, "-u", "-i"]
                try:
                    self._proc = subprocess.Popen(
                        cmd,
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        bufsize=0,
                        env=env
                    )
                except Exception as e:
                    logger.error(f"Failed to spawn Python REPL: {e}")
                    raise RuntimeError(f"Failed to spawn Python REPL: {e}")

                init_marker = f"__JARVIS_INIT_{self._session_id}__"
                init_cmd = f"print('{init_marker}')\n".encode("utf-8")
                try:
                    self._proc.stdin.write(init_cmd)
                    self._proc.stdin.flush()
                except Exception as e:
                    self._kill_process()
                    raise RuntimeError(f"Failed writing init command to Python REPL: {e}")

                if not self._wait_for_sentinel(init_marker, timeout=15):
                    self._kill_process()
                    raise RuntimeError("Python REPL startup timed out waiting for init marker.")

            elif self.lang == "powershell":
                cmd = ["powershell", "-NoProfile", "-NoExit", "-Command", "-"]
                try:
                    self._proc = subprocess.Popen(
                        cmd,
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        bufsize=0,
                        env=env
                    )
                except Exception as e:
                    logger.error(f"Failed to spawn PowerShell REPL: {e}")
                    raise RuntimeError(f"Failed to spawn PowerShell REPL: {e}")

                init_marker = f"__JARVIS_INIT_{self._session_id}__"
                init_cmd = (
                    "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; "
                    "[Console]::InputEncoding = [System.Text.Encoding]::UTF8; "
                    "Remove-Module PSReadLine -ErrorAction SilentlyContinue; "
                    f"Write-Host '{init_marker}'\n"
                ).encode("utf-8")
                try:
                    self._proc.stdin.write(init_cmd)
                    self._proc.stdin.flush()
                except Exception as e:
                    self._kill_process()
                    raise RuntimeError(f"Failed writing init command to PowerShell REPL: {e}")

                if not self._wait_for_sentinel(init_marker, timeout=15):
                    self._kill_process()
                    raise RuntimeError("PowerShell REPL startup timed out waiting for init marker.")

    def _wait_for_sentinel(self, sentinel: str, timeout: float = 15.0) -> bool:
        """Reads and discards output until the specified sentinel appears on stdout."""
        start = time.perf_counter()
        accum = bytearray()

        while True:
            if time.perf_counter() - start > timeout:
                return False

            if self._proc is None or self._proc.poll() is not None:
                return False

            avail_out = _peek_pipe(self._proc.stdout)
            if avail_out > 0:
                try:
                    chunk = os.read(self._proc.stdout.fileno(), min(avail_out, 65536))
                    if chunk:
                        accum.extend(chunk)
                        text = accum.decode("utf-8", errors="replace")
                        if sentinel in text:
                            return True
                except (OSError, ValueError):
                    pass

            avail_err = _peek_pipe(self._proc.stderr)
            if avail_err > 0:
                try:
                    os.read(self._proc.stderr.fileno(), min(avail_err, 65536))
                except (OSError, ValueError):
                    pass

            time.sleep(0.005)

    def is_alive(self) -> bool:
        """Checks if the underlying subprocess is still active and running."""
        with self._lock:
            if self._proc is None:
                return False
            return self._proc.poll() is None

    def execute(self, code: str, timeout: Optional[int] = None) -> Dict[str, Any]:
        """
        Executes code in the persistent REPL environment.

        Args:
            code: Code string to execute.
            timeout: Optional execution timeout in seconds. Defaults to self.timeout.

        Returns:
            Dictionary with keys:
                - success (bool): True if execution succeeded without uncaught errors.
                - stdout (str): Standard output produced, truncated to 8000 chars.
                - stderr (str): Standard error output produced, truncated to 8000 chars.
                - returncode (int): 0 on success, non-zero on error/exit.
                - duration (float): Execution duration in seconds.
        """
        with self._lock:
            timeout_val = timeout if timeout is not None else self.timeout
            start_time = time.perf_counter()

            # Ensure subprocess is alive or auto-restart
            if not self.is_alive():
                try:
                    self._start_process()
                except Exception as e:
                    return {
                        "success": False,
                        "stdout": "",
                        "stderr": f"REPL subprocess is not alive and failed to restart: {e}",
                        "returncode": -1,
                        "duration": 0.0,
                    }

            # Return immediately on empty code
            if not code or not code.strip():
                return {
                    "success": True,
                    "stdout": "",
                    "stderr": "",
                    "returncode": 0,
                    "duration": round(time.perf_counter() - start_time, 4),
                }

            self._seq += 1
            seq = self._seq
            sentinel_marker = SENTINEL_MARKER
            temp_file_path: Optional[str] = None

            try:
                if self.lang == "python":
                    temp_file = tempfile.NamedTemporaryFile(
                        mode="w",
                        suffix=".py",
                        delete=False,
                        encoding="utf-8"
                    )
                    temp_file_path = temp_file.name
                    temp_file.write(code)
                    temp_file.flush()
                    temp_file.close()

                    safe_path = temp_file_path.replace("\\", "/")
                    ok_var = f"_jarvis_ok_{self._session_id}_{seq}"

                    payload = (
                        f"{ok_var} = False\n"
                        f"exec(open('{safe_path}', encoding='utf-8').read()); {ok_var} = True\n"
                        f"print('{sentinel_marker}', int({ok_var}))\n"
                    )
                    self._proc.stdin.write(payload.encode("utf-8"))
                    self._proc.stdin.flush()

                elif self.lang == "powershell":
                    clean_code = code.strip()
                    payload = (
                        f"$Error.Clear()\n"
                        f"{clean_code}\n"
                        f"Write-Host '{sentinel_marker}' $(if ($Error.Count -eq 0) {{ '1' }} else {{ '0' }})\n"
                    )
                    self._proc.stdin.write(payload.encode("utf-8"))
                    self._proc.stdin.flush()

            except Exception as e:
                self._kill_process()
                self._cleanup_temp_file(temp_file_path)
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": f"Failed to send code to {self.lang} process: {e}",
                    "returncode": -1,
                    "duration": round(time.perf_counter() - start_time, 4),
                }

            stdout_bytes = bytearray()
            stderr_bytes = bytearray()
            sentinel_found = False

            while True:
                elapsed = time.perf_counter() - start_time
                if timeout_val is not None and elapsed > timeout_val:
                    # Timeout exceeded: terminate process per rule #6
                    self._kill_process()
                    duration = round(elapsed, 4)
                    out_str = _truncate_output(stdout_bytes.decode("utf-8", errors="replace").rstrip("\r\n"))
                    err_str = f"Execution timed out after {timeout_val} seconds"
                    self._cleanup_temp_file(temp_file_path)
                    return {
                        "success": False,
                        "stdout": out_str,
                        "stderr": err_str,
                        "returncode": -1,
                        "duration": duration,
                    }

                poll_code = self._proc.poll()
                if poll_code is not None:
                    # Subprocess terminated unexpectedly or due to exit()
                    self._drain_all(stdout_bytes, stderr_bytes)
                    duration = round(time.perf_counter() - start_time, 4)
                    out_text = stdout_bytes.decode("utf-8", errors="replace")
                    err_text = stderr_bytes.decode("utf-8", errors="replace")

                    if sentinel_marker in out_text:
                        parts = out_text.split(sentinel_marker, 1)
                        out_text = parts[0]

                    out_text = _truncate_output(out_text.replace("\r\n", "\n").rstrip("\r\n"))
                    err_text = _truncate_output(err_text.replace("\r\n", "\n").rstrip("\r\n"))
                    self._cleanup_temp_file(temp_file_path)

                    return {
                        "success": (poll_code == 0),
                        "stdout": out_text,
                        "stderr": err_text,
                        "returncode": poll_code,
                        "duration": duration,
                    }

                # Non-blocking read stdout
                avail_out = _peek_pipe(self._proc.stdout)
                if avail_out > 0:
                    try:
                        chunk = os.read(self._proc.stdout.fileno(), min(avail_out, 65536))
                        if chunk:
                            stdout_bytes.extend(chunk)
                            text_so_far = stdout_bytes.decode("utf-8", errors="replace")
                            if sentinel_marker in text_so_far:
                                idx = text_so_far.rfind(sentinel_marker)
                                if "\n" in text_so_far[idx:]:
                                    sentinel_found = True
                    except (OSError, ValueError):
                        pass

                # Non-blocking read stderr
                avail_err = _peek_pipe(self._proc.stderr)
                if avail_err > 0:
                    try:
                        chunk = os.read(self._proc.stderr.fileno(), min(avail_err, 65536))
                        if chunk:
                            stderr_bytes.extend(chunk)
                    except (OSError, ValueError):
                        pass

                if sentinel_found:
                    break

                time.sleep(0.005)

            # Drain any trailing stderr bytes
            time.sleep(0.01)
            self._drain_stderr(stderr_bytes)

            duration = round(time.perf_counter() - start_time, 4)
            raw_stdout = stdout_bytes.decode("utf-8", errors="replace")
            raw_stderr = stderr_bytes.decode("utf-8", errors="replace")

            user_stdout = ""
            success = True
            returncode = 0

            if sentinel_marker in raw_stdout:
                idx = raw_stdout.rfind(sentinel_marker)
                user_stdout = raw_stdout[:idx]
                sentinel_tail = raw_stdout[idx + len(sentinel_marker):].strip()

                tokens = sentinel_tail.split()
                first_token = tokens[0].lower() if tokens else ""

                if first_token in ("1", "true"):
                    success = True
                    returncode = 0
                elif first_token in ("0", "false"):
                    success = False
                    returncode = 1
                else:
                    if raw_stderr.strip():
                        success = False
                        returncode = 1
                    else:
                        success = True
                        returncode = 0
            else:
                user_stdout = raw_stdout

            self._cleanup_temp_file(temp_file_path)

            user_stdout = user_stdout.replace("\r\n", "\n").rstrip("\r\n")
            user_stderr = raw_stderr.replace("\r\n", "\n").rstrip("\r\n")

            # Filter interactive Python REPL prompts (>>> and ...) from stderr
            if self.lang == "python" and user_stderr:
                filtered_lines = [
                    line for line in user_stderr.split("\n")
                    if not re.match(r"^(?:>>>|\.\.\.|\s)*$", line)
                ]
                user_stderr = "\n".join(filtered_lines).strip()

            user_stdout = _truncate_output(user_stdout)
            user_stderr = _truncate_output(user_stderr)

            return {
                "success": success,
                "stdout": user_stdout,
                "stderr": user_stderr,
                "returncode": returncode,
                "duration": duration,
            }

    def _drain_stderr(self, stderr_bytes: bytearray):
        """Drains remaining bytes from stderr pipe."""
        if self._proc and self._proc.stderr and not self._proc.stderr.closed:
            for _ in range(10):
                avail = _peek_pipe(self._proc.stderr)
                if avail > 0:
                    try:
                        c = os.read(self._proc.stderr.fileno(), min(avail, 65536))
                        if c:
                            stderr_bytes.extend(c)
                            continue
                    except (OSError, ValueError):
                        pass
                break

    def _drain_all(self, stdout_bytes: bytearray, stderr_bytes: bytearray, max_iterations: int = 50):
        """Drains any remaining bytes from both stdout and stderr pipes."""
        for _ in range(max_iterations):
            read_any = False
            if self._proc and self._proc.stdout and not self._proc.stdout.closed:
                avail = _peek_pipe(self._proc.stdout)
                if avail > 0:
                    try:
                        c = os.read(self._proc.stdout.fileno(), min(avail, 65536))
                        if c:
                            stdout_bytes.extend(c)
                            read_any = True
                    except (OSError, ValueError):
                        pass

            if self._proc and self._proc.stderr and not self._proc.stderr.closed:
                avail = _peek_pipe(self._proc.stderr)
                if avail > 0:
                    try:
                        c = os.read(self._proc.stderr.fileno(), min(avail, 65536))
                        if c:
                            stderr_bytes.extend(c)
                            read_any = True
                    except (OSError, ValueError):
                        pass

            if not read_any:
                break
            time.sleep(0.005)

    def _cleanup_temp_file(self, path: Optional[str]):
        """Safely removes a temporary execution file."""
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass

    def reset(self):
        """Kills and restarts the persistent sub-process."""
        with self._lock:
            self._kill_process()
            self._start_process()

    def close(self):
        """Terminates the persistent sub-process and releases resources."""
        with self._lock:
            self._kill_process()

    def _kill_process(self):
        """Internal helper to terminate the process and close open pipe handles."""
        if self._proc is not None:
            try:
                if self._proc.poll() is None:
                    self._proc.kill()
                    self._proc.wait(timeout=2)
            except Exception:
                pass
            finally:
                try:
                    if self._proc.stdin and not self._proc.stdin.closed:
                        self._proc.stdin.close()
                except Exception:
                    pass
                try:
                    if self._proc.stdout and not self._proc.stdout.closed:
                        self._proc.stdout.close()
                except Exception:
                    pass
                try:
                    if self._proc.stderr and not self._proc.stderr.closed:
                        self._proc.stderr.close()
                except Exception:
                    pass
                self._proc = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

    def __repr__(self) -> str:
        status = "running" if self.is_alive() else "stopped"
        pid = self._proc.pid if self._proc and self.is_alive() else None
        return f"<PersistentREPL lang='{self.lang}' status='{status}' pid={pid}>"
