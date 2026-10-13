"""
JARVIS Automatic Dependency Resolver
=====================================
Detects missing Python packages and CLI binaries from stderr/traceback text
and automatically installs them via pip or winget.
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
import sys
from typing import Any, Dict, Optional

logger = logging.getLogger("JARVIS.PackageResolver")

# Common import names mapped to their respective PyPI package distribution names
COMMON_PACKAGE_ALIASES: dict[str, str] = {
    # Vision & Image Processing
    "cv2": "opencv-python",
    "PIL": "Pillow",
    "skimage": "scikit-image",
    "imageio": "imageio",
    "imutils": "imutils",

    # Documents & Office
    "yaml": "PyYAML",
    "docx": "python-docx",
    "pptx": "python-pptx",
    "fitz": "PyMuPDF",
    "pdfplumber": "pdfplumber",
    "pypdf": "pypdf",
    "PyPDF2": "PyPDF2",
    "openpyxl": "openpyxl",
    "xlrd": "xlrd",
    "xlsxwriter": "XlsxWriter",

    # Web & Scraping
    "bs4": "beautifulsoup4",
    "requests": "requests",
    "urllib3": "urllib3",
    "playwright": "playwright",
    "selenium": "selenium",
    "aiohttp": "aiohttp",
    "httpx": "httpx",

    # Machine Learning & Scientific
    "sklearn": "scikit-learn",
    "scipy": "scipy",
    "numpy": "numpy",
    "pandas": "pandas",
    "matplotlib": "matplotlib",
    "mpl_toolkits": "matplotlib",
    "seaborn": "seaborn",
    "torch": "torch",
    "torchvision": "torchvision",
    "torchaudio": "torchaudio",
    "transformers": "transformers",

    # Audio & Voice & Media
    "sounddevice": "sounddevice",
    "soundfile": "soundfile",
    "pyaudio": "PyAudio",
    "speech_recognition": "SpeechRecognition",
    "moviepy": "moviepy",
    "pygame": "pygame",
    "librosa": "librosa",
    "pydub": "pydub",

    # System & GUI
    "gi": "PyGObject",
    "wx": "wxPython",
    "serial": "pyserial",
    "usb": "pyusb",
    "magic": "python-magic-bin",
    "win32api": "pywin32",
    "win32con": "pywin32",
    "win32gui": "pywin32",
    "win32com": "pywin32",
    "pythoncom": "pywin32",
    "pynput": "pynput",
    "pyautogui": "pyautogui",
    "keyboard": "keyboard",
    "mouse": "mouse",

    # Utilities & Auth & Security
    "Crypto": "pycryptodome",
    "cryptography": "cryptography",
    "dateutil": "python-dateutil",
    "dotenv": "python-dotenv",
    "jwt": "PyJWT",
    "jose": "python-jose",
    "psutil": "psutil",
    "pydantic": "pydantic",

    # Database
    "psycopg2": "psycopg2-binary",
    "sqlalchemy": "SQLAlchemy",
    "pymongo": "pymongo",
    "redis": "redis",

    # AI / LLM APIs
    "google.generativeai": "google-generativeai",
    "google": "google-generativeai",
    "openai": "openai",
    "anthropic": "anthropic",
    "groq": "groq",
}

# Mapping of CLI binary commands to Windows winget package IDs
WINGET_BINARY_MAP: dict[str, str] = {
    "ffmpeg": "Gyan.FFmpeg",
    "ffprobe": "Gyan.FFmpeg",
    "git": "Git.Git",
    "node": "OpenJS.NodeJS",
    "npm": "OpenJS.NodeJS",
    "npx": "OpenJS.NodeJS",
    "python": "Python.Python.3.11",
    "pip": "Python.Python.3.11",
    "curl": "cURL.cURL",
    "wget": "JernejSimoncic.Wget",
    "7z": "7zip.7zip",
    "rustc": "Rustlang.Rustup",
    "cargo": "Rustlang.Rustup",
    "go": "GoLang.Go",
    "docker": "Docker.DockerDesktop",
    "tesseract": "UB-Mannheim.Tesseract-OCR",
    "gh": "GitHub.cli",
    "yarn": "Yarn.Yarn",
    "make": "GnuWin32.Make",
    "pandoc": "JohnMacFarlane.Pandoc",
    "graphviz": "Graphviz.Graphviz",
    "dot": "Graphviz.Graphviz",
    "vlc": "VideoLAN.VLC",
    "jq": "jqlang.jq",
    "neovim": "Neovim.Neovim",
    "nvim": "Neovim.Neovim",
}

# Regular expression to strip ANSI escape codes
_ANSI_REGEX = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


def _clean_text(text: str) -> str:
    """Strip ANSI escape sequences from text."""
    if not text:
        return ""
    return _ANSI_REGEX.sub("", text)


def _resolve_alias(module_name: str) -> str:
    """Resolve an import/module name to the appropriate PyPI package name."""
    if not module_name:
        return ""

    # Direct match in alias map
    if module_name in COMMON_PACKAGE_ALIASES:
        return COMMON_PACKAGE_ALIASES[module_name]

    # Case-insensitive match in alias map
    module_lower = module_name.lower()
    for k, v in COMMON_PACKAGE_ALIASES.items():
        if k.lower() == module_lower:
            return v

    # Check top-level package if dotted (e.g. 'PIL.Image' -> 'PIL')
    if "." in module_name:
        top_level = module_name.split(".")[0]
        if top_level in COMMON_PACKAGE_ALIASES:
            return COMMON_PACKAGE_ALIASES[top_level]
        top_lower = top_level.lower()
        for k, v in COMMON_PACKAGE_ALIASES.items():
            if k.lower() == top_lower:
                return v
        return top_level

    return module_name


class PackageResolver:
    """
    Automatic dependency resolver for JARVIS.
    Detects missing Python dependencies and system binaries, providing
    automated installation capabilities via pip and winget.
    """

    COMMON_PACKAGE_ALIASES = COMMON_PACKAGE_ALIASES
    WINGET_BINARY_MAP = WINGET_BINARY_MAP

    @staticmethod
    def detect_missing_package(stderr: str) -> str | None:
        """
        Parses stderr/traceback text to detect missing Python packages.
        Looks for patterns like:
          - ModuleNotFoundError: No module named 'xyz'
          - ImportError: No module named 'xyz'
          - 'xyz' is not recognized as an internal or external command (for CLI tools)

        Returns the package name or None.
        """
        if not stderr or not isinstance(stderr, str):
            return None

        clean_err = _clean_text(stderr)

        # 1. ModuleNotFoundError: No module named 'xyz'
        m_mod = re.search(
            r"ModuleNotFoundError:\s*No module named\s+['\"]?([a-zA-Z0-9_\.]+)['\"]?",
            clean_err,
            re.IGNORECASE,
        )
        if m_mod:
            raw_pkg = m_mod.group(1).strip()
            return _resolve_alias(raw_pkg)

        # 2. ImportError: No module named 'xyz'
        m_imp = re.search(
            r"ImportError:\s*No module named\s+['\"]?([a-zA-Z0-9_\.]+)['\"]?",
            clean_err,
            re.IGNORECASE,
        )
        if m_imp:
            raw_pkg = m_imp.group(1).strip()
            return _resolve_alias(raw_pkg)

        # 2b. ImportError: cannot import name 'abc' from 'xyz'
        m_from = re.search(
            r"ImportError:\s*cannot import name\s+['\"]?[a-zA-Z0-9_]+['\"]?\s+from\s+(?:partially initialized module\s+)?['\"]?([a-zA-Z0-9_\.]+)['\"]?",
            clean_err,
            re.IGNORECASE,
        )
        if m_from:
            raw_pkg = m_from.group(1).strip()
            return _resolve_alias(raw_pkg)

        # 2c. Generic "No module named 'xyz'"
        m_gen = re.search(
            r"No module named\s+['\"]([a-zA-Z0-9_\.]+)['\"]",
            clean_err,
            re.IGNORECASE,
        )
        if m_gen:
            raw_pkg = m_gen.group(1).strip()
            return _resolve_alias(raw_pkg)

        # 3. 'xyz' is not recognized as an internal or external command (for CLI tools)
        m_cmd = re.search(
            r"['\"]?([a-zA-Z0-9_\-\.]+)['\"]?\s+is not recognized as an internal or external command",
            clean_err,
            re.IGNORECASE,
        )
        if not m_cmd:
            m_cmd = re.search(
                r"The term\s+['\"]?([a-zA-Z0-9_\-\.]+)['\"]?\s+is not recognized",
                clean_err,
                re.IGNORECASE,
            )

        if m_cmd:
            cmd_name = m_cmd.group(1).strip()
            # If it's a known system binary handled by winget, let detect_missing_binary handle it
            if cmd_name.lower() in WINGET_BINARY_MAP:
                return None
            return _resolve_alias(cmd_name)

        return None

    @staticmethod
    def detect_missing_binary(stderr: str) -> str | None:
        """
        Detects missing CLI binaries from error messages like:
          - 'ffmpeg' is not recognized
          - 'ffmpeg' is not recognized as an internal or external command
          - FileNotFoundError: ... 'ffmpeg'
          - [WinError 2] The system cannot find the file specified: 'ffmpeg'

        Returns the binary name or None.
        """
        if not stderr or not isinstance(stderr, str):
            return None

        clean_err = _clean_text(stderr)

        # Check known winget binaries first for fast, exact detection
        for bin_name in WINGET_BINARY_MAP:
            escaped = re.escape(bin_name)
            patterns = [
                rf"['\"]?{escaped}(?:\.exe)?['\"]?\s+is not recognized",
                rf"The term\s+['\"]?{escaped}(?:\.exe)?['\"]?\s+is not recognized",
                rf"\b{escaped}(?:\.exe)?:\s*(?:command\s+)?not found\b",
                rf"FileNotFoundError:.*?\b{escaped}(?:\.exe)?\b",
                rf"\[WinError 2\].*?\b{escaped}(?:\.exe)?\b",
            ]
            for pat in patterns:
                if re.search(pat, clean_err, re.IGNORECASE):
                    return bin_name

        # General patterns for command not recognized
        general_patterns = [
            r"['\"]?([a-zA-Z0-9_\-\.]+)(?:\.exe)?['\"]?\s+is not recognized",
            r"The term\s+['\"]?([a-zA-Z0-9_\-\.]+)(?:\.exe)?['\"]?\s+is not recognized",
            r"([a-zA-Z0-9_\-\.]+)(?:\.exe)?:\s*(?:command\s+)?not found",
            r"FileNotFoundError:\s*\[Errno 2\]\s*No such file or directory:\s*['\"]([^'\"]+?)['\"]",
            r"\[WinError 2\]\s*The system cannot find the file specified(?::\s*['\"]?([^'\"\n]+?)['\"]?)?",
        ]

        for pat in general_patterns:
            m = re.search(pat, clean_err, re.IGNORECASE)
            if m and m.group(1):
                raw = m.group(1).strip().strip("'\"")
                base = os.path.basename(raw)
                if base.lower().endswith(".exe"):
                    base = base[:-4]
                if base:
                    return base

        return None

    @classmethod
    def install_python_package(cls, package_name: str, timeout: int = 60) -> dict[str, Any]:
        """
        Runs pip install {package_name} and returns:
          {"success": bool, "output": str, "error": str}
        """
        if not package_name or not isinstance(package_name, str):
            return {"success": False, "output": "", "error": "Invalid package name"}

        pkg_clean = package_name.strip().strip("'\"")
        resolved_pkg = _resolve_alias(pkg_clean)

        logger.info(f"Attempting to install Python package: {resolved_pkg}")

        # Prefer current python interpreter executable to ensure package is installed in current env
        cmd = [sys.executable, "-m", "pip", "install", resolved_pkg]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
            success = (result.returncode == 0)
            output = result.stdout or ""
            error = result.stderr if not success else ""

            if success:
                logger.info(f"Successfully installed Python package: {resolved_pkg}")
            else:
                logger.warning(f"Failed to install Python package {resolved_pkg}: {error}")

            return {
                "success": success,
                "output": output,
                "error": error,
            }
        except subprocess.TimeoutExpired:
            err_msg = f"Installation of '{resolved_pkg}' timed out after {timeout}s"
            logger.error(err_msg)
            return {"success": False, "output": "", "error": err_msg}
        except FileNotFoundError:
            # Fallback to direct 'pip' command if sys.executable cannot invoke pip
            try:
                cmd_fallback = ["pip", "install", resolved_pkg]
                result = subprocess.run(
                    cmd_fallback,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    check=False,
                )
                success = (result.returncode == 0)
                return {
                    "success": success,
                    "output": result.stdout or "",
                    "error": result.stderr if not success else "",
                }
            except Exception as ex:
                return {"success": False, "output": "", "error": str(ex)}
        except Exception as e:
            logger.error(f"Error installing Python package {resolved_pkg}: {e}")
            return {"success": False, "output": "", "error": str(e)}

    @classmethod
    def install_binary_winget(cls, binary_name: str, timeout: int = 120) -> dict[str, Any]:
        """
        Attempts to install via winget install {binary_name} with a default 120s timeout.
        Returns:
          {"success": bool, "output": str, "error": str}
        """
        if not binary_name or not isinstance(binary_name, str):
            return {"success": False, "output": "", "error": "Invalid binary name"}

        bin_clean = binary_name.strip().strip("'\"").lower()
        package_id = WINGET_BINARY_MAP.get(bin_clean, binary_name.strip())

        logger.info(f"Attempting to install binary via winget: {binary_name} (ID: {package_id})")

        # Use package ID if known, otherwise install by name
        if bin_clean in WINGET_BINARY_MAP:
            cmd = [
                "winget",
                "install",
                "--id",
                package_id,
                "-e",
                "--accept-source-agreements",
                "--accept-package-agreements",
            ]
        else:
            cmd = [
                "winget",
                "install",
                package_id,
                "--accept-source-agreements",
                "--accept-package-agreements",
            ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
            success = (result.returncode == 0)
            output = result.stdout or ""
            error = result.stderr if not success else ""

            if success:
                logger.info(f"Successfully installed binary via winget: {binary_name}")
            else:
                logger.warning(f"Failed to install binary {binary_name}: {error or output}")

            return {
                "success": success,
                "output": output,
                "error": error,
            }
        except subprocess.TimeoutExpired:
            err_msg = f"Winget installation of '{binary_name}' timed out after {timeout}s"
            logger.error(err_msg)
            return {"success": False, "output": "", "error": err_msg}
        except FileNotFoundError:
            err_msg = "winget command not found on the system"
            logger.error(err_msg)
            return {"success": False, "output": "", "error": err_msg}
        except Exception as e:
            logger.error(f"Error installing binary {binary_name}: {e}")
            return {"success": False, "output": "", "error": str(e)}

    @classmethod
    def auto_resolve(cls, stderr: str) -> dict[str, Any]:
        """
        Master method that:
          1. Checks for missing Python package -> installs it via pip
          2. Checks for missing binary -> installs via winget
          3. Returns {"resolved": bool, "package": str, "method": str, "output": str}
        """
        if not stderr or not isinstance(stderr, str):
            return {
                "resolved": False,
                "package": "",
                "method": "",
                "output": "No stderr content provided to analyze",
            }

        # 1. Check for missing Python package
        missing_pkg = cls.detect_missing_package(stderr)
        if missing_pkg:
            logger.info(f"Auto-resolve detected missing Python package: {missing_pkg}")
            res = cls.install_python_package(missing_pkg)
            if res.get("success"):
                return {
                    "resolved": True,
                    "package": missing_pkg,
                    "method": "pip",
                    "output": res.get("output", ""),
                }
            # If pip installation failed, try binary resolution as fallback
            logger.warning(f"Pip installation for {missing_pkg} failed; checking for binary fallback.")

        # 2. Check for missing binary
        missing_bin = cls.detect_missing_binary(stderr)
        if missing_bin:
            logger.info(f"Auto-resolve detected missing binary: {missing_bin}")
            res_bin = cls.install_binary_winget(missing_bin)
            if res_bin.get("success"):
                return {
                    "resolved": True,
                    "package": missing_bin,
                    "method": "winget",
                    "output": res_bin.get("output", ""),
                }
            return {
                "resolved": False,
                "package": missing_bin,
                "method": "winget",
                "output": res_bin.get("error") or res_bin.get("output", ""),
            }

        # If missing package was detected but installation failed and no binary was found
        if missing_pkg:
            return {
                "resolved": False,
                "package": missing_pkg,
                "method": "pip",
                "output": res.get("error") or res.get("output", ""),
            }

        # Neither package nor binary detected
        return {
            "resolved": False,
            "package": "",
            "method": "",
            "output": "No missing Python package or system binary detected in stderr",
        }
