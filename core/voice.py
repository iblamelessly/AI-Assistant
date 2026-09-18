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
        """Strips markdown code blocks, tags, URLs, and symbols for clean spoken voice."""
        if not text:
            return ""

        # Remove code blocks ```...```
        cleaned = re.sub(r"```[\s\S]*?```", " [Code output omitted] ", text)
        # Remove tool tags [ACTION: ...] or [TOOL: ...]
        cleaned = re.sub(r"\[(?:ACTION|TOOL):\s*.*?\]", "", cleaned)
        # Remove markdown headers and formatting
        cleaned = re.sub(r"[#*_~`>]", "", cleaned)
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
            cleaned = summary.strip() + " I have displayed the full details on your screen, sir."

        return cleaned

    def generate_speech_base64(self, text: str) -> str:
        """
        Generates MP3 audio using edge-tts and returns a base64 string
        suitable for immediate HTML5 audio playback in the desktop UI.
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

        # Offline fallback: pyttsx3
        try:
            import pyttsx3
            engine = pyttsx3.init()
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
