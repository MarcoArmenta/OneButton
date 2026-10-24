"""Push-to-talk recording driven by one key.

Press once to start, press again to stop. Recording also stops after
`silence_timeout` seconds of silence or at `max_recording` seconds, whichever
comes first, so a dropped button never leaves the microphone open forever.
"""

from __future__ import annotations

import queue
import threading
import time

import numpy as np

SILENCE_RMS = 0.01  # Below this the chunk counts as silence. Tune in local/config.yaml later if needed.


class ButtonListener:
    """Fires an event each time the configured key is pressed."""

    def __init__(self, key_name: str):
        from pynput import keyboard

        self._keyboard = keyboard
        self.key = getattr(keyboard.Key, key_name, None) or keyboard.KeyCode.from_char(key_name)
        self.pressed = threading.Event()
        self._listener = keyboard.Listener(on_press=self._on_press)
        self._listener.daemon = True
        self._listener.start()

    def _on_press(self, key):
        if key == self.key:
            self.pressed.set()

    def wait(self, timeout: float | None = None) -> bool:
        hit = self.pressed.wait(timeout)
        self.pressed.clear()
        return hit


class Recorder:
    def __init__(self, cfg: dict):
        self.rate = int(cfg["sample_rate"])
        self.silence_timeout = float(cfg["silence_timeout"])
        self.max_recording = float(cfg["max_recording"])

    def record_until(self, stop_event: threading.Event) -> np.ndarray:
        """Record mono float32 audio until stop_event, silence timeout, or max length."""
        import sounddevice as sd

        chunks: queue.Queue = queue.Queue()

        def callback(indata, frames, time_info, status):
            chunks.put(indata[:, 0].copy())

        collected: list[np.ndarray] = []
        started = time.monotonic()
        last_sound = started
        with sd.InputStream(samplerate=self.rate, channels=1, dtype="float32", callback=callback):
            while True:
                try:
                    chunk = chunks.get(timeout=0.2)
                    collected.append(chunk)
                    if float(np.sqrt(np.mean(chunk ** 2))) > SILENCE_RMS:
                        last_sound = time.monotonic()
                except queue.Empty:
                    pass
                now = time.monotonic()
                if stop_event.is_set():
                    break
                if now - last_sound > self.silence_timeout:
                    break
                if now - started > self.max_recording:
                    break
        if not collected:
            return np.zeros(0, dtype=np.float32)
        return np.concatenate(collected)
