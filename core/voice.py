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
        self._mem_cache = {}
        # Pre-warm common responses asynchronously in background
        threading.Thread(target=self._prewarm_cache, daemon=True).start()

    def _prewarm_cache(self):
        """Pre-synthesizes common JARVIS response phrases so they return instantly (0ms)."""
        common_phrases = [
            "Yes, sir?",
            "At your service, sir.",
            "Yes, sir, how may I help you?",
            "Standing by, sir.",
            "Opening Google Chrome for you now, sir.",
            "Opening YouTube in Chrome for you now, sir.",
            "Certainly, sir.",
            "Right away, sir."
        ]
        for phrase in common_phrases:
            try:
                self.synthesize_and_speak(phrase, play_audio=False)
            except Exception:
                pass

    def set_enabled(self, enabled: bool):
        self.enabled = bool(enabled)

    def is_enabled(self) -> bool:
        return self.enabled

    def set_voice(self, voice_name: str):
        self.voice = voice_name

    # Phonetic pronunciation mapping to prevent TTS from mispronouncing technical terms (Claude Voice Mode pattern)
    PHONETIC_PRONUNCIATIONS = {
        r"\bChromium\b": "KRO-mee-um",
        r"\bPowerShell\b": "POW-er-shell",
        r"\bVulkan\b": "VUL-kan",
        r"\bffmpeg\b": "F-F-em-peg",
        r"\bFFmpeg\b": "F-F-em-peg",
        r"\bGUI\b": "GOO-ee",
        r"\bCLI\b": "C-L-I",
        r"\bAPI\b": "A-P-I",
        r"\bAPIs\b": "A-P-Is",
        r"\bSQL\b": "SEE-kwul",
        r"\bPostgreSQL\b": "Post-gres Q-L",
        r"\bJSON\b": "JAY-son",
        r"\bYAML\b": "YAM-ul",
        r"\bRegex\b": "REG-ex",
        r"\bregex\b": "REG-ex",
        r"\bGitHub\b": "GIT-hub",
        r"\bPywebview\b": "Pie-web-view",
        r"\bJARVIS\b": "JAR-vis",
        r"\bTTS\b": "T-T-S",
        r"\bSTT\b": "S-T-T",
        r"\bLLM\b": "L-L-M",
        r"\bLLMs\b": "L-L-Ms",
        r"\bstdout\b": "standard out",
        r"\bstderr\b": "standard error",
        r"\bstdin\b": "standard in",
        r"\brepo\b": "REE-po",
        r"\brepos\b": "REE-pos",
    }

    def clean_text_for_speech(self, text: str) -> str:
        """
        Strips markdown code blocks, tags, URLs, tables, and symbols for clean spoken voice.
        Enforces Anthropic voice-mode strict 50-word/2-sentence ceiling and phonetic clarity.
        """
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

        # Remove HTML and XML tags
        cleaned = re.sub(r"<[^>]+>", " ", text)
        # Remove code blocks ```...```
        cleaned = re.sub(r"```[\s\S]*?```", " [Code output omitted] ", cleaned)
        # Remove tool tags [ACTION: ...] or [TOOL: ...]
        cleaned = re.sub(r"\[(?:ACTION|TOOL):\s*.*?\]", "", cleaned)
        # Remove suggestions [Suggestion: ...]
        cleaned = re.sub(r"\[Suggestion:[\s\S]*?\]", "", cleaned)
        # Remove document tags [DOCUMENT: ...]
        cleaned = re.sub(r"\[DOCUMENT:[\s\S]*?\]", "", cleaned)
        # Remove media tags [MEDIA: ...]
        cleaned = re.sub(r"\[MEDIA:[\s\S]*?\]", "", cleaned)
        # Remove markdown tables (| header | header |)
        cleaned = re.sub(r"^\s*\|.*?\|\s*$", "", cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r"\|", " ", cleaned)
        # Convert markdown links [text](url) to just text
        cleaned = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", cleaned)
        # Remove markdown headers and formatting symbols
        cleaned = re.sub(r"[#*_~`>]", "", cleaned)
        # Remove bullet markers
        cleaned = re.sub(r"^\s*[-*•]\s+", "", cleaned, flags=re.MULTILINE)
        # Remove raw URLs
        cleaned = re.sub(r"https?://\S+", "link", cleaned)
        # Remove LaTeX / math delimiters
        cleaned = re.sub(r"\$[^$]+\$", "", cleaned)
        cleaned = re.sub(r"\\[\(\)\[\]]", "", cleaned)

        # Apply phonetic pronunciations for technical words
        for pattern, phonetic in self.PHONETIC_PRONUNCIATIONS.items():
            cleaned = re.sub(pattern, phonetic, cleaned)

        # Normalize whitespace
        cleaned = re.sub(r"\s+", " ", cleaned).strip()

        # Strict Anthropic voice mode ceiling: max 50 words / 2 sentences
        words = cleaned.split()
        if len(words) > 50:
            sentences = re.split(r"(?<=[.!?])\s+", cleaned)
            summary_sentences = []
            curr_words = 0
            for s in sentences:
                s_words = len(s.split())
                if curr_words + s_words <= 45 and len(summary_sentences) < 2:
                    summary_sentences.append(s)
                    curr_words += s_words
                else:
                    break
            if summary_sentences:
                cleaned = " ".join(summary_sentences).strip() + " I have displayed the full details on your screen, sir."
            else:
                cleaned = " ".join(words[:40]) + "... I have displayed the full details on your screen, sir."

        return cleaned

    def synthesize_and_speak(self, text: str, play_audio: bool = False) -> str | None:
        """
        High-performance neural speech synthesis with instant audio caching:
        1. Checks in-memory & disk audio cache by hash of (voice, text). Instant return (~0.001s).
        2. Synthesizes high-fidelity British voice audio (edge-tts 7.3+) if not in cache.
        3. Saves to persistent disk cache for future instant re-use.
        4. Plays audio if play_audio=True.
        5. Returns base64 payload for frontend waveform and speech.
        """
        if not self.enabled or not text:
            return None

        clean_text = self.clean_text_for_speech(text)
        if not clean_text:
            return None

        out_dir = Path(__file__).resolve().parent.parent / "media" / "output" / "voice"
        out_dir.mkdir(parents=True, exist_ok=True)
        speech_file = out_dir / "jarvis_speech.mp3"

        # Check in-memory and persistent on-disk audio cache for instant return (0ms)
        import hashlib
        cache_key = hashlib.md5(f"{self.voice}:{clean_text}".encode("utf-8")).hexdigest()
        cache_file = out_dir / f"cache_{cache_key}.mp3"

        audio_bytes = None
        if cache_key in self._mem_cache:
            audio_bytes = self._mem_cache[cache_key]
        elif cache_file.exists() and cache_file.stat().st_size > 0:
            try:
                with open(cache_file, "rb") as f:
                    audio_bytes = f.read()
                self._mem_cache[cache_key] = audio_bytes
            except Exception:
                pass

        # Synthesize via edge-tts if not in cache
        if not audio_bytes:
            try:
                import edge_tts
                communicate = edge_tts.Communicate(clean_text, self.voice, rate="-3%", pitch="-2Hz")
                asyncio.run(communicate.save(str(speech_file)))

                if speech_file.exists() and speech_file.stat().st_size > 0:
                    with open(speech_file, "rb") as f:
                        audio_bytes = f.read()
                    self._mem_cache[cache_key] = audio_bytes
                    # Save to persistent cache file
                    try:
                        with open(cache_file, "wb") as f:
                            f.write(audio_bytes)
                    except Exception:
                        pass
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
