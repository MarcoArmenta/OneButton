"""Speak text aloud. Falls back gracefully: the screen always gets the text too."""

from __future__ import annotations

import shutil
import subprocess
import sys


class Speaker:
    def __init__(self, cfg: dict):
        self.engine = cfg.get("tts", "auto")
        self.voice = cfg.get("tts_voice") or ""
        self.rate = int(cfg.get("tts_rate", 170))
        self.lang = cfg.get("language", "es")
        if self.engine == "auto":
            if shutil.which("say"):
                self.engine = "say"
            elif shutil.which("espeak-ng") or shutil.which("espeak"):
                self.engine = "espeak"
            else:
                try:
                    import pyttsx3  # noqa: F401
                    self.engine = "pyttsx3"
                except ImportError:
                    self.engine = "none"
        self._pyttsx3 = None

    def say(self, text: str, show: bool = True) -> None:
        text = (text or "").strip()
        if not text:
            return
        if show:
            print(f"\n🔊 {text}\n", flush=True)
        try:
            if self.engine == "say":
                cmd = ["say", "-r", str(self.rate)]
                if self.voice:
                    cmd += ["-v", self.voice]
                subprocess.run(cmd + [text], check=False, timeout=120)
            elif self.engine == "espeak":
                exe = shutil.which("espeak-ng") or "espeak"
                cmd = [exe, "-s", str(self.rate), "-v", self.voice or self.lang]
                subprocess.run(cmd + [text], check=False, timeout=120)
            elif self.engine == "pyttsx3":
                import pyttsx3
                if self._pyttsx3 is None:
                    self._pyttsx3 = pyttsx3.init()
                    self._pyttsx3.setProperty("rate", self.rate)
                    if self.voice:
                        self._pyttsx3.setProperty("voice", self.voice)
                self._pyttsx3.say(text)
                self._pyttsx3.runAndWait()
        except Exception as exc:  # Speech must never take the loop down.
            print(f"[tts] {exc}", file=sys.stderr)
