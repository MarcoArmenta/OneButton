"""The OneButton loop.

    press -> record -> press -> transcribe -> screen, command, or Claude turn -> speak

One or two buttons, two gestures each; see gestures.py for the mapping. With
two buttons, yes and no never depend on speech recognition. Local commands
("actualiza", "deshacer", "repite") never reach the agent, and anything that
changes the installed version is read aloud and waits for a yes.

It speaks one language (`speak_language`, English unless he says "habla en
español") and understands English and Spanish at once: every command has both
forms, and every phrase the loop says is written in both, `L(en, es)`.

The buttons belong to the loop. They are swallowed before any application sees
them, so a press never pages a PDF; moving a page is done by voice ("baja un
poco", "scroll down", "otra vez").

The talk button means one of two things, and he can hear which: "I am talking"
(two notes going up) or "I am done" (one lower note). A press while the
computer is speaking stops the voice and starts listening at once; button two
silences it without listening.

The screen (onebutton/screen) is a local page with panels: the conversation,
the maths board, the manuscript. Short utterances that name a panel or ask to
read are handled there, instantly. Holding button 2 opens its ring menu and
the loop forwards button presses and speech to the page until it closes.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

from . import __version__, auth, commands, conversations, desktop_commands, hardware, login, updater
from .config import LOCAL_DIR, WORKSPACE_DIR, load, save_local
from .gestures import (A_CANCEL, A_HELP, A_NO, A_REASSURE, A_REPEAT, A_STOP, A_TALK, A_YES,
                       CONFIRMING, IDLE, LONG, NO, RECORDING, SHORT, TALK, THINKING, help_text, interpret)
from .lang import L, SUPPORTED, language, set_language
from .lang import helper as helper_of
from .lang import name as language_name

# What may still be done on the computer while he is dictating: nothing that takes free text.
DICTATION_SAFE = ("scroll", "scroll_again", "volume")
SCROLL_AGAIN_WINDOW = 300.0     # seconds during which "otra vez" still means the last scroll
BARGE_SECONDS = 20.0            # after a press cut the voice to talk: how long nothing else is said while he has not spoken
EXIT_WORDS = ("salir", "sal", "listo", "terminar", "cerrar", "exit", "done", "close", "finish", "quit", "leave")
CANCEL_WORDS = ("cancela", "cancelar", "salir", "quita", "no", "cancel", "exit", "stop", "never mind")
HERE_WORDS = ("aqui", "pulsa", "clic", "click", "ahi", "here", "there", "press", "that one")


def banner() -> str:
    return L("OneButton is ready. Press the button and speak. Press again when you finish.",
             "OneButton listo. Pulsa el botón y habla. Pulsa otra vez cuando termines.")


class Loop:
    cues = None                     # the listening / stopped sounds (sounds.Cues), when there is audio
    barged = False                  # he pressed to talk while it was speaking, and has not been recorded yet
    barged_at = 0.0
    last_recording_barged = False   # the last recording began that way

    def __init__(self, cfg: dict, dry_run: bool = False):
        from .rules import install as install_rules
        from .tts import Speaker

        self.cfg = cfg
        self.dry_run = dry_run
        set_language(cfg.get("speak_language"))
        self.speaker = Speaker(cfg)
        self.last_scroll: tuple[str, int, float] | None = None   # direction, amount, when
        self.last_reply = ""
        self.progress_interval = float(cfg.get("progress_interval", 45))
        self.log_path = LOCAL_DIR / "session.log" if cfg.get("log_transcripts", True) else None
        self.modules: list[subprocess.Popen] = []
        from .board import Board
        self.screen = Board(int(cfg.get("screen_port") or cfg.get("pizarra_port") or 8765))
        self.screen_alive_until = 0.0
        mods = list(cfg.get("modules") or [])
        self.mods = mods
        self.panels = ["conversacion"] + (["pizarron"] if "maths-screen" in mods else []) + \
            (["escritorio"] if "scribe" in mods else [])
        self.conversation = WORKSPACE_DIR / "conversacion.md"   # what the screen shows: the current conversation
        self.convs = conversations.Registry()
        self.convs_lock = threading.Lock()
        self.desktop_enabled = "computadora" in mods
        self.desktop_py = Path(__file__).resolve().parent.parent / "modules" / "computadora" / "desktop.py"
        self.overlay: subprocess.Popen | None = None
        install_rules(mods, speak=language())
        self.two_buttons = bool(cfg.get("button2_key"))
        if dry_run:
            self.button = self.recorder = self.transcriber = self.agent = None
            return
        from .agent import Agent
        from .button import Button
        from .audio import Recorder
        from .stt import Transcriber

        self.button = Button({"talk": cfg["button_key"], "no": cfg.get("button2_key")},
                             cfg.get("button_source", "auto"),
                             filters={"min_hold": float(cfg["press_min_hold"]), "bounce": float(cfg["press_bounce"]),
                                      "refractory": float(cfg["press_refractory"]), "long_hold": float(cfg["long_hold"])},
                             exclusive=bool(cfg.get("button_exclusive", True)))
        from .sounds import Cues

        self.recorder = Recorder(cfg)
        self.transcriber = Transcriber(cfg)
        self.cues = Cues(cfg)
        self.agent = Agent(cfg)
        self.agent.on_denied = self.note_denied

    # ---- helpers -------------------------------------------------------
    def log(self, who: str, text: str) -> None:
        if not self.log_path:
            return
        try:
            with self.log_path.open("a", encoding="utf-8") as fh:
                stamp = dt.datetime.now().isoformat(timespec="seconds")
                fh.write(f"{stamp} {who}: {text.strip()}\n")
        except OSError:
            pass

    def note_denied(self, refused: list[str]) -> None:
        """Claude Code refused these tool calls: they are outside the allow list in claude/settings.json.
        Kept in the log and shown in the terminal, so a helper sees exactly what would have to be allowed."""
        for what in refused:
            self.log("PERMISO", what)
            print(f"[permiso] Claude Code no tiene permiso para: {what}", file=sys.stderr, flush=True)

    def screen_look(self) -> dict:
        """Theme, layout and text size for the page. The "glasses" preset suits OLED display glasses."""
        preset = self.cfg.get("screen_preset") or "auto"
        if preset == "auto":
            found = hardware.screens()
            if found:
                preset = hardware.suggest_preset(found)
            else:  # cannot look right now: what the first run saw
                preset = (hardware.load() or {}).get("suggested_preset") or "monitor"
        look = {"monitor": {"theme": "auto", "layout": "tabs", "font_size": 28},
                "glasses": {"theme": "glasses", "layout": "wide", "font_size": 30},
                "tablet": {"theme": "auto", "layout": "tabs", "font_size": 24}}.get(preset, {})
        for key in ("theme", "layout", "font_size"):
            if self.cfg.get(f"screen_{key}") not in (None, "", "auto"):
                look[key] = self.cfg[f"screen_{key}"]
        if look.get("theme") == "auto":
            look.pop("theme")
        return look

    def page_rect(self) -> tuple[int, int, int, int] | None:
        """(x, y, width, height) of the screen the page should fill, or None when unknown."""
        found = hardware.screens() or (hardware.load() or {}).get("screens") or []
        s = hardware.page_screen(found, self.cfg.get("screen_display", "auto"))
        if not s or not s.get("width"):
            return None
        return int(s.get("x", 0)), int(s.get("y", 0)), int(s["width"]), int(s["height"])

    def converse(self, who: str, text: str, conv: conversations.Conversation | None = None) -> None:
        """Append a turn to the conversation's own file and, if it is the current one, to
        workspace/conversacion.md, which the screen shows in large type."""
        conv = conv or self.convs.current
        try:
            WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
            stamp = dt.datetime.now().strftime("%H:%M")
            own = WORKSPACE_DIR / conv.file
            own.parent.mkdir(parents=True, exist_ok=True)
            with self.convs_lock:
                with own.open("a", encoding="utf-8") as fh:
                    fh.write(f"## {stamp} {who}\n\n{text.strip()}\n\n")
                if own.stat().st_size > 400_000:  # keep the file light: drop the oldest half
                    parts = own.read_text(encoding="utf-8").split("\n## ")
                    own.write_text("## " + "\n## ".join(parts[len(parts) // 2:]).lstrip("# "), encoding="utf-8")
                if conv is self.convs.current:
                    self.conversation.write_text(own.read_text(encoding="utf-8"), encoding="utf-8")
        except OSError:
            pass

    def show_conversation(self, conv: conversations.Conversation) -> None:
        """Put a conversation on the screen (after a switch)."""
        try:
            own = WORKSPACE_DIR / conv.file
            with self.convs_lock:
                self.conversation.write_text(own.read_text(encoding="utf-8") if own.exists() else "", encoding="utf-8")
        except OSError:
            pass

    def screen_try(self, text: str) -> bool:
        """Offer a short utterance to the screen first (panel names, "baja", "sube", "lee ...").
        True if it took it."""
        if self.dry_run or len(commands.normalize(text).split()) > 6:
            return False
        if time.monotonic() < self.screen_alive_until:
            return False
        seq = self.screen.post({"type": "voice", "text": text})
        if not seq:
            return False
        st = self.screen.wait_handled(seq, timeout=1.5)
        if int(st.get("seq_handled") or 0) < seq:
            self.screen_alive_until = time.monotonic() + 60  # page not open; stop asking for a minute
            return False
        if not st.get("handled"):
            return False
        if st.get("mode") not in (None, "idle"):
            self.screen_mode(entered=True)
        return True

    def say(self, text: str, clean: bool = False) -> None:
        """Speak, and let any button press cut it short.

        A short press of the talk button cuts the voice because he wants to talk: the press still
        counts, so whoever reads the button next starts recording, and nothing else is said until
        he has spoken. Any other press only silences it.
        """
        if self.dry_run or not self.button:
            self.speaker.say(text, clean=clean)
            return
        if self.barging():
            print(f"\n🔇 {text}\n", flush=True)   # he has the floor: it stays on the screen, unsaid
            return
        self.button.clear()
        finished = self.speaker.say(text, until=lambda: not self.button.events.empty(), clean=clean)
        if not finished:
            ev = self.button.poll()
            self.button.clear()
            if ev == (TALK, SHORT):
                self.barged, self.barged_at = True, time.monotonic()
                self.button.events.put(ev)
                self.log("BOTÓN", "una pulsación cortó la voz y empieza a escuchar")
            else:
                self.log("BOTÓN", "una pulsación cortó la voz; no empezó a grabar")

    def barging(self) -> bool:
        """True from a press that cut the voice to talk until the recording it asked for starts.
        It lapses by itself, so a press lost on the way can never leave the computer mute."""
        if self.barged and time.monotonic() - self.barged_at > BARGE_SECONDS:
            self.barged = False
        return self.barged

    def forget_presses(self) -> None:
        """Drop presses made before now, except the one that is waiting to start his recording."""
        if not self.barging():
            self.button.clear()

    def heard_nothing(self) -> None:
        """A recording with no words in it. If he had pressed only to silence the voice, say nothing."""
        if self.last_recording_barged:
            return
        self.say(L("I heard nothing. Press the button and try again.",
                   "No escuché nada. Pulsa el botón y vuelve a intentarlo."))

    def start_modules(self) -> None:
        """Start the screen, then any long-running helper a module ships."""
        from .rules import MODULES_DIR

        if not self.dry_run or self.cfg.get("screen_in_dry_run"):
            screen = Path(__file__).resolve().parent / "screen" / "start.py"
            env = dict(os.environ)
            if not self.cfg.get("open_browser", True):
                env["ONEBUTTON_NO_BROWSER"] = "1"
            rect = self.page_rect()
            if rect:
                env["ONEBUTTON_SCREEN_RECT"] = ",".join(str(v) for v in rect)
            try:
                self.modules.append(subprocess.Popen(
                    [sys.executable, str(screen), str(WORKSPACE_DIR), str(self.screen.base.rsplit(":", 1)[1])],
                    env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
            except OSError as exc:
                print(f"[pantalla] no pude arrancar la pantalla: {exc}", file=sys.stderr)
            for _ in range(30):
                if self.screen.available():
                    break
                time.sleep(0.1)
            self.screen.post({"type": "config", "panels": self.panels, "lang": language(),
                              "desktop": self.desktop_enabled, **self.screen_look()})
        for name in self.cfg.get("modules") or []:
            script = MODULES_DIR / name / "start.py"
            if script.exists():
                try:
                    proc = subprocess.Popen([sys.executable, str(script), str(WORKSPACE_DIR)],
                                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    self.modules.append(proc)
                except OSError as exc:
                    print(f"[módulos] no pude arrancar {name}: {exc}", file=sys.stderr)

    # ---- input -----------------------------------------------------------
    def action(self, state: str, timeout: float | None = None) -> str | None:
        ev = self.button.wait(timeout)
        if ev is None:
            return None
        act = interpret(ev, state, self.two_buttons)
        # The same press means different things at different moments; the log says which it was.
        self.log("BOTÓN", f"{ev[0]} {ev[1]} ({state}) -> {act}")
        return act

    def listen_once(self) -> str | None:
        """Wait idle for a press, record until the next press, return text. None if cancelled."""
        if self.dry_run:
            try:
                return input("\n[tú] ")
            except EOFError:
                raise KeyboardInterrupt
        while True:
            act = self.action(IDLE, 1.0)
            if act is None:
                self.announce_finished()
                continue
            if act == A_TALK:
                return self.record_and_transcribe()
            if act == A_HELP:
                if self.two_buttons and self.screen.available():
                    self.screen_mode()
                else:
                    self.say(help_text(self.two_buttons))
            elif act == A_REPEAT:
                self.say(self.last_reply or L("There is nothing to repeat yet.", "No hay nada que repetir todavía."), clean=True)

    def record_and_transcribe(self) -> str | None:
        """Recording starts now. Ends on the next press; None if cancelled."""
        print(L("🎙️  Recording... (press to finish)", "🎙️  Grabando... (pulsa para terminar)"), flush=True)
        stop = threading.Event()
        cancelled = threading.Event()

        def watch_button():
            while not stop.is_set():
                act = self.action(RECORDING, 0.1)
                if act == A_STOP:
                    stop.set()
                elif act == A_CANCEL:
                    cancelled.set()
                    stop.set()

        self.last_recording_barged, self.barged = self.barged, False
        threading.Thread(target=watch_button, daemon=True).start()
        if self.cues:
            self.cues.start()
        audio = self.recorder.record_until(stop)
        stop.set()
        if self.cues:
            self.cues.stop()
        # How long it listened and how loud the loudest moment was (1.0 is the limit): a long, quiet
        # recording is one he did not know was running; a short loud one that gives no text is the recogniser.
        level = float(abs(audio).max()) if audio.size else 0.0
        self.log("GRABACIÓN", f"{audio.size / self.recorder.rate:.1f} s, nivel {level:.2f}")
        if cancelled.is_set():
            self.say(L("Cancelled.", "Cancelado."))
            return None
        print(L("⏳ Transcribing...", "⏳ Transcribiendo..."), flush=True)
        text = self.transcriber.transcribe(audio)
        print(f"[tú] {text}", flush=True)
        self.log("TÚ", text)
        return text

    def confirm(self, question: str) -> bool:
        """Ask aloud; yes is a held talk button (two-button setups) or a spoken confirm word."""
        if self.two_buttons:
            self.say(question + L(" Hold button one to say yes, or press button two to cancel. "
                                  "You can also say 'go ahead'.",
                                  " Mantén pulsado el botón uno para decir sí, o pulsa el botón dos para cancelar. "
                                  "También puedes decir 'adelante'."))
        else:
            self.say(question + L(" Say 'go ahead' to continue, or anything else to cancel.",
                                  " Di 'adelante' para continuar, o cualquier otra cosa para cancelar."))
        if self.dry_run:
            heard = self.listen_once()
            return heard is not None and commands.classify(heard, self.cfg, awaiting_confirmation=True).kind == commands.CONFIRM
        while True:
            act = self.action(CONFIRMING)
            if act == A_YES:
                return True
            if act in (A_NO, A_CANCEL):
                return False
            if act == A_TALK:
                heard = self.record_and_transcribe()
                if heard is None:
                    return False
                return commands.classify(heard, self.cfg, awaiting_confirmation=True).kind == commands.CONFIRM

    # ---- screen mode -------------------------------------------------------
    def screen_mode(self, entered: bool = False) -> None:
        """Buttons and speech go to the page until it reports idle or button 2 is held.

        Reached by holding button 2 (opens the ring menu) or when a short
        utterance put the page into a mode (reading, board editing).
        """
        if not entered:
            self.say(L("Menu.", "Menú."))
            self.screen.post({"type": "menu"})
        self.log("SISTEMA", "modo pantalla")
        try:
            while True:
                ev = self.button.wait()
                if ev is None:
                    continue
                button, gesture = ev
                if (button, gesture) == (NO, LONG):
                    return
                if (button, gesture) == (TALK, SHORT):
                    text = self.record_and_transcribe()
                    if text is None:
                        continue
                    if commands.normalize(text) in EXIT_WORDS:
                        return
                    st = self.screen_voice(text)
                else:
                    seq = self.screen.post({"type": "button", "button": button, "gesture": gesture})
                    st = self.screen.wait_handled(seq)
                if st.get("mode") in (None, "idle"):
                    return
        finally:
            self.screen.post({"type": "exit"})

    def screen_voice(self, text: str) -> dict:
        st = self.screen.state()
        if st.get("awaiting"):
            self.dictate_latex(text)
            return self.screen.state()
        seq = self.screen.post({"type": "voice", "text": text})
        st = self.screen.wait_handled(seq)
        if st.get("handled") is False and st.get("selected"):
            self.dictate_latex(text)  # free-form edit of the selected part of a formula
            st = self.screen.state()
        elif st.get("handled") is False:
            self.say(L("I did not understand. Say the name of a panel, a number, or 'exit'.",
                       "No entendí. Di el nombre de un panel, un número, o 'salir'."))
        return st

    def dictate_latex(self, text: str) -> None:
        print(L("🤖 Converting to LaTeX...", "🤖 Convirtiendo a LaTeX..."), flush=True)
        latex = self.agent.convert_latex(text)
        if not latex:
            self.say(L("I could not convert it. Say it again.", "No pude convertirlo. Dilo otra vez."))
            return
        self.log("LATEX", f"{text} -> {latex}")
        self.screen.post({"type": "latex", "text": latex})

    # ---- the computer ------------------------------------------------------
    def desktop(self, *args: str) -> dict:
        try:
            proc = subprocess.run([sys.executable, str(self.desktop_py), *args], capture_output=True, text=True, timeout=30)
            res = json.loads(proc.stdout.strip() or "{}")
        except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError) as exc:
            res = {"error": str(exc)}
        if isinstance(res, dict) and res.get("error"):
            # Some orders are silent (scrolling): without this line a failure would leave no trace.
            self.log("EQUIPO", f"error en {args[0] if args else '?'}: {res['error']}")
        return res

    def desktop_act(self, act: dict) -> bool:
        """Carry out a direct order. False when the computer has nothing by that name, so what he
        said was not an order after all and should go to Claude ("ve a la sección cinco")."""
        a = act["action"]
        if a == "windows":
            wins = self.desktop("windows")
            titles = [w["title"] for w in wins if isinstance(w, dict)][:8] if isinstance(wins, list) else []
            self.say(L("Windows: ", "Ventanas: ") + ". ".join(titles) + "." if titles else L("I see no windows.", "No veo ventanas."))
        elif a in ("focus", "open"):
            r = self.desktop(a, act["target"])
            if r.get("error"):
                return False   # no window or program of that name
            self.say(r.get("focused") or r.get("opened") or L("Done.", "Hecho."))
        elif a in ("minimize", "maximize"):
            self.say(self.outcome(self.desktop(a), L("Done.", "Hecho.")))
        elif a == "key":
            self.say(self.outcome(self.desktop("key", act["keys"]), L("Done.", "Hecho.")), clean=True)
        elif a == "type":
            self.say(self.outcome(self.desktop("type", act["text"]), L("Typed.", "Escrito.")))
        elif a == "scroll":   # silent: he sees the page move, and speech would only slow the next "otra vez"
            self.last_scroll = (act["dir"], int(act["n"]), time.monotonic())
            self.desktop("scroll", act["dir"], str(act["n"]))
        elif a == "volume":
            self.say(self.outcome(self.desktop("volume", act["what"]), ""))
        elif a == "screenshot":
            self.say(self.outcome(self.desktop("screenshot"), L("Screenshot saved.", "Captura guardada.")))
        elif a == "describe":
            r = self.desktop("screenshot")
            if "path" in r:
                self.handle_claude(L(
                    f"Read the screenshot at {r['path']} and describe in three sentences what is on screen and what can be done.",
                    f"Lee la captura de pantalla en {r['path']} y describe en tres frases qué hay en pantalla y qué se puede hacer."))
        elif a == "right_click":
            self.desktop("click", "here", "right")
        elif a == "double_click":
            self.desktop("click", "here", "double")
        elif a == "power":
            names = {"shutdown": L("shut the computer down", "apagar la computadora"),
                     "restart": L("restart the computer", "reiniciarla"),
                     "sleep": L("put the computer to sleep", "suspenderla")}
            if self.confirm(L(f"I am going to {names[act['what']]}. Shall I?", f"Voy a {names[act['what']]}. ¿Lo hago?")):
                self.say(L("See you later.", "Hasta luego."))
                self.desktop("power", act["what"])
            else:
                self.say(L("Cancelled.", "Cancelado."))
        elif a == "click_number":
            labels = getattr(self, "_labels", None) or self.desktop("elements")
            self.click_label(labels if isinstance(labels, list) else [], act["n"])
        elif a == "overlay":
            self.overlay_mode()
        elif a == "grid":
            self.grid_mode()

    def click_label(self, labels: list, n: int) -> None:
        for lab in labels:
            if lab.get("n") == n:
                self.desktop("click", str(lab["x"]), str(lab["y"]))
                self.say(lab.get("name") or str(n))
                return
        self.say(L(f"There is no {n}. There are {len(labels)}.", f"No hay {n}. Hay {len(labels)}."))

    # ---- overlay (numbers) and grid: choose by number, or scan with the buttons ----
    def overlay_send(self, msg: dict) -> None:
        if self.overlay is None or self.overlay.poll() is not None:
            script = self.desktop_py.parent / "overlay.py"
            try:
                self.overlay = subprocess.Popen([sys.executable, str(script)], stdin=subprocess.PIPE, text=True,
                                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except OSError:
                return
        try:
            self.overlay.stdin.write(json.dumps(msg) + "\n")
            self.overlay.stdin.flush()
        except (OSError, ValueError):
            self.overlay = None

    def overlay_close(self) -> None:
        if self.overlay and self.overlay.poll() is None:
            try:
                self.overlay.stdin.close()
            except OSError:
                pass
            self.overlay.wait(2)
        self.overlay = None
        self._labels = None

    def overlay_mode(self) -> None:
        labels = self.desktop("elements")
        if not isinstance(labels, list) or not labels:
            self.say(L("I find no controls in this window. Try the grid.",
                       "No encuentro controles en esta ventana. Prueba con la rejilla."))
            return
        self._labels = labels
        sel = 0
        self.overlay_send({"labels": labels, "selected": None})
        self.say(L(f"{len(labels)} numbers. Say one, or press button two to step through and hold button one to click.",
                   f"{len(labels)} números. Di uno, o pulsa el dos para recorrer y mantén el uno para pulsar."))
        try:
            while True:
                ev = self.button.wait()
                if ev is None:
                    continue
                button, gesture = ev
                if (button, gesture) == (NO, LONG):
                    return
                if (button, gesture) == (NO, SHORT):
                    sel = sel % len(labels) + 1
                    self.overlay_send({"labels": labels, "selected": sel})
                    self.speaker.say(labels[sel - 1].get("name") or str(sel), show=False)
                elif (button, gesture) == (TALK, LONG) and sel:
                    self.overlay_close()
                    self.click_label(labels, sel)
                    return
                elif (button, gesture) == (TALK, SHORT):
                    text = self.record_and_transcribe()
                    if text is None:
                        continue
                    t = commands.normalize(text)
                    if t in CANCEL_WORDS:
                        return
                    n = desktop_commands.number(t.split())
                    if n:
                        self.overlay_close()
                        self.click_label(labels, n)
                        return
                    self.say(L("Say a number, or 'cancel'.", "Di un número, o 'cancela'."))
        finally:
            self.overlay_close()

    def grid_mode(self) -> None:
        shot = self.desktop("screenshot")
        w, h = int(shot.get("width") or 1920), int(shot.get("height") or 1080)
        rect = [0, 0, w, h]
        sel = 0
        self.overlay_send({"grid": rect, "selected": None})
        self.say(L("Grid. Say a number from one to nine to zoom in, three times to click. Hold button one to click where it is.",
                   "Rejilla. Di un número del uno al nueve para acercar, tres veces para pulsar. Mantén el uno para pulsar donde está."))
        try:
            for _depth in range(4):
                chosen = None
                while chosen is None:
                    ev = self.button.wait()
                    if ev is None:
                        continue
                    button, gesture = ev
                    if (button, gesture) == (NO, LONG):
                        return
                    if (button, gesture) == (NO, SHORT):
                        sel = sel % 9 + 1
                        self.overlay_send({"grid": rect, "selected": sel})
                        self.speaker.say(str(sel), show=False)
                    elif (button, gesture) == (TALK, LONG):
                        if sel:
                            chosen = sel
                        else:
                            self.overlay_close()
                            self.desktop("click", str(rect[0] + rect[2] // 2), str(rect[1] + rect[3] // 2))
                            return
                    elif (button, gesture) == (TALK, SHORT):
                        text = self.record_and_transcribe()
                        if text is None:
                            continue
                        t = commands.normalize(text)
                        if t in CANCEL_WORDS:
                            return
                        if t in HERE_WORDS:
                            self.overlay_close()
                            self.desktop("click", str(rect[0] + rect[2] // 2), str(rect[1] + rect[3] // 2))
                            return
                        n = desktop_commands.number(t.split())
                        if n and 1 <= n <= 9:
                            chosen = n
                        else:
                            self.say(L("From one to nine, or 'here'.", "Del uno al nueve, o 'aquí'."))
                r, c = divmod(chosen - 1, 3)
                rect = [rect[0] + c * rect[2] // 3, rect[1] + r * rect[3] // 3, rect[2] // 3, rect[3] // 3]
                sel = 0
                if rect[2] < 40 or rect[3] < 40:
                    break
                self.overlay_send({"grid": rect, "selected": None})
            self.overlay_close()
            self.desktop("click", str(rect[0] + rect[2] // 2), str(rect[1] + rect[3] // 2))
            self.say(L("Clicked.", "Pulsado."))
        finally:
            self.overlay_close()

    # ---- handlers --------------------------------------------------------
    def handle_update(self) -> None:
        self.say(L("Looking for updates.", "Buscando actualizaciones."))
        try:
            rel = updater.check()
        except updater.UpdateError as exc:
            self.say(L(f"I could not update. {exc}", f"No pude actualizar. {exc}"))
            return
        if rel is None:
            self.say(L("You already have the newest version.", "Ya tienes la versión más reciente."))
            return
        notes = updater.spoken_notes(rel.notes, language()) or L("No notes about the changes.", "Sin notas de cambios.")
        if not self.confirm(L(f"There is a new version, {rel.tag}. Changes: {notes}. Shall I install it?",
                              f"Hay una versión nueva, {rel.tag}. Cambios: {notes}. ¿La instalo?")):
            self.say(L("Cancelled. I changed nothing.", "Cancelado. No cambié nada."))
            return
        try:
            updater.install(rel.tag)
        except updater.UpdateError as exc:
            self.say(L(f"The installation failed and I changed nothing. {exc}",
                       f"La instalación falló y no cambié nada. {exc}"))
            return
        self.say(L(f"Version {rel.tag} is installed. It will restart in a moment. If something goes wrong, say 'undo'.",
                   f"Instalada la versión {rel.tag}. Se reiniciará en un momento. Si algo va mal, di 'deshacer'."))
        self.log("SISTEMA", f"instalada {rel.tag}; reiniciando")
        sys.exit(3)  # bin/onebutton restarts us on the new version

    def handle_login(self, reason: str = "") -> None:
        """Sign Claude Code in again from the browser, with no keyboard anywhere.

        `claude auth login` runs in a pseudo-terminal and opens the browser on the claude.ai
        authorisation page. He clicks "Autorizar" with the numbered overlay ("números", then the
        number). The page then shows a code the CLI is waiting for: the loop reads it off the
        browser window (desktop.py find_text), or off the clipboard if he clicked the page's
        copy button, and types it into the pseudo-terminal. Claude Code's own status confirms.
        """
        helper = helper_of(self.cfg)
        if self.dry_run:
            self.say(L("(simulated) sign-in", "(simulado) inicio de sesión"))
            return
        if auth.status(self.cfg["claude_bin"], use_credentials=False).get("loggedIn"):
            if auth.retire_token():
                self.agent.shutdown()
            self.say(L("You are already signed in to Claude Code.", "Ya tienes la sesión iniciada en Claude Code."))
            return
        exe = shutil.which(self.cfg["claude_bin"]) or self.cfg["claude_bin"]
        term = login.TerminalProcess([exe, "auth", "login", "--claudeai"])
        if not term.start():
            self.log("LOGIN", f"no pude abrir la terminal: {term.error}")
            self.say(L(f"I could not start the sign-in. {helper} is needed.",
                       f"No pude empezar el inicio de sesión. Hace falta {helper}."))
            return
        how = (L("When you see the Authorize button, say 'numbers' and then its number. I take care of the rest.",
                 "Cuando veas el botón Autorizar, di 'números' y luego su número. Del resto me encargo yo.")
               if self.desktop_enabled else
               L(f"{helper} has to click Authorize and copy the code, because the computadora module is not turned on.",
                 f"Hace falta que {helper} pulse Autorizar y copie el código, porque el módulo computadora no está activado."))
        self.say(L(f"{reason}I am opening the browser to sign in to Claude. {how} "
                   f"If the page asks for a password, {helper} is needed. Say 'cancel' to leave it.",
                   f"{reason}Abro el navegador para iniciar sesión en Claude. {how} "
                   f"Si la página pide contraseña, hace falta {helper}. Di 'cancela' para dejarlo."))
        self.log("SISTEMA", "inicio de sesión por voz")
        deadline = time.monotonic() + 420
        next_status, next_scan, url_opened, code_sent, seen_len = 0.0, 0.0, False, False, 0
        try:
            while time.monotonic() < deadline:
                now = time.monotonic()
                out = term.snapshot()
                if len(out) > seen_len:
                    self.log("LOGIN", out[seen_len:].strip()[-500:])
                    seen_len = len(out)
                if now >= next_status:
                    if auth.status(self.cfg["claude_bin"], use_credentials=False).get("loggedIn"):
                        if auth.retire_token():
                            self.log("SISTEMA", "token antiguo retirado de credentials.env")
                        self.agent.shutdown()   # new processes pick up the new sign-in
                        self.say(L("Signed in. I can work now.", "Sesión iniciada. Ya puedo trabajar."))
                        return
                    next_status = now + 3
                if not term.alive():
                    self.say(L(f"Claude Code closed the sign-in without finishing it. {helper} is needed.",
                               f"Claude Code cerró el inicio de sesión sin terminarlo. Hace falta {helper}."))
                    return
                if not code_sent and now >= next_scan:
                    code = self.find_login_code()
                    if code:
                        term.send_line(code)
                        code_sent = True
                        self.log("LOGIN", "código enviado a la terminal")
                        self.say(L("I have the code. One moment.", "Tengo el código. Un momento."))
                    next_scan = now + 2.5
                ev = self.button.wait(0.5)
                if ev is None:
                    continue
                if ev == (TALK, LONG) or (self.two_buttons and ev == (NO, SHORT)):
                    self.say(L("Cancelled.", "Cancelado."))
                    return
                if ev != (TALK, SHORT):
                    continue
                heard = self.record_and_transcribe()
                if heard is None:
                    continue
                if commands.normalize(heard) in {commands.normalize(w) for w in self.cfg["cancel_words"]}:
                    self.say(L("Cancelled.", "Cancelado."))
                    return
                code = login.extract_code(heard)
                act = desktop_commands.parse(heard) if self.desktop_enabled else None
                if code:
                    term.send_line(code); code_sent = True
                elif act:
                    if self.desktop_act(act) is False:
                        self.say(how)
                elif commands.normalize(heard) in ("abre la pagina", "abre el enlace", "abre el navegador", "open the page",
                                                   "open the link", "open the browser") and login.extract_url(out):
                    import webbrowser
                    webbrowser.open(login.extract_url(out)); url_opened = True
                else:
                    self.say(how)
            self.say(L(f"The sign-in was not completed. {helper} is needed.",
                       f"No se completó el inicio de sesión. Hace falta {helper}."))
        finally:
            term.kill()

    def find_login_code(self) -> str | None:
        """The authorisation code, from the browser window's accessibility tree or the clipboard."""
        code = login.extract_code(login.read_clipboard())
        if code:
            return code
        if self.desktop_enabled:
            found = self.desktop("find_text", login.CODE_RE.pattern)
            if isinstance(found, list):
                for t in found:
                    code = login.extract_code(str(t))
                    if code:
                        return code
        return None

    def handle_update_claude(self) -> None:
        """Upgrade Claude Code itself with its own `claude update`, after a yes."""
        if not self.confirm(L("I am going to look for a new version of Claude Code and install it if there is one.",
                              "Voy a buscar una versión nueva de Claude Code e instalarla si la hay.")):
            self.say(L("Cancelled.", "Cancelado."))
            return
        if self.dry_run:
            self.say(L("(simulated) claude update", "(simulado) claude update"))
            return
        before = auth.version(self.cfg["claude_bin"])
        self.say(L("Looking. It may take a minute.", "Buscando. Puede tardar un minuto."))
        try:
            proc = subprocess.run([shutil.which(self.cfg["claude_bin"]) or self.cfg["claude_bin"], "update"],
                                  capture_output=True, text=True, timeout=600, env=auth.subprocess_env())
        except FileNotFoundError:
            self.say(L("I cannot find Claude Code on this computer.", "No encuentro Claude Code en esta computadora."))
            return
        except subprocess.TimeoutExpired:
            self.say(L("Updating Claude Code took too long and I stopped it.",
                       "La actualización de Claude Code tardó demasiado y la detuve."))
            return
        after = auth.version(self.cfg["claude_bin"])
        out = ((proc.stdout or "") + (proc.stderr or "")).lower()
        self.log("SISTEMA", f"claude update rc={proc.returncode} {before} -> {after}: {out.strip()[-300:]}")
        if proc.returncode != 0 and after == before:
            tail = (proc.stderr or proc.stdout or L("no detail", "sin detalle")).strip().splitlines()[-1]
            self.say(L(f"I could not update Claude Code: {tail}. {helper_of(self.cfg)} may be needed.",
                       f"No pude actualizar Claude Code: {tail}. Quizá haga falta {helper_of(self.cfg)}."))
        elif after and before and after != before:
            self.say(L(f"Claude Code updated from version {before} to {after}.",
                       f"Claude Code actualizado de la versión {before} a la {after}."))
        elif any(k in out for k in ("already", "up to date", "up-to-date", "latest", "no update")):
            self.say(L(f"Claude Code is already on the latest version, {after or before}.",
                       f"Claude Code ya está en la última versión, la {after or before}."))
        else:
            self.say(L(f"Done. Claude Code is on version {after or before}.",
                       f"Listo. Claude Code está en la versión {after or before}."))

    def handle_undo(self) -> None:
        prev = updater.read_state().get("previous")
        if not prev:
            self.say(L("There is no previous version to go back to.", "No hay una versión anterior a la que volver."))
            return
        if not self.confirm(L(f"I will go back to version {prev}. Shall I?", f"Volveré a la versión {prev}. ¿Lo hago?")):
            self.say(L("Cancelled. I changed nothing.", "Cancelado. No cambié nada."))
            return
        try:
            updater.undo()
        except updater.UpdateError as exc:
            self.say(L(f"I could not go back. {exc}", f"No pude volver atrás. {exc}"))
            return
        self.say(L(f"Done, going back to version {prev}. It will restart in a moment.",
                   f"Listo, vuelvo a la versión {prev}. Se reiniciará en un momento."))
        self.log("SISTEMA", f"deshecho a {prev}; reiniciando")
        sys.exit(3)

    # ---- several conversations ---------------------------------------------
    def announce_finished(self) -> None:
        """A finished turn of the current conversation is spoken; one of another conversation is
        announced once, and its reply waits until he switches to it."""
        for c in self.convs.unannounced():
            if c is self.convs.current:
                self.deliver(c)
            else:
                c.announced = True
                n = conversations.spoken(c.n)
                self.say(L(f"Conversation {n} has finished. Say 'conversation {n}' to hear it.",
                           f"Terminó la conversación {n}. Di 'conversación {n}' para oírla."))

    def handle_conversation(self, cmd: dict) -> None:
        kind, n = cmd["kind"], cmd.get("n")
        if kind == conversations.NEW:
            c = self.convs.new()
            self.show_conversation(c)
            self.last_reply = ""
            self.log("SISTEMA", f"conversación {c.n} abierta")
            self.say(L(f"Conversation {conversations.spoken(c.n)}. I am listening.",
                       f"Conversación {conversations.spoken(c.n)}. Te escucho."))
        elif kind == conversations.SWITCH:
            c = self.convs.switch(n)
            if not c:
                self.say(L(f"There is no conversation {conversations.spoken(n)}. {self.convs.summary()}",
                           f"No hay conversación {conversations.spoken(n)}. {self.convs.summary()}"))
                return
            self.show_conversation(c)
            self.last_reply = c.last_reply
            self.log("SISTEMA", f"conversación {c.n}")
            name = L(f"Conversation {conversations.spoken(c.n)}.", f"Conversación {conversations.spoken(c.n)}.")
            if c.replies:
                self.say(name + L(" It has finished.", " Terminó."))
                self.deliver(c)
            elif c.state == conversations.WORKING:
                self.say(name + L(" Still working; I will tell you when it finishes.",
                                  " Sigue trabajando; te aviso cuando termine."))
            else:
                self.say(name)
        elif kind == conversations.CLOSE:
            c = self.convs.get(n) if n else self.convs.current
            if not c:
                self.say(L(f"There is no conversation {conversations.spoken(n)}.",
                           f"No hay conversación {conversations.spoken(n)}."))
                return
            if self.agent:
                self.agent.close(c.session_id)
            self.convs.close(c.n)
            self.show_conversation(self.convs.current)
            self.last_reply = self.convs.current.last_reply
            self.log("SISTEMA", f"conversación {c.n} cerrada")
            now = conversations.spoken(self.convs.current.n)
            self.say(L(f"Conversation {conversations.spoken(c.n)} is closed. You are in number {now}.",
                       f"Cerrada la conversación {conversations.spoken(c.n)}. Estás en la {now}."))
        elif kind == conversations.LIST:
            self.say(self.convs.summary())

    def classify(self, heard: str) -> commands.Command:
        """What an utterance is. At the writing desk "deshacer", "repite" and "update" are about
        his text, not about the installed version or the last reply, so they go to the assistant."""
        cmd = commands.classify(heard, self.cfg)
        if self.convs.current.dictating and cmd.kind in (commands.UNDO, commands.REPEAT, commands.UPDATE):
            return commands.Command(commands.TEXT, heard.strip())
        return cmd

    def handle_text(self, text: str) -> None:
        conv_cmd = conversations.parse(text)
        if conv_cmd:
            self.handle_conversation(conv_cmd)
            return
        conv = self.convs.current
        mode = commands.dictation(text) if "escritorio" in self.panels else None
        if mode:
            # The writing desk: his words go to the assistant exactly as said, and what he says is
            # not taken for an order to the computer (see DICTATION_SAFE) until dictation ends.
            conv.dictating = mode == "start"
            self.log("SISTEMA", f"dictado: {mode}")
            self.handle_claude(text)
            return
        if self.screen_try(text):
            if conv.dictating and self.screen.state().get("panel") not in (None, "escritorio"):
                conv.dictating = False   # he left the desk for another panel
            return
        if self.desktop_enabled and not self.dry_run:
            act = self.desktop_parse(text, conv.dictating)
            if act and act["action"] == "type" and self.screen.state().get("focused"):
                act = None   # the OneButton page is in front: there is no application to type into, so it is for Claude
            if act:
                self.log("EQUIPO", json.dumps(act, ensure_ascii=False))
                if self.desktop_act(act) is not False:
                    return
        self.handle_claude(text)

    @staticmethod
    def outcome(result: dict, done: str) -> str:
        """What to say after an order to the computer. The tool's own error is for the log (it is
        written there by desktop()), not for his ears: it is technical and in one language."""
        return L("I could not do that.", "No pude hacerlo.") if result.get("error") else done

    def desktop_parse(self, text: str, dictating: bool = False) -> dict | None:
        """The direct action an utterance asks for, if any. "Otra vez" repeats the last scroll while
        it is recent and means nothing here otherwise; while dictating only scrolling and volume count."""
        act = desktop_commands.parse(text)
        if not act or (dictating and act["action"] not in DICTATION_SAFE):
            return None
        if act["action"] == "scroll_again":
            last = self.last_scroll
            if not last or time.monotonic() - last[2] > SCROLL_AGAIN_WINDOW:
                return None
            return {"action": "scroll", "dir": last[0], "n": last[1]}
        return act

    def handle_language(self, code: str) -> None:
        """"Speak Spanish", "habla en inglés": change what the computer speaks, now and at every start."""
        if code == language():
            self.say(L(f"I am already speaking {language_name(code)}.", f"Ya estoy hablando {language_name(code)}."))
            return
        from .rules import install as install_rules

        set_language(code)
        self.cfg["speak_language"] = code
        self.speaker.set_language(code)
        install_rules(self.mods, speak=code)   # the assistant's rules name the language it answers in
        if not self.dry_run:
            try:
                save_local(speak_language=code)
            except OSError as exc:
                self.log("SISTEMA", f"no pude guardar el idioma: {exc}")
            if self.agent and not self.convs.working():
                self.agent.shutdown()          # conversations resume under the new rules on their next message
            self.screen.post({"type": "config", "panels": self.panels, "lang": code, **self.screen_look()})
        self.log("SISTEMA", f"idioma: {code}")
        self.say(L("From now on I speak English. I still understand both English and Spanish.",
                   "Desde ahora hablo español. Sigo entendiendo español e inglés."))

    def handle_claude(self, text: str) -> None:
        conv = self.convs.current
        if not conv.title:
            conv.title = conversations.short_title(text)
        self.converse("Tú", text, conv)
        if self.dry_run:
            conv.add_reply(L(f"(simulated) I received: {text}", f"(simulado) Recibí: {text}"))
            self.deliver(conv)
            return
        if conv.state == conversations.WORKING:
            self.say(L("Noted. I will pass it on as soon as I can.", "Anotado. Se lo paso en cuanto pueda."))   # queued into the running turn
        self.send(conv, text)
        self.wait_for(conv)

    def send(self, conv: conversations.Conversation, text: str) -> None:
        """Hand a message to the conversation's Claude Code process; replies come back through add_reply."""
        print(L(f"🤖 Thinking... (conversation {conv.n})", f"🤖 Pensando... (conversación {conv.n})"), flush=True)
        conv.state = conversations.WORKING
        conv.announced = True

        def on_reply(reply: str, conv=conv):
            self.log("BOT", f"[{conv.n}] {reply}")
            self.converse("Asistente", reply, conv)
            conv.add_reply(reply)

        self.agent.send(conv.session_id, text, on_reply)

    def deliver(self, conv: conversations.Conversation) -> None:
        """Speak the finished turns of a conversation, oldest first."""
        lapsed = False
        for reply in conv.take_replies():
            self.last_reply = reply
            print(f"\n{reply}\n", flush=True)
            self.say(reply, clean=True)
            lapsed = lapsed or auth.says_login_needed(reply)
        if lapsed and not self.dry_run:
            self.handle_login()

    def wait_for(self, conv: conversations.Conversation) -> None:
        """Stay with a working conversation: button 2 cancels it, button 1 lets him speak.

        Saying 'nueva conversación' or 'conversación dos' leaves this one working in the
        background and returns to the main loop in the other conversation.
        """
        self.forget_presses()
        next_progress = time.monotonic() + self.progress_interval
        while conv.state == conversations.WORKING:
            act = self.action(THINKING, 0.2)
            if act == A_CANCEL:
                self.agent.cancel(conv.session_id)
                conv.take_replies()
                self.say(L("Cancelled.", "Cancelado."))
                return
            if act == A_REASSURE:
                heard = self.record_and_transcribe()
                if heard is None:
                    continue
                cmd = conversations.parse(heard)
                if cmd:
                    self.handle_conversation(cmd)
                    if self.convs.current is not conv:
                        conv.announced = False   # finishing in the background will be announced
                        return
                    continue
                if commands.normalize(heard) in {commands.normalize(w) for w in self.cfg["cancel_words"]}:
                    self.agent.cancel(conv.session_id)
                    conv.take_replies()
                    self.say(L("Cancelled.", "Cancelado."))
                    return
                # anything else is for this conversation: Claude Code queues it into the running turn
                self.converse("Tú", heard, conv)
                self.send(conv, heard)
                self.say(L("Noted.", "Anotado."))
            elif self.progress_interval > 0 and time.monotonic() >= next_progress:
                self.speaker.say(L("Still on it.", "Sigo en ello."), show=False)
                next_progress = time.monotonic() + 2 * self.progress_interval
        if conv.replies:
            self.deliver(conv)

    # ---- main ------------------------------------------------------------
    def run_setup(self) -> None:
        from . import setup
        from .audio import Recorder
        from .stt import Transcriber

        setup.run(self.cfg, self.speaker, transcriber_factory=lambda c: self.transcriber, recorder_factory=Recorder)
        sys.exit(3)  # the launcher restarts us with the new config

    def run(self) -> None:
        if not self.dry_run and hardware.load() is None:
            self.run_setup()
        if not self.dry_run:
            self.speaker.say(L("One moment, listening to the noise in the room.",
                               "Un momento, escuchando el ruido de la sala."), show=False)
            self.recorder.calibrate()
        self.start_modules()
        if self.button:
            # Whether the button's keys are kept from other programs: if "no", a press also reaches
            # whatever is in front (a space bar pauses a video), and the reason is in the terminal.
            self.log("SISTEMA", f"botón: captura {getattr(self.button, 'source', '?')}, "
                                f"teclas reservadas: {'sí' if getattr(self.button, 'exclusive', False) else 'no'}")
        self.say(banner())
        if not self.dry_run:
            st = auth.status(self.cfg["claude_bin"])
            self.log("SISTEMA", f"auth: {st}")
            if not st.get("loggedIn"):
                self.handle_login(L("Claude Code is not signed in. ", "Claude Code no tiene la sesión iniciada. "))
        try:
            while True:
                try:
                    heard = self.listen_once()
                except KeyboardInterrupt:
                    self.say(L("See you later.", "Hasta luego."))
                    return
                if heard is None:
                    continue
                cmd = self.classify(heard)
                if cmd.kind == commands.EMPTY:
                    self.heard_nothing()
                elif cmd.kind == commands.UPDATE:
                    self.handle_update()
                elif cmd.kind == commands.UPDATE_CLAUDE:
                    self.handle_update_claude()
                elif cmd.kind == commands.LOGIN:
                    self.handle_login()
                elif cmd.kind == commands.UNDO:
                    self.handle_undo()
                elif cmd.kind == commands.REPEAT:
                    self.say(self.last_reply or L("There is nothing to repeat yet.", "No hay nada que repetir todavía."), clean=True)
                elif cmd.kind == commands.SETUP:
                    if self.dry_run:
                        self.say(L("(simulated) button setup", "(simulado) configuración de botones"))
                    else:
                        self.run_setup()
                elif cmd.kind == commands.LANGUAGE:
                    self.handle_language(cmd.text)
                else:
                    self.handle_text(cmd.text)
        finally:
            if self.agent:
                self.agent.shutdown()
            for proc in self.modules:
                proc.terminate()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="onebutton", description="Voice-first computing with one button.")
    ap.add_argument("--version", action="version", version=f"onebutton {__version__}")
    ap.add_argument("--dry-run", action="store_true",
                    help="Type instead of speaking; no audio, no Claude. For testing the loop.")
    ap.add_argument("--check-update", action="store_true", help="Print the newest verified release and exit.")
    ap.add_argument("--check-auth", action="store_true", help="Print Claude Code's sign-in status and exit.")
    ap.add_argument("--setup", action="store_true", help="Run the voice-guided hardware setup and exit.")
    ap.add_argument("--hardware", action="store_true", help="Print detected screens and microphones and exit.")
    ap.add_argument("--voices", action="store_true",
                    help="Print the voice that will speak and the installed voices of the language spoken, and "
                         "the same for the other language; say a test sentence, and exit. Downloads the Piper "
                         "voice of a language the system has no voice for.")
    args = ap.parse_args(argv)
    cfg = load()
    if args.voices:
        from .tts import Speaker
        LOCAL_DIR.mkdir(parents=True, exist_ok=True)
        set_language(cfg["speak_language"])
        speaker = Speaker(cfg)
        info = speaker.describe()
        # The other language too: "speak Spanish" / "habla en inglés" switches at any moment, and a
        # voice that has to be downloaded should be fetched now, by the helper, not then.
        others = []
        for code in SUPPORTED:
            if code != language():
                speaker.set_language(code)
                others.append(speaker.describe())
        speaker.set_language(language())
        print(json.dumps(dict(info, other_languages=others), indent=2, ensure_ascii=False))
        speaker.say(L("This is the OneButton voice.", "Esta es la voz de OneButton."))
        return 0 if info["speaks_the_language"] else 1
    if args.hardware:
        print(json.dumps(hardware.detect(), indent=2, ensure_ascii=False))
        return 0
    if args.setup:
        LOCAL_DIR.mkdir(parents=True, exist_ok=True)
        Loop(cfg).run_setup()
        return 0
    if args.check_auth:
        st = auth.status(cfg["claude_bin"])
        print(json.dumps(st, indent=2))
        return 0 if st.get("loggedIn") else 1
    if args.check_update:
        try:
            rel = updater.check()
        except updater.UpdateError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        print("up to date" if rel is None else f"{rel.tag}\n\n{rel.notes}")
        return 0
    LOCAL_DIR.mkdir(parents=True, exist_ok=True)
    Loop(cfg, dry_run=args.dry_run).run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
