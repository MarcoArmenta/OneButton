"""Speak text aloud, and stop when asked.

Engines: say (macOS), winrt (Windows 11 natural voices via PowerShell and
Windows.Media.SpeechSynthesis), sapi (Windows, System.Speech), piper (offline,
good Spanish voices on Linux), espeak-ng, pyttsx3. Subprocess engines can be
interrupted by the button; pyttsx3 cannot. On Windows "auto" tries winrt and
drops to sapi for the rest of the session if it fails.
The screen always gets the text too.
"""

from __future__ import annotations

import os
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
        self._last_rc = 0
        self._lock = threading.Lock()
        self._pyttsx3 = None
        if self.engine == "auto":
            if os.name == "nt" and shutil.which("powershell"):
                self.engine = "winrt"
            elif shutil.which("say"):
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
        self.interruptible = self.engine in ("say", "winrt", "sapi", "piper", "espeak")

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
            if self.engine == "winrt":
                ok = self._winrt(spoken, until)
                if ok is None:            # engine failed, not interrupted: fall back for good
                    print("[tts] voces naturales no disponibles; usando SAPI", file=sys.stderr)
                    self.engine = "sapi"
                    return self._sapi(spoken, until)
                return ok
            if self.engine == "sapi":
                return self._sapi(spoken, until)
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
    def _run(self, cmd: list[str], until: Callable[[], bool] | None, input_text: str | None = None) -> bool:
        with self._lock:
            self._proc = subprocess.Popen(
                cmd, stdin=subprocess.PIPE if input_text is not None else None,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            proc = self._proc
        if input_text is not None and proc.stdin:
            try:
                proc.stdin.write(input_text.encode("utf-8"))
                proc.stdin.close()
            except (BrokenPipeError, OSError):
                pass
        while proc.poll() is None:
            if until and until():
                proc.kill()
                proc.wait()
                return False
            time.sleep(0.05)
        self._last_rc = proc.returncode
        return True

    _SAPI_SCRIPT = (
        "[Console]::InputEncoding = [System.Text.Encoding]::UTF8; "
        "Add-Type -AssemblyName System.Speech; "
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        "$s.Rate = {rate}; "
        "if ('{voice}') {{ try {{ $s.SelectVoice('{voice}') }} catch {{}} }} "
        "else {{ try {{ $s.SelectVoiceByHints([System.Speech.Synthesis.VoiceGender]::NotSet, "
        "[System.Speech.Synthesis.VoiceAge]::NotSet, 0, [System.Globalization.CultureInfo]'{culture}') }} catch {{}} }} "
        "$s.Speak([Console]::In.ReadToEnd())"
    )

    # Windows.Media.SpeechSynthesis exposes the Windows 11 "Natural" voices (Dalia, Jorge for es-MX)
    # that System.Speech cannot see. Windows PowerShell 5.1 can project WinRT types directly.
    _WINRT_SCRIPT = (
        "$ErrorActionPreference='Stop'; "
        "[Console]::InputEncoding=[System.Text.Encoding]::UTF8; "
        "$text=[Console]::In.ReadToEnd(); "
        "Add-Type -AssemblyName System.Runtime.WindowsRuntime; "
        "$null=[Windows.Media.SpeechSynthesis.SpeechSynthesizer,Windows.Media.SpeechSynthesis,ContentType=WindowsRuntime]; "
        "$asTask=([System.WindowsRuntimeSystemExtensions].GetMethods()|?{{$_.Name -eq 'AsTask' -and "
        "$_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'}})[0]; "
        "$synth=New-Object Windows.Media.SpeechSynthesis.SpeechSynthesizer; "
        "$all=[Windows.Media.SpeechSynthesis.SpeechSynthesizer]::AllVoices; "
        "$v=$null; if('{voice}'){{ $v=$all|?{{$_.DisplayName -like '*{voice}*'}}|select -First 1 }}; "
        "if(-not $v){{ $v=$all|?{{$_.Language -like '{culture}*' -and $_.DisplayName -like '*Natural*'}}|select -First 1 }}; "
        "if(-not $v){{ $v=$all|?{{$_.Language -like '{lang}*'}}|select -First 1 }}; "
        "if($v){{ $synth.Voice=$v }}; "
        "$synth.Options.SpeakingRate={rate}; "
        "$op=$synth.SynthesizeTextToStreamAsync($text); "
        "$t=$asTask.MakeGenericMethod([Windows.Media.SpeechSynthesis.SpeechSynthesisStream]).Invoke($null,@($op)); "
        "$t.Wait(-1)|Out-Null; $stream=$t.Result; "
        "$in=[System.IO.WindowsRuntimeStreamExtensions]::AsStreamForRead($stream.GetInputStreamAt(0)); "
        "$wav=[System.IO.Path]::GetTempFileName()+'.wav'; "
        "$fs=[System.IO.File]::Create($wav); $in.CopyTo($fs); $fs.Close(); "
        "(New-Object System.Media.SoundPlayer $wav).PlaySync(); Remove-Item $wav -ErrorAction SilentlyContinue"
    )

    def _winrt(self, text: str, until) -> bool | None:
        """True spoken, False interrupted, None failed (caller falls back to SAPI)."""
        rate = max(0.5, min(3.0, round(self.rate / 170, 2)))
        culture = {"es": "es-MX", "en": "en-US"}.get(self.lang[:2], self.lang)
        script = self._WINRT_SCRIPT.format(voice=self.voice.replace("'", ""), culture=culture,
                                           lang=self.lang[:2], rate=rate)
        cmd = ["powershell", "-NoProfile", "-NonInteractive", "-Command", script]
        ok = self._run(cmd, until, input_text=text)
        if ok and self._last_rc != 0:
            return None
        return ok

    def _sapi(self, text: str, until) -> bool:
        """Windows speech through System.Speech. Text goes in on stdin so quoting never bites."""
        rate = max(-10, min(10, round((self.rate - 170) / 15)))
        culture = {"es": "es-MX", "en": "en-US"}.get(self.lang[:2], self.lang)
        script = self._SAPI_SCRIPT.format(rate=rate, voice=self.voice.replace("'", ""), culture=culture)
        cmd = ["powershell", "-NoProfile", "-NonInteractive", "-Command", script]
        return self._run(cmd, until, input_text=text)

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
