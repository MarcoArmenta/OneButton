"""Two short sounds that say whether the computer is listening.

The talk button starts a recording and ends it with the same press, and nothing
he is looking at says which of the two a press just did. So each has a sound of
its own, different enough to tell apart without thinking:

    listening   two quick notes going up
    stopped     one lower note

They are made here, as numbers, so there are no sound files to ship or to lose.
`cue_sounds: false` in the config turns them off.
"""

from __future__ import annotations

import os
import sys
import threading
import time

import numpy as np

RATE = 44100
# (frequency in Hz, seconds); 0 Hz is a pause.
START = [(660, 0.07), (0, 0.025), (990, 0.11)]
STOP = [(392, 0.17)]


def tone(notes: list[tuple[float, float]], rate: int = RATE, volume: float = 0.3) -> np.ndarray:
    """The notes as mono float32 samples, each faded in and out so it does not click."""
    parts = []
    for hz, seconds in notes:
        n = int(rate * seconds)
        if not hz:
            parts.append(np.zeros(n, dtype=np.float32))
            continue
        wave = np.sin(2 * np.pi * hz * np.arange(n) / rate)
        fade = min(n // 2, int(rate * 0.008))
        if fade:
            ramp = np.linspace(0.0, 1.0, fade)
            wave[:fade] *= ramp
            wave[-fade:] *= ramp[::-1]
        parts.append((volume * wave).astype(np.float32))
    return np.concatenate(parts) if parts else np.zeros(0, dtype=np.float32)


def _play(samples: np.ndarray, notes: list[tuple[float, float]]) -> None:
    """Start the sound and return at once. Windows has a second way if the first one fails."""
    try:
        import sounddevice as sd
        sd.play(samples, RATE)
    except Exception:
        if os.name != "nt":
            raise
        import winsound

        def beeps() -> None:
            for hz, seconds in notes:
                if hz:
                    winsound.Beep(int(hz), int(seconds * 1000))
                else:
                    time.sleep(seconds)
        threading.Thread(target=beeps, daemon=True).start()


class Cues:
    def __init__(self, cfg: dict, play=None):
        self.enabled = bool(cfg.get("cue_sounds", True))
        self._play = play or _play
        self._sounds = {"start": (tone(START), START), "stop": (tone(STOP), STOP)}

    def start(self) -> None:
        """He pressed to talk: it is listening now."""
        self._emit("start")

    def stop(self) -> None:
        """It stopped listening."""
        self._emit("stop")

    def _emit(self, which: str) -> None:
        if not self.enabled:
            return
        try:
            self._play(*self._sounds[which])
        except Exception as exc:   # a sound must never take the loop down
            print(f"[sonido] no pude dar el aviso sonoro: {exc}", file=sys.stderr)
