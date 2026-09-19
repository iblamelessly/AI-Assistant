import io
import time
import threading
import requests
import numpy as np

try:
    import sounddevice as sd
    import soundfile as sf
    AUDIO_SUPPORTED = True
except ImportError:
    AUDIO_SUPPORTED = False

class MicrophoneEngine:
    """
    Hardware microphone recorder and transcription bridge.
    Uses sounddevice for native OS audio capture and Groq Whisper Large v3
    for near-instantaneous (~0.2s) speech-to-text.
    """

    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate
        self.is_recording = False
        self._frames = []
        self._stream = None
        self._lock = threading.Lock()

    def is_available(self) -> bool:
        return AUDIO_SUPPORTED

    def start_recording(self) -> bool:
        """Starts recording audio from default microphone in background."""
        if not AUDIO_SUPPORTED:
            return False

        with self._lock:
            if self.is_recording:
                return True
            self._frames = []
            self.is_recording = True

            def callback(indata, frames, time_info, status):
                if self.is_recording:
                    self._frames.append(indata.copy())

            try:
                self._stream = sd.InputStream(
                    samplerate=self.sample_rate,
                    channels=1,
                    dtype="float32",
                    callback=callback
                )
                self._stream.start()
                return True
            except Exception as e:
                print(f"[MicrophoneEngine] Error starting audio stream: {e}")
                self.is_recording = False
                self._stream = None
                return False

    def stop_recording(self) -> bytes:
        """Stops recording and returns WAV audio bytes."""
        with self._lock:
            if not self.is_recording:
                return b""
            self.is_recording = False
            if self._stream:
                try:
                    self._stream.stop()
                    self._stream.close()
                except Exception:
                    pass
                self._stream = None

            if not self._frames:
                return b""

            audio_data = np.concatenate(self._frames, axis=0)
            buf = io.BytesIO()
            sf.write(buf, audio_data, self.sample_rate, format="WAV")
            return buf.getvalue()

    def transcribe(self, wav_bytes: bytes, groq_api_key: str = "") -> str:
        """
        Transcribes WAV audio using Groq Whisper Large v3 (ultra-fast & high accuracy).
        Falls back to Google Speech Recognition if no key or offline.
        """
        if not wav_bytes or len(wav_bytes) < 1000:
            return ""

        # Primary: Groq Whisper API (~0.2s latency, high accuracy)
        if groq_api_key and len(groq_api_key) > 10:
            try:
                headers = {"Authorization": f"Bearer {groq_api_key}"}
                files = {"file": ("voice_input.wav", wav_bytes, "audio/wav")}
                data = {"model": "whisper-large-v3"}
                resp = requests.post(
                    "https://api.groq.com/openai/v1/audio/transcriptions",
                    headers=headers,
                    files=files,
                    data=data,
                    timeout=15
                )
                if resp.status_code == 200:
                    text = resp.json().get("text", "").strip()
                    if text:
                        return text
                else:
                    print(f"[MicrophoneEngine] Groq Whisper error {resp.status_code}: {resp.text}")
            except Exception as e:
                print(f"[MicrophoneEngine] Groq transcription error: {e}")

        # Secondary Fallback: speech_recognition Google Speech API
        try:
            import speech_recognition as sr
            r = sr.Recognizer()
            with sr.AudioFile(io.BytesIO(wav_bytes)) as source:
                audio = r.record(source)
            text = r.recognize_google(audio)
            return text.strip()
        except Exception as e:
            print(f"[MicrophoneEngine] Fallback speech recognition error: {e}")

        return ""
