import os
import re
import asyncio
import base64
import tempfile
import threading
from pathlib import Path

class VoiceEngine:
    """Manages Text-to-Speech generation and voice settings for Jarvis."""

    DEFAULT_VOICE = "en-GB-RyanNeural"  # Sophisticated British Jarvis tone

    def __init__(self, voice=DEFAULT_VOICE, enabled=True):
        self.voice = voice
        self.enabled = enabled
        self._lock = threading.Lock()

    def set_enabled(self, enabled: bool):
        self.enabled = bool(enabled)

    def is_enabled(self) -> bool:
        return self.enabled

    def set_voice(self, voice_name: str):
        self.voice = voice_name

    def clean_text_for_speech(self, text: str) -> str:
        """Strips markdown code blocks, tags, URLs, and symbols for clean spoken voice in English."""
        if not text:
            return ""

        # Normalize unicode hyphens, quotes, and symbols that can cause speech synthesis to choke
        replacements = {
            "\u2011": "-", "\u2010": "-", "\u2012": "-", "\u2013": "-", "\u2014": "--",
            "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
            "\u2026": "...", "\u00a0": " ", "\u2022": " ", "⚡": "", "✓": "", "✕": "", "🎙️": ""
        }
        for k, v in replacements.items():
            text = text.replace(k, v)

        # Remove code blocks ```...```
        cleaned = re.sub(r"```[\s\S]*?```", " [Code output omitted] ", text)
        # Remove tool tags [ACTION: ...] or [TOOL: ...]
        cleaned = re.sub(r"\[(?:ACTION|TOOL):\s*.*?\]", "", cleaned)
        # Remove suggestions [Suggestion: ...]
        cleaned = re.sub(r"\[Suggestion:[\s\S]*?\]", "", cleaned)
        # Remove document tags [DOCUMENT: ...]
        cleaned = re.sub(r"\[DOCUMENT:[\s\S]*?\]", "", cleaned)
        # Remove media tags [MEDIA: ...]
        cleaned = re.sub(r"\[MEDIA:[\s\S]*?\]", "", cleaned)
        # Remove markdown headers and formatting
        cleaned = re.sub(r"[#*_~`>]", "", cleaned)
        # Remove bullet markers
        cleaned = re.sub(r"^\s*[-*•]\s+", "", cleaned, flags=re.MULTILINE)
        # Remove URLs
        cleaned = re.sub(r"https?://\S+", "link", cleaned)
        # Normalize whitespace
        cleaned = re.sub(r"\s+", " ", cleaned).strip()

        # Limit spoken length so Jarvis doesn't drone on forever if user asked for a 20-page document
        if len(cleaned) > 400:
            # Speak the first 2-3 sentences
            sentences = re.split(r"(?<=[.!?])\s+", cleaned)
            summary = ""
            for s in sentences:
                if len(summary) + len(s) <= 350:
                    summary += (" " + s)
                else:
                    break
            if not summary.strip():
                summary = cleaned[:320]
            cleaned = summary.strip() + " I have displayed the full details on your screen, sir."

        return cleaned

    def synthesize_and_speak(self, text: str, play_audio: bool = False) -> str | None:
        """
        Single-pass neural speech synthesis:
        1. Synthesizes high-fidelity British voice audio (edge-tts) ONCE.
        2. Saves to a local cache file.
        3. Only plays directly to Windows sound device if play_audio=True (CLI/background mode).
           In GUI mode, play_audio=False prevents dual-playback echo with WebView2 HTML5 Audio.
        4. Returns base64 payload for frontend waveform, subtitles, and animation.
        """
        if not self.enabled or not text:
            return None

        clean_text = self.clean_text_for_speech(text)
        if not clean_text:
            return None

        audio_bytes = None
        out_dir = Path(__file__).resolve().parent.parent / "media" / "output" / "voice"
        out_dir.mkdir(parents=True, exist_ok=True)
        speech_file = out_dir / "jarvis_speech.mp3"

        # 1. Edge TTS synthesis with authentic British JARVIS cadence (calibrated rate & pitch)
        try:
            import edge_tts
            communicate = edge_tts.Communicate(clean_text, self.voice, rate="-3%", pitch="-2Hz")
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(communicate.save(str(speech_file)))
            loop.close()

            if speech_file.exists() and speech_file.stat().st_size > 0:
                with open(speech_file, "rb") as f:
                    audio_bytes = f.read()
        except Exception as e:
            print(f"[VoiceEngine] edge-tts error: {e}")

        # 2. SAPI5 pyttsx3 fallback if edge-tts produced no audio
        if not audio_bytes:
            try:
                import pyttsx3
                engine = pyttsx3.init()
                try:
                    for v in engine.getProperty("voices"):
                        v_name = v.name.lower()
                        if "en" in str(getattr(v, "languages", "")).lower() or "english" in v_name or "david" in v_name or "zira" in v_name:
                            engine.setProperty("voice", v.id)
                            break
                except Exception:
                    pass
                fallback_wav = out_dir / "jarvis_speech.wav"
                engine.save_to_file(clean_text, str(fallback_wav))
                engine.runAndWait()
                if fallback_wav.exists() and fallback_wav.stat().st_size > 0:
                    with open(fallback_wav, "rb") as f:
                        audio_bytes = f.read()
                    speech_file = fallback_wav
            except Exception as e:
                print(f"[VoiceEngine] pyttsx3 fallback error: {e}")

        # 3. Direct Windows Speaker Playback
        if play_audio and speech_file.exists() and speech_file.stat().st_size > 0:
            def _play_worker(file_path):
                with self._lock:
                    try:
                        import ctypes
                        mci = ctypes.windll.winmm.mciSendStringW
                        alias = f"jarvis_voice_{os.getpid()}"
                        mci(f"stop {alias}", None, 0, None)
                        mci(f"close {alias}", None, 0, None)

                        # Use short path name to avoid spaces or Unicode issues in MCI
                        buf = ctypes.create_unicode_buffer(512)
                        ctypes.windll.kernel32.GetShortPathNameW(str(file_path), buf, 512)
                        safe_path = buf.value or str(file_path)

                        ftype = "waveaudio" if safe_path.lower().endswith(".wav") else "mpegvideo"
                        open_cmd = f'open "{safe_path}" type {ftype} alias {alias}'
                        r1 = mci(open_cmd, None, 0, None)
                        if r1 == 0:
                            mci(f"play {alias} wait", None, 0, None)
                            mci(f"close {alias}", None, 0, None)
                        else:
                            # Direct PowerShell SoundPlayer fallback
                            import subprocess
                            subprocess.run([
                                "powershell", "-NoProfile", "-Command",
                                f"$w = New-Object System.Media.SoundPlayer '{safe_path}'; $w.PlaySync()"
                            ], capture_output=True, timeout=15)
                    except Exception as ex:
                        print(f"[VoiceEngine] Native playback error: {ex}")

            threading.Thread(target=_play_worker, args=(speech_file,), daemon=True).start()

        if audio_bytes:
            return base64.b64encode(audio_bytes).decode("utf-8")
        return None

    def generate_speech_base64(self, text: str) -> str:
        """Synthesizes speech and returns base64 for webview audio playback without double playing."""
        return self.synthesize_and_speak(text, play_audio=False)

    def speak_aloud(self, text: str, block: bool = False):
        """Compatibility wrapper: delegates to single-pass synthesis with playback."""
        self.synthesize_and_speak(text, play_audio=True)

    def stop(self):
        """Stops any currently playing audio playback."""
        try:
            import ctypes
            mci = ctypes.windll.winmm.mciSendStringW
            alias = f"jarvis_voice_{os.getpid()}"
            mci(f"stop {alias}", None, 0, None)
            mci(f"close {alias}", None, 0, None)
        except Exception:
            pass
