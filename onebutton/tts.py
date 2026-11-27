"""Speak text aloud, and stop when asked.

Engines: say (macOS), winrt (Windows, Windows.Media.SpeechSynthesis through PowerShell),
sapi (Windows, System.Speech), piper (offline neural voices, the same on every system),
espeak-ng, pyttsx3. All but pyttsx3 can be interrupted by the button.

The voice is chosen by language (voices.py), never left to the engine's default: the
default voice of an English system reads Spanish with English pronunciation. On "auto"
the order is: a voice of the language being spoken installed on the system; then Piper,
whose voice is downloaded once into local/voices; and only then the system's default
voice, with a warning in the terminal. An engine that fails while speaking hands over
to the next one for the rest of the session.

The language is `speak_language`, and `set_language()` changes it while running ("speak
Spanish", "habla en inglés"): the engine and the voice are then chosen again, for the new
language, the next time something is said. `tts_voices` names a voice to prefer per language.
The screen always gets the text too.
"""

from __future__ import annotations

import importlib.util
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Callable

from . import voices
from .config import LOCAL_DIR
from .speech import clean_for_speech

VOICES_DIR = LOCAL_DIR / "voices"
SUBPROCESS_ENGINES = ("say", "winrt", "sapi", "piper", "espeak")


def _which(*names: str) -> str | None:
    for n in names:
        if shutil.which(n):
            return n
    return None


class Speaker:
    def __init__(self, cfg: dict):
        self._asked = cfg.get("tts", "auto")     # the engine the configuration asked for
        self.voices = dict(cfg.get("tts_voices") or {})   # per language, (part of) the name of a voice to prefer
        self.rate = int(cfg.get("tts_rate", 170))
        self.piper_model = cfg.get("piper_model") or ""
        self.piper_voice = cfg.get("piper_voice") or ""
        self._listed: list[dict] | None = None   # the voices the system says it has, asked once
        self._failed: set[str] = set()      # engines that broke while speaking
        self._proc: subprocess.Popen | None = None
        self._last_rc = 0
        self._lock = threading.Lock()
        self.set_language(cfg.get("speak_language", "en"))

    @property
    def interruptible(self) -> bool:
        self._settle()
        return self.engine in SUBPROCESS_ENGINES

    # ---- public --------------------------------------------------------
    def set_language(self, code: str) -> None:
        """Speak in `code` from now on. The engine and the voice are chosen again, for that
        language, on the next thing said: the one in use may not speak it at all."""
        self.lang = code or "en"
        self.engine = self._asked
        self._wanted = self.voices.get(self._family()) or ""   # what the configuration asked for, by name
        self.voice = self._wanted
        self._settled = False               # engine and voice are decided on the first thing said
        self._piper_cmd: list[str] | None = None
        self._piper_file: Path | None = None
        self._piper_rate = 22050
        self._pyttsx3 = None

    def _family(self) -> str:
        """'es-MX' -> 'es'."""
        return self.lang.replace("_", "-").split("-")[0].lower()

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
            self._settle()
            while True:
                ok = self._speak(spoken, until)
                if ok is not None:
                    return ok
                if not self._after_failure():   # the engine failed, it was not interrupted
                    return True
        except Exception as exc:  # Speech must never take the loop down.
            print(f"[tts] {exc}", file=sys.stderr)
        return True

    def stop(self) -> None:
        with self._lock:
            if self._proc and self._proc.poll() is None:
                self._proc.kill()

    def describe(self) -> dict:
        """What will speak, for `onebutton --voices` and the installer."""
        self._settle()
        family = self._family()
        piper = self.engine == "piper"
        return {"language": self.lang, "engine": self.engine,
                "voice": (self._piper_file.stem if piper else self.voice) or "(la voz por defecto del sistema)",
                "speaks_the_language": piper or self.engine == "espeak" or bool(self._pick_for(self.engine)),
                "installed": [v for v in self._system_voices() if v["lang"].lower().startswith(family)],
                "piper_model": str(self._piper_file) if piper else None}

    # ---- choosing the engine and the voice -------------------------------
    @staticmethod
    def _has(engine: str) -> bool:
        if engine in ("winrt", "sapi"):
            return os.name == "nt" and bool(shutil.which("powershell"))
        if engine == "say":
            return bool(shutil.which("say"))
        return engine == "espeak" and bool(_which("espeak-ng", "espeak"))

    def _system_voices(self) -> list[dict]:
        if self._listed is None:
            self._listed = self._windows_voices() if self._has("winrt") else (self._say_voices() if self._has("say") else [])
        return self._listed

    def _pick_for(self, engine: str) -> dict | None:
        """A voice of the configured language that `engine` has, or None."""
        return voices.pick([v for v in self._system_voices() if v["engine"] == engine], self.lang, self._wanted)

    def _settle(self) -> None:
        if self._settled:
            return
        self._settled = True
        asked = self.engine
        if asked not in ("auto", "winrt", "sapi", "say", "piper"):
            return                                  # espeak, pyttsx3, none: as configured
        if asked == "piper":
            if self._piper_ready():
                return
            print("[tts] Piper no está disponible (falta el paquete piper-tts o su voz); uso otra voz.", file=sys.stderr)
            asked = "auto"
        if asked != "auto":                         # an engine asked for by name: that one, with a voice of the language
            found = self._pick_for(asked)
            if found:
                self.voice = found["name"]
            else:
                self._warn_wrong_language(f"El motor de voz '{asked}', pedido en la configuración, no tiene")
            return
        found = voices.pick(self._system_voices(), self.lang, self._wanted)
        if found:
            self.engine, self.voice = found["engine"], found["name"]
        elif self._piper_ready():
            self.engine = "piper"
        elif self._has("winrt") or self._has("say"):
            # Nothing here speaks the language: the system's own voice is better than silence.
            self.engine = "winrt" if self._has("winrt") else "say"
            self._warn_wrong_language()
        elif self._has("espeak"):
            self.engine = "espeak"
        else:
            try:
                import pyttsx3  # noqa: F401
                self.engine = "pyttsx3"
            except ImportError:
                self.engine = "none"

    def _after_failure(self) -> bool:
        """The current engine broke while speaking: move to the next one that can. False when none is left."""
        failed = self.engine
        self._failed.add(failed)
        left = [e for e in ("winrt", "sapi", "say", "espeak") if e not in self._failed and self._has(e)]
        for engine in left:                         # first a system voice of the language
            found = self._pick_for(engine)
            if found or engine == "espeak":         # espeak is simply told the language
                self.engine, self.voice = engine, (found["name"] if found else "")
                break
        else:
            if "piper" not in self._failed and self._piper_ready():
                self.engine = "piper"
            elif left:                              # last resort: the system's default voice
                self.engine, self.voice = left[0], ""
                self._warn_wrong_language()
            else:
                return False
        print(f"[tts] {failed} falló; sigo con {self.engine}", file=sys.stderr)
        return True

    def _warn_wrong_language(self, who: str = "No encuentro en esta computadora, ni pude descargar,") -> None:
        print(f"\n[tts] AVISO: {who} ninguna voz para el idioma '{self.lang}'.\n"
              "      Usaré la voz por defecto del sistema, que leerá el texto con la pronunciación de otro idioma.\n"
              "      Para arreglarlo: deja `tts: auto`, conecta la computadora a internet y reinicia OneButton\n"
              "      (descarga una voz, una sola vez), o instala una voz del idioma en los ajustes del sistema\n"
              "      (Windows: Configuración > Hora e idioma > Voz > Agregar voces).\n"
              "      `onebutton --voices` muestra qué voz se usa.\n", file=sys.stderr)

    _LIST_SCRIPT = (
        "$ErrorActionPreference='Stop'; "
        "try{ [Console]::OutputEncoding=[System.Text.Encoding]::UTF8 }catch{}; "
        "try{ Add-Type -AssemblyName System.Runtime.WindowsRuntime; "
        "$null=[Windows.Media.SpeechSynthesis.SpeechSynthesizer,Windows.Media.SpeechSynthesis,ContentType=WindowsRuntime]; "
        "foreach($v in [Windows.Media.SpeechSynthesis.SpeechSynthesizer]::AllVoices)"
        "{ Write-Output ('winrt|'+$v.Language+'|'+$v.DisplayName) } }catch{}; "
        "try{ Add-Type -AssemblyName System.Speech; "
        "foreach($v in (New-Object System.Speech.Synthesis.SpeechSynthesizer).GetInstalledVoices())"
        "{ if($v.Enabled){ Write-Output ('sapi|'+$v.VoiceInfo.Culture.Name+'|'+$v.VoiceInfo.Name) } } }catch{}"
    )

    def _windows_voices(self) -> list[dict]:
        """Every installed voice both Windows engines can see, the modern engine first."""
        try:
            proc = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", self._LIST_SCRIPT],
                                  capture_output=True, timeout=40)
            return voices.parse_windows(proc.stdout.decode("utf-8", errors="replace"))
        except (OSError, subprocess.TimeoutExpired):
            return []

    def _say_voices(self) -> list[dict]:
        try:
            proc = subprocess.run(["say", "-v", "?"], capture_output=True, timeout=20)
            return voices.parse_say(proc.stdout.decode("utf-8", errors="replace"))
        except (OSError, subprocess.TimeoutExpired):
            return []

    # ---- piper: finding it and its voice ---------------------------------
    def _piper_ready(self) -> bool:
        """True when Piper can speak: the program, something to play audio with, and a voice file."""
        if self._piper_cmd:
            return True
        if importlib.util.find_spec("sounddevice") is None:
            return False
        if importlib.util.find_spec("piper") is not None:
            base = [sys.executable, "-m", "piper"]
        elif shutil.which("piper"):
            base = ["piper"]
        else:
            return False
        model = self._piper_model_file(can_download=base[0] != "piper")
        if not model:
            return False
        try:
            meta = json.loads(Path(str(model) + ".json").read_text(encoding="utf-8"))
            self._piper_rate = int(meta["audio"]["sample_rate"])
        except (OSError, ValueError, KeyError, TypeError):
            self._piper_rate = 22050
        self._piper_file = Path(model)
        self._piper_cmd = base + ["--model", str(model), "--output_raw"]
        return True

    def _of_this_language(self, name: str) -> bool:
        """Piper voices are named by language ("es_MX-claude-high"). One configured for Spanish must not
        read English after "speak English"; a name that does not say its language is taken as given."""
        m = re.match(r"([a-z]{2,3})[_-][a-z]{2}\b", name.lower())
        return not m or m.group(1) == self._family()

    def _piper_model_file(self, can_download: bool) -> Path | None:
        if self.piper_model and self._of_this_language(Path(self.piper_model).name):
            given = Path(self.piper_model).expanduser()
            if given.is_file():
                return given
            print(f"[tts] piper_model no existe: {given}", file=sys.stderr)
        name = self.piper_voice if self.piper_voice and self._of_this_language(self.piper_voice) else voices.piper_voice(self.lang)
        if not name:
            return None
        model = VOICES_DIR / f"{name}.onnx"
        if model.is_file() and Path(str(model) + ".json").is_file():
            return model
        if not can_download:
            return None
        print(f"[tts] Descargando la voz {name} (una sola vez, unos 60 MB)...", file=sys.stderr, flush=True)
        try:
            # Into a folder of its own and moved when complete, so a download cut short is never taken for a voice.
            VOICES_DIR.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(dir=VOICES_DIR) as tmp:
                subprocess.run([sys.executable, "-m", "piper.download_voices", name, "--data-dir", tmp],
                               check=True, timeout=1800, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                for suffix in (".onnx.json", ".onnx"):
                    os.replace(Path(tmp) / f"{name}{suffix}", VOICES_DIR / f"{name}{suffix}")
        except (OSError, subprocess.SubprocessError) as exc:
            print(f"[tts] no pude descargar la voz {name}: {exc}", file=sys.stderr)
            return None
        return model

    # ---- engines -------------------------------------------------------
    def _speak(self, spoken: str, until: Callable[[], bool] | None) -> bool | None:
        """True spoken, False interrupted, None the engine failed."""
        if self.engine == "say":
            cmd = ["say", "-r", str(self.rate)] + (["-v", self.voice] if self.voice else []) + [spoken]
            return self._run(cmd, until)
        if self.engine == "espeak":
            exe = _which("espeak-ng", "espeak") or "espeak"
            return self._run([exe, "-s", str(self.rate), "-v", self.voice or self.lang, spoken], until)
        if self.engine == "winrt":
            return self._winrt(spoken, until)
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
        return True

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

    # Windows.Media.SpeechSynthesis sees the voices installed with a Windows language (Sabina and Raul
    # for es-MX). Windows PowerShell 5.1 can project WinRT types directly.
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
        "if(-not $v){{ $v=$all|?{{$_.Language -like '{culture}*'}}|select -First 1 }}; "
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
        rate = max(0.5, min(3.0, round(self.rate / 170, 2)))
        script = self._WINRT_SCRIPT.format(voice=self.voice.replace("'", ""), culture=voices.culture(self.lang),
                                           lang=self.lang[:2], rate=rate)
        cmd = ["powershell", "-NoProfile", "-NonInteractive", "-Command", script]
        ok = self._run(cmd, until, input_text=text)
        if ok and self._last_rc != 0:
            return None
        return ok

    def _sapi(self, text: str, until) -> bool:
        """Windows speech through System.Speech. Text goes in on stdin so quoting never bites."""
        rate = max(-10, min(10, round((self.rate - 170) / 15)))
        script = self._SAPI_SCRIPT.format(rate=rate, voice=self.voice.replace("'", ""), culture=voices.culture(self.lang))
        cmd = ["powershell", "-NoProfile", "-NonInteractive", "-Command", script]
        return self._run(cmd, until, input_text=text)

    def _piper(self, text: str, until) -> bool | None:
        """Piper writes raw 16-bit audio as it finishes each sentence; it is played as it arrives,
        so a long reply starts at once and the button can cut it anywhere."""
        import sounddevice as sd

        scale = max(0.5, min(2.0, 170 / max(self.rate, 1)))     # tts_rate 170 is Piper's own pace
        cmd = self._piper_cmd + ["--length_scale", f"{scale:.2f}"]
        env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")   # the accents survive the pipe on Windows
        with self._lock:
            self._proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                          stderr=subprocess.DEVNULL, env=env)
            proc = self._proc
        chunks: queue.Queue = queue.Queue()

        def pump() -> None:
            try:
                proc.stdin.write(text.encode("utf-8") + b"\n")
                proc.stdin.close()
                while True:
                    data = proc.stdout.read1(16384)
                    if not data:
                        break
                    chunks.put(data)
            except (OSError, ValueError):
                pass
            chunks.put(None)

        threading.Thread(target=pump, daemon=True).start()
        step = int(self._piper_rate * 0.1) * 2       # a tenth of a second: how often the button is looked at
        played, carry = False, b""
        try:
            with sd.RawOutputStream(samplerate=self._piper_rate, channels=1, dtype="int16") as out:
                while True:
                    if until and until():
                        out.abort()
                        return False
                    try:
                        data = chunks.get(timeout=0.05)
                    except queue.Empty:
                        continue
                    if data is None:
                        break
                    data = carry + data
                    whole = len(data) - len(data) % 2    # whole 16-bit samples; the odd byte waits for the next chunk
                    data, carry = data[:whole], data[whole:]
                    for i in range(0, len(data), step):
                        if until and until():
                            out.abort()
                            return False
                        out.write(data[i:i + step])
                        played = True
        except Exception as exc:    # no sound device, a broken stream: let another engine speak
            print(f"[tts] Piper: {exc}", file=sys.stderr)
            return None
        finally:
            if proc.poll() is None:
                proc.kill()
            proc.wait()
        return True if played else None
