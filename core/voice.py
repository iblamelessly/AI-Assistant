import os
import re
import asyncio
import base64
import tempfile
import threading

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

    def generate_speech_base64(self, text: str) -> str:
        """
        Generates MP3 audio using edge-tts (English neural voices) and returns a base64 string
        suitable for immediate HTML5 audio playback in the desktop UI.
        Falls back to local SAPI5 pyttsx3 in English if edge-tts is unavailable.
        """
        if not self.enabled:
            return None

        clean_text = self.clean_text_for_speech(text)
        if not clean_text:
            return None

        try:
            import edge_tts

            async def _synthesize():
                communicate = edge_tts.Communicate(clean_text, self.voice)
                audio_bytes = b""
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        audio_bytes += chunk["data"]
                return audio_bytes

            # Run in event loop safely
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            audio_data = loop.run_until_complete(_synthesize())
            loop.close()

            if audio_data:
                return base64.b64encode(audio_data).decode("utf-8")
        except Exception as e:
            print(f"[VoiceEngine] edge-tts error: {e}")

        # Offline fallback: pyttsx3 (strictly English voice)
        try:
            import pyttsx3
            engine = pyttsx3.init()
            # Select an English voice
            try:
                for v in engine.getProperty("voices"):
                    v_name = v.name.lower()
                    if "en" in str(getattr(v, "languages", "")).lower() or "english" in v_name or "david" in v_name or "zira" in v_name:
                        engine.setProperty("voice", v.id)
                        break
            except Exception:
                pass

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
                temp_wav = tf.name

            engine.save_to_file(clean_text, temp_wav)
            engine.runAndWait()

            if os.path.exists(temp_wav):
                with open(temp_wav, "rb") as f:
                    wav_data = f.read()
                os.remove(temp_wav)
                return base64.b64encode(wav_data).decode("utf-8")
        except Exception as e:
            print(f"[VoiceEngine] pyttsx3 fallback error: {e}")

        return None

    def speak_aloud(self, text: str, block: bool = False):
        """
        Synthesizes and vocalizes speech directly through the Windows OS audio system
        using winmm MCI playback (or pyttsx3 fallback) to guarantee audible output on laptop speakers.
        """
        if not self.enabled or not text:
            return

        clean_text = self.clean_text_for_speech(text)
        if not clean_text:
            return

        def _worker():
            with self._lock:
                try:
                    import ctypes
                    mci = ctypes.windll.winmm.mciSendStringW
                    alias = f"jarvis_voice_{os.getpid()}"
                    mci(f"close {alias}", None, 0, None)

                    temp_mp3 = tempfile.mktemp(suffix=".mp3")
                    import edge_tts
                    communicate = edge_tts.Communicate(clean_text, self.voice)
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(communicate.save(temp_mp3))
                    loop.close()

                    if os.path.exists(temp_mp3) and os.path.getsize(temp_mp3) > 0:
                        mci(f'open "{temp_mp3}" type mpegvideo alias {alias}', None, 0, None)
                        mci(f"play {alias} wait", None, 0, None)
                        mci(f"close {alias}", None, 0, None)
                        try:
                            os.remove(temp_mp3)
                        except Exception:
                            pass
                        return
                except Exception as e:
                    print(f"[VoiceEngine] speak_aloud edge-tts error: {e}")

                # Offline fallback to SAPI5 pyttsx3
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
                    engine.say(clean_text)
                    engine.runAndWait()
                except Exception as e:
                    print(f"[VoiceEngine] speak_aloud pyttsx3 error: {e}")

        if block:
            _worker()
        else:
            threading.Thread(target=_worker, daemon=True).start()

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
