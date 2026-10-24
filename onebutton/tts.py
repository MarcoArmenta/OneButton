"""Speak text aloud, and stop when asked.

Engines: say (macOS), piper (offline, good Spanish voices), espeak-ng, pyttsx3.
Subprocess engines can be interrupted by the button; pyttsx3 cannot.
The screen always gets the text too.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Callable

from .speech import clean_for_speech


def _which(*names: str) -> str | None:
    for n in names:
        if shutil.which(n):
            return n
    return None


class Speaker:
    def __init__(self, cfg: dict):
        self.engine = cfg.get("tts", "auto")
        self.voice = cfg.get("tts_voice") or ""
        self.rate = int(cfg.get("tts_rate", 170))
        self.lang = cfg.get("language", "es")
        self.piper_model = cfg.get("piper_model") or ""
        self._proc: subprocess.Popen | None = None
        self._lock = threading.Lock()
        self._pyttsx3 = None
        if self.engine == "auto":
            if shutil.which("say"):
                self.engine = "say"
            elif shutil.which("piper") and self.piper_model:
                self.engine = "piper"
            elif _which("espeak-ng", "espeak"):
                self.engine = "espeak"
            else:
                try:
                    import pyttsx3  # noqa: F401
                    self.engine = "pyttsx3"
                except ImportError:
                    self.engine = "none"
        self.interruptible = self.engine in ("say", "piper", "espeak")

    # ---- public --------------------------------------------------------
    def say(self, text: str, show: bool = True, until: Callable[[], bool] | None = None,
            clean: bool = False) -> bool:
        """Speak `text`. Returns False if interrupted by `until()` turning True."""
        text = (text or "").strip()
        if not text:
            return True
        if show:
            print(f"\n🔊 {text}\n", flush=True)
        spoken = clean_for_speech(text, self.lang) if clean else text
        if not spoken:
            return True
        try:
            if self.engine == "say":
                cmd = ["say", "-r", str(self.rate)] + (["-v", self.voice] if self.voice else []) + [spoken]
                return self._run(cmd, until)
            if self.engine == "espeak":
                exe = _which("espeak-ng", "espeak") or "espeak"
                cmd = [exe, "-s", str(self.rate), "-v", self.voice or self.lang, spoken]
                return self._run(cmd, until)
            if self.engine == "piper":
                return self._piper(spoken, until)
            if self.engine == "pyttsx3":
                import pyttsx3
                if self._pyttsx3 is None:
                    self._pyttsx3 = pyttsx3.init()
                    self._pyttsx3.setProperty("rate", self.rate)
                    if self.voice:
                        self._pyttsx3.setProperty("voice", self.voice)
                self._pyttsx3.say(spoken)
                self._pyttsx3.runAndWait()
        except Exception as exc:  # Speech must never take the loop down.
            print(f"[tts] {exc}", file=sys.stderr)
        return True

    def stop(self) -> None:
        with self._lock:
            if self._proc and self._proc.poll() is None:
                self._proc.kill()

    # ---- engines -------------------------------------------------------
    def _run(self, cmd: list[str], until: Callable[[], bool] | None) -> bool:
        with self._lock:
            self._proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            proc = self._proc
        while proc.poll() is None:
            if until and until():
                proc.kill()
                proc.wait()
                return False
            time.sleep(0.05)
        return True

    def _piper(self, text: str, until) -> bool:
        player = _which("afplay", "paplay", "aplay", "ffplay")
        if not player:
            print("[tts] piper needs afplay, paplay, aplay or ffplay to play audio", file=sys.stderr)
            return True
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as fh:
            wav = Path(fh.name)
        try:
            subprocess.run(["piper", "--model", self.piper_model, "--output_file", str(wav)],
                           input=text, text=True, check=True, timeout=300,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            cmd = [player, str(wav)]
            if player == "ffplay":
                cmd = ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", str(wav)]
            return self._run(cmd, until)
        finally:
            wav.unlink(missing_ok=True)
