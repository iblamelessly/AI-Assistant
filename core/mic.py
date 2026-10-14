import io
import re
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

# Phonetic normalization: fix common accent-driven transcription errors
# Covers Indian English phoneme patterns + common tech vocabulary mishearing
PHONETIC_CORRECTIONS = {
    r"\bjai?r?vi[sz]s?\b":                "JARVIS",
    r"\bjah?r?vi[sz]s?\b":               "JARVIS",
    r"\byou\s+tube\b":                    "YouTube",
    r"\bu\s*tube\b":                      "YouTube",
    r"\bpower\s*point\b":                 "PowerPoint",
    r"\bp\.?p\.?t\.?\b":                  "PPT",
    r"\bpd\.?\s*[ef]\.?\b":              "PDF",
    r"\bpdff?\b":                         "PDF",
    r"\btele\s*gram\b":                   "Telegram",
    r"\bgit\s+hub\b":                     "GitHub",
    r"\bgi[dt]\s*hub\b":                  "GitHub",
    r"\bpy\s*thon\b":                     "Python",
    r"\bpython[sz]?\b":                   "Python",
    r"\bgro[aqk]{1,3}\b":               "Groq",
    r"\bscreens?h?ot[sz]?\b":            "screenshot",
    r"\bpresenta\w+\b":                   "presentation",
    r"\bpresentation[sz]?\b":             "presentation",
    r"\bdoc[s]?x?\b":                     "docx",
    r"\bkrea[td]\w*\b":                   "create",
    r"\bsear[tch]+\b":                    "search",
    r"\bopen\s+it\s+up\b":               "open",
    r"\bspot\s*ify\b":                    "Spotify",
    r"\bspoti\s*fai\b":                   "Spotify",
    r"\bred\s*dit\b":                     "Reddit",
    r"\bamazon\s*dot\s*com\b":            "Amazon",
    r"\binstagram\b":                     "Instagram",
    r"\blinked\s*in\b":                   "LinkedIn",
    r"\bwhats\s*app\b":                   "WhatsApp",
    r"\bwhat's\s*app\b":                  "WhatsApp",
    r"\bnet\s*flix\b":                    "Netflix",
    r"\bvs\s*code\b":                     "VS Code",
    r"\bviscose\b":                       "VS Code",
    r"\bcode\s*visual\b":                 "VS Code",
    r"\b(crome|chrom|krome|crom)\b":      "chrome",
    r"\bempty\s*(found|had|hound|fount)\b": "empty hand",
}

# Speech synonyms — common spoken variants → normalized command text
SPEECH_SYNONYMS = {
    "emptyfound": "empty hand",
    "empty found": "empty hand",
    "empty had": "empty hand",
    "make a slide": "create presentation",
    "make slides": "create presentation",
    "make a slideshow": "create presentation",
    "write a document": "create word document",
    "write me a document": "create word document",
    "make a document": "create word document",
    "make a pdf": "create pdf",
    "make me a pdf": "create pdf",
    "open you tube": "open youtube",
    "open jar vis": "open jarvis",
    "turn it up": "volume up",
    "turn up": "volume up",
    "louder please": "volume up",
    "turn it down": "volume down",
    "turn down": "volume down",
    "quieter please": "volume down",
    "shut it": "mute",
    "quiet": "mute",
    "what time is it": "what is the time",
    "what's the time": "what is the time",
    "take a snap": "take a screenshot",
    "take snap": "take a screenshot",
}


class MicrophoneEngine:
    """
    Hardware microphone recorder and transcription bridge.
    Uses sounddevice for native OS audio capture and Groq Whisper Large v3
    for near-instantaneous (~0.2s) speech-to-text with accent normalization.
    """

    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate
        self.is_recording = False
        self._frames = []
        self._stream = None
        self._lock = threading.Lock()
        self._on_silence_callback = None
        self._speech_detected = False
        self._last_speech_time = 0.0
        self._start_time = 0.0
        self._ambient_level = 0.02
        self._ambient_samples = []
        self._auto_stopped = False

    def is_available(self) -> bool:
        return AUDIO_SUPPORTED

    @staticmethod
    def ensure_system_unmuted():
        """
        Safeguard: Checks Windows Core Audio endpoints and ensures
        the system microphone is unmuted and has an adequate recording volume.
        Prevents hardware mute button or Windows settings from blocking audio capture.
        """
        try:
            import comtypes
            comtypes.CoInitialize()
            try:
                from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
                from ctypes import cast, POINTER
                from comtypes import CLSCTX_ALL
                mic = AudioUtilities.GetMicrophone()
                if mic:
                    endpoint = mic.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                    vol = cast(endpoint, POINTER(IAudioEndpointVolume))
                    if vol.GetMute():
                        vol.SetMute(0, None)
                        print("[MicrophoneEngine] System microphone was muted in Windows. Automatically unmuted it.")
                    scalar = vol.GetMasterVolumeLevelScalar()
                    if scalar < 0.30:
                        vol.SetMasterVolumeLevelScalar(0.85, None)
                        print(f"[MicrophoneEngine] Boosted low microphone volume to 85% (was {scalar*100:.0f}%).")
            finally:
                comtypes.CoUninitialize()
        except Exception:
            pass

    def _trigger_auto_stop(self):
        """Dispatched when silence is detected after user speech or timeout occurs."""
        with self._lock:
            if not self.is_recording or self._auto_stopped:
                return
            self._auto_stopped = True
        wav_bytes = self.stop_recording()
        if self._on_silence_callback:
            try:
                self._on_silence_callback(wav_bytes)
            except Exception as e:
                print(f"[MicrophoneEngine] Error in on_silence callback: {e}")

    def start_recording(self, on_silence=None, auto_stop: bool = True) -> bool:
        """Starts recording audio from default microphone with dynamic VAD silence detection."""
        if not AUDIO_SUPPORTED:
            return False

        # Ensure hardware/OS microphone is unmuted before opening audio stream
        self.ensure_system_unmuted()

        with self._lock:
            if self.is_recording:
                return True
            self._frames = []
            self.is_recording = True
            self._auto_stopped = False
            self._speech_detected = False
            self._on_silence_callback = on_silence
            self._start_time = time.time()
            self._last_speech_time = self._start_time
            self._ambient_samples = []
            self._speech_frame_count = 0

            def callback(indata, frames, time_info, status):
                if not self.is_recording:
                    return
                self._frames.append(indata.copy())

                if auto_stop and on_silence and not self._auto_stopped:
                    try:
                        rms = float(np.sqrt(np.mean(indata**2)))
                        now = time.time()

                        # First 200ms calibrate ambient background noise baseline
                        if now - self._start_time < 0.20:
                            self._ambient_samples.append(rms)
                            if self._ambient_samples:
                                self._ambient_level = max(0.006, float(np.mean(self._ambient_samples)))
                            return

                        # Human speech threshold: distinctly above background laptop noise
                        voice_threshold = max(0.026, self._ambient_level * 1.8)
                        if rms > voice_threshold:
                            self._speech_frame_count += 1
                            if self._speech_frame_count >= 2:
                                self._speech_detected = True
                            self._last_speech_time = now
                        elif self._speech_detected:
                            # Speech detected and user paused naturally for >= 0.55s -> snappy auto-stop
                            if (now - self._last_speech_time) >= 0.55:
                                threading.Thread(target=self._trigger_auto_stop, daemon=True).start()
                        elif (now - self._start_time) >= 4.0:
                            # No speech detected within 4s -> auto-stop
                            threading.Thread(target=self._trigger_auto_stop, daemon=True).start()
                    except Exception:
                        pass

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
        """Stops recording and returns WAV audio bytes with AGC normalization."""
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

            # Balanced Automatic Gain Control (AGC) for quiet microphones without blowing out noise:
            peak = float(np.max(np.abs(audio_data)))
            if 0.003 < peak < 0.6:
                gain = min(6.0, 0.70 / peak)
                audio_data = audio_data * gain

            buf = io.BytesIO()
            sf.write(buf, audio_data, self.sample_rate, format="WAV")
            return buf.getvalue()

    def normalize_transcript(self, text: str) -> str:
        """
        Post-processing layer for Whisper output.
        1. Applies phonetic corrections for common accent-driven mishearings.
        2. Expands speech synonyms to canonical command forms.
        """
        if not text:
            return text

        corrected = text
        # Layer 1 — phonetic pattern corrections
        for pattern, replacement in PHONETIC_CORRECTIONS.items():
            corrected = re.sub(pattern, replacement, corrected, flags=re.IGNORECASE)

        # Layer 2 — speech synonym expansion (full-phrase replacement)
        corrected_lower = corrected.lower().strip()
        for spoken, canonical in SPEECH_SYNONYMS.items():
            if corrected_lower == spoken or corrected_lower.startswith(spoken + " "):
                corrected = corrected.replace(corrected[:len(spoken)], canonical, 1) if corrected_lower.startswith(spoken) else canonical

        return corrected.strip()

    def transcribe(self, wav_bytes: bytes, groq_api_key: str = "") -> str:
        """
        Transcribes WAV audio using Groq Whisper Large v3 (ultra-fast & high accuracy).
        - Sends vocabulary prompt for better recognition of tech/AI terms.
        - Applies phonetic normalization for Indian/regional accent accuracy.
        Falls back to Google Speech Recognition if no key or offline.
        """
        if not wav_bytes or len(wav_bytes) < 1000:
            return ""

        # Primary: Groq Whisper API (~0.2s latency, high accuracy)
        if groq_api_key and len(groq_api_key) > 10:
            try:
                headers = {"Authorization": f"Bearer {groq_api_key}"}
                files = {"file": ("voice_input.wav", wav_bytes, "audio/wav")}
                data = {
                    "model": "whisper-large-v3-turbo",
                    "language": "en",         # Force English — faster, more accurate for Indian English
                    "temperature": "0",        # Deterministic — no randomness in transcription
                    "response_format": "text", # Clean text response
                    # Vocabulary hint: seed the model with JARVIS-specific terms
                    "prompt": (
                        "JARVIS, YouTube, PowerPoint, Python, PDF, presentation, slides, "
                        "Telegram, GitHub, Google, Spotify, Reddit, Amazon, LinkedIn, "
                        "create, search, open, download, screenshot, PPT, docx, "
                        "volume, folder, cyberpunk, aurora, obsidian, midnight, "
                        "ocean blue, forest, sunset, rose gold, corporate, executive, "
                        "VS Code, terminal, PowerShell, file explorer, WhatsApp, Netflix, "
                        "Instagram, Pinterest, Flipkart, Wikipedia, Stack Overflow"
                    )
                }
                resp = requests.post(
                    "https://api.groq.com/openai/v1/audio/transcriptions",
                    headers=headers,
                    files=files,
                    data=data,
                    timeout=10
                )
                if resp.status_code != 200:
                    # Retry with whisper-large-v3 if turbo model has an outage
                    data["model"] = "whisper-large-v3"
                    files = {"file": ("voice_input.wav", wav_bytes, "audio/wav")}
                    resp = requests.post(
                        "https://api.groq.com/openai/v1/audio/transcriptions",
                        headers=headers,
                        files=files,
                        data=data,
                        timeout=10
                    )

                if resp.status_code == 200:
                    raw_text = resp.text.strip() if isinstance(resp.text, str) else resp.json().get("text", "").strip()
                    if raw_text:
                        clean_lower = raw_text.lower().strip().strip(".?!")
                        HALLUCINATION_BLACKLIST = {
                            "thank you", "thank you very much", "thanks for watching",
                            "subtitles by", "you", "bye", "silence", "...", "the", "a",
                            "an", "mbc", "amara.org", "please subscribe", "subscribe",
                            "watching", "like and subscribe", "so", "oh", "um", "uh"
                        }
                        if clean_lower in HALLUCINATION_BLACKLIST or clean_lower.startswith("subtitles by") or len(clean_lower) <= 2:
                            return ""
                        normalized = self.normalize_transcript(raw_text)
                        return normalized
                else:
                    print(f"[MicrophoneEngine] Groq Whisper error {resp.status_code}: {resp.text}")
            except Exception as e:
                print(f"[MicrophoneEngine] Groq transcription error: {e}")

        # Secondary Fallback: speech_recognition Google Speech API (max 8s timeout)
        try:
            import speech_recognition as sr
            r = sr.Recognizer()
            r.operation_timeout = 8
            with sr.AudioFile(io.BytesIO(wav_bytes)) as source:
                audio = r.record(source)
            text = r.recognize_google(audio)
            clean_text = text.strip()
            if len(clean_text) <= 2:
                return ""
            return self.normalize_transcript(clean_text)
        except Exception as e:
            print(f"[MicrophoneEngine] Fallback speech recognition error: {e}")

        return ""
