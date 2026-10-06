"""Offline speech-to-text: records mic audio on press, transcribes with
faster-whisper on release.

The model is lazy-loaded on first use (downloaded once, then cached
locally) so sessions that never touch dictation don't pay that startup
cost, and transcription runs fully offline after that one-time download.
Recording and transcription both happen off the Tk thread so the gesture
loop and cursor tracking never freeze while listening or thinking.
"""

import threading

import numpy as np
import sounddevice as sd

_SAMPLE_RATE = 16000
_MODEL_SIZE = "base.en"


class SpeechToText:
    def __init__(self):
        self._model = None
        self._recording = False
        self._frames = []
        self._stream = None
        self._lock = threading.Lock()

    def is_recording(self):
        return self._recording

    def start_recording(self):
        if self._recording:
            return
        self._frames = []
        self._recording = True
        self._stream = sd.InputStream(
            samplerate=_SAMPLE_RATE, channels=1, dtype="float32", callback=self._on_audio,
        )
        self._stream.start()

    def _on_audio(self, indata, _frames, _time_info, _status):
        with self._lock:
            self._frames.append(indata.copy())

    def stop_recording_and_transcribe(self, on_result):
        """Runs transcription in a background thread; `on_result(text)` is
        called from that thread with the transcript (or None on silence
        / failure) — callers must marshal back to the Tk thread (e.g.
        `root.after(0, lambda: ...)`) before touching any widget."""
        if not self._recording:
            on_result(None)
            return
        self._recording = False
        self._stream.stop()
        self._stream.close()
        self._stream = None

        threading.Thread(target=self._transcribe, args=(on_result,), daemon=True).start()

    def _transcribe(self, on_result):
        with self._lock:
            frames = list(self._frames)
        if not frames:
            on_result(None)
            return

        audio = np.concatenate(frames, axis=0).flatten()
        try:
            if self._model is None:
                from faster_whisper import WhisperModel
                self._model = WhisperModel(_MODEL_SIZE, device="cpu", compute_type="int8")
            segments, _info = self._model.transcribe(audio, language="en")
            text = " ".join(segment.text.strip() for segment in segments).strip()
        except Exception:
            text = ""
        on_result(text or None)
