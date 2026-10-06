"""Offline speech-to-text: records mic audio on press, transcribes with
faster-whisper on release.

The model is lazy-loaded on first use (downloaded once, then cached
locally) so sessions that never touch dictation don't pay that startup
cost, and transcription runs fully offline after that one-time download.
Recording and transcription both happen off the Tk thread so the gesture
loop and cursor tracking never freeze while listening or thinking.

Whisper has no streaming mode, so the live preview is approximated by
re-transcribing the most recent audio every fraction of a second. That
preview is display-only: what actually gets typed is always one full
transcription of the entire recording after it stops — the same single
pass dictation has always used — so preview mistakes can never reach the
user's text.
"""

import threading
import time

import numpy as np
import sounddevice as sd

_SAMPLE_RATE = 16000
_MODEL_SIZE = "base.en"

_PREVIEW_INTERVAL = 0.4  # seconds between live-preview passes
_PREVIEW_WINDOW = 20  # seconds of most recent audio each preview pass re-transcribes

# Auto-stop: after speech, this much continuous silence ends the
# recording; if nothing is ever said, give up after the longer timeout.
_SILENCE_AUTO_STOP = 4.0
_NO_SPEECH_AUTO_STOP = 10.0

# A block counts as voice when it's this many times louder than the
# tracked noise floor (relative, so it works for quiet and loud mics
# alike), with a small absolute minimum so dead-silent input can't count.
_VOICE_RATIO = 3.0
_MIN_VOICE_LEVEL = 0.004


class SpeechToText:
    def __init__(self, device=None):
        self._model = None
        self._model_lock = threading.Lock()
        self._recording = False
        self._frames = []
        self._stream = None
        self._lock = threading.Lock()
        self._device = device  # sounddevice input device index, or None for the system default

        self.level = 0.0  # 0-1 loudness of the latest audio, for the live meter
        self._noise_floor = None
        self._peak = 0.02
        self._heard_voice = False
        self._last_voice_time = 0.0
        self._start_time = 0.0

    def set_device(self, device):
        """device: a sounddevice input device index, or None for the
        system default. Takes effect on the next start_recording() call —
        changing it mid-recording doesn't restart the active stream."""
        self._device = device

    def is_recording(self):
        return self._recording

    def start_recording(self, on_preview=None):
        """on_preview(text), if given, is called from a background thread
        with a live best-guess transcript while recording — callers must
        marshal back to the Tk thread before touching any widget."""
        if self._recording:
            return
        self._frames = []
        self.level = 0.0
        self._noise_floor = None
        self._peak = 0.02
        self._heard_voice = False
        self._start_time = self._last_voice_time = time.monotonic()
        self._recording = True
        self._stream = sd.InputStream(
            samplerate=_SAMPLE_RATE, channels=1, dtype="float32", callback=self._on_audio,
            device=self._device,
        )
        self._stream.start()
        if on_preview is not None:
            threading.Thread(target=self._preview_loop, args=(on_preview,), daemon=True).start()

    def _on_audio(self, indata, _frames, _time_info, _status):
        block = indata.copy()
        with self._lock:
            self._frames.append(block)

        rms = float(np.sqrt(np.mean(block ** 2)))
        if self._noise_floor is None or rms < self._noise_floor:
            self._noise_floor = rms
        else:
            # Creeps up slowly, so sustained speech never gets mistaken for
            # the room's background noise.
            self._noise_floor += (rms - self._noise_floor) * 0.002
        if rms > max(self._noise_floor * _VOICE_RATIO, _MIN_VOICE_LEVEL):
            self._heard_voice = True
            self._last_voice_time = time.monotonic()
        self._peak = max(self._peak * 0.995, rms)
        self.level = min(1.0, rms / self._peak)

    def should_auto_stop(self):
        if not self._recording:
            return False
        now = time.monotonic()
        if self._heard_voice:
            return now - self._last_voice_time > _SILENCE_AUTO_STOP
        return now - self._start_time > _NO_SPEECH_AUTO_STOP

    def _load_model(self):
        with self._model_lock:
            if self._model is None:
                from faster_whisper import WhisperModel
                self._model = WhisperModel(_MODEL_SIZE, device="cpu", compute_type="int8")
            return self._model

    def _preview_loop(self, on_preview):
        try:
            model = self._load_model()
        except Exception:
            return
        transcribed_frames = 0
        while self._recording:
            time.sleep(_PREVIEW_INTERVAL)
            if not (self._recording and self._heard_voice):
                continue
            with self._lock:
                frames = list(self._frames)
            if len(frames) == transcribed_frames:
                continue
            transcribed_frames = len(frames)
            audio = np.concatenate(frames, axis=0).flatten()[-_PREVIEW_WINDOW * _SAMPLE_RATE:]
            try:
                with self._model_lock:
                    # Greedy decoding keeps each pass fast; the speech filter
                    # stops Whisper inventing words during silent stretches.
                    segments, _info = model.transcribe(
                        audio, language="en", beam_size=1, vad_filter=True,
                        condition_on_previous_text=False,
                    )
                    text = " ".join(segment.text.strip() for segment in segments).strip()
            except Exception:
                continue
            if self._recording and text:
                on_preview(text)

    def stop_recording_and_transcribe(self, on_result):
        """Runs transcription in a background thread; `on_result(text)` is
        called from that thread with the transcript (or None on silence
        / failure) — callers must marshal back to the Tk thread (e.g.
        `root.after(0, lambda: ...)`) before touching any widget."""
        if not self._recording:
            on_result(None)
            return
        self._recording = False
        self.level = 0.0
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
            model = self._load_model()
            with self._model_lock:
                segments, _info = model.transcribe(audio, language="en")
                text = " ".join(segment.text.strip() for segment in segments).strip()
        except Exception:
            text = ""
        on_result(text or None)
