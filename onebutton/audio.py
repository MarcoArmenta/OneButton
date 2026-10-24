"""Microphone recording with silence and length caps.

Silence is judged against a threshold calibrated from the room at startup,
so a noisy fan does not keep the recording open and a quiet room does not
cut the user off mid-thought.
"""

from __future__ import annotations

import queue
import sys
import threading
import time

import numpy as np

FLOOR_RMS = 0.004


class Recorder:
    def __init__(self, cfg: dict):
        self.rate = int(cfg["sample_rate"])
        self.silence_timeout = float(cfg["silence_timeout"])
        self.max_recording = float(cfg["max_recording"])
        self.device = cfg.get("input_device") or None
        rms = cfg.get("silence_rms", "auto")
        self.silence_rms = None if rms == "auto" else float(rms)

    def calibrate(self, seconds: float = 1.0) -> float:
        """Measure ambient noise and set the silence threshold to a multiple of it."""
        import sounddevice as sd

        if self.silence_rms is not None:
            return self.silence_rms
        try:
            frames = sd.rec(int(seconds * self.rate), samplerate=self.rate, channels=1,
                            dtype="float32", device=self.device)
            sd.wait()
            noise = float(np.sqrt(np.mean(frames[:, 0] ** 2)))
        except Exception as exc:
            print(f"[audio] calibración fallida ({exc}); usando umbral por defecto", file=sys.stderr)
            noise = 0.0
        self.silence_rms = max(FLOOR_RMS, 3.0 * noise)
        return self.silence_rms

    def record_until(self, stop_event: threading.Event) -> np.ndarray:
        """Record mono float32 audio until stop_event, silence timeout, or max length."""
        import sounddevice as sd

        if self.silence_rms is None:
            self.calibrate()
        chunks: queue.Queue = queue.Queue()

        def callback(indata, frames, time_info, status):
            chunks.put(indata[:, 0].copy())

        collected: list[np.ndarray] = []
        started = time.monotonic()
        last_sound = started
        with sd.InputStream(samplerate=self.rate, channels=1, dtype="float32",
                            callback=callback, device=self.device):
            while True:
                try:
                    chunk = chunks.get(timeout=0.2)
                    collected.append(chunk)
                    if float(np.sqrt(np.mean(chunk ** 2))) > self.silence_rms:
                        last_sound = time.monotonic()
                except queue.Empty:
                    pass
                now = time.monotonic()
                if stop_event.is_set() or now - last_sound > self.silence_timeout \
                        or now - started > self.max_recording:
                    break
        if not collected:
            return np.zeros(0, dtype=np.float32)
        return np.concatenate(collected)
