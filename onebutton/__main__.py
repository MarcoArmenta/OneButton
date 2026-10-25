"""The OneButton loop.

    press -> record -> press -> transcribe -> screen, command, or Claude turn -> speak

One or two buttons, two gestures each; see gestures.py for the mapping. With
two buttons, yes and no never depend on speech recognition. Local commands
("actualiza", "deshacer", "repite") never reach the agent, and anything that
changes the installed version is read aloud and waits for a yes.

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
import subprocess
import sys
import threading
import time
from pathlib import Path

from . import __version__, auth, commands, desktop_commands, hardware, updater
from .config import LOCAL_DIR, WORKSPACE_DIR, load
from .gestures import (A_CANCEL, A_HELP, A_NO, A_REASSURE, A_REPEAT, A_STOP, A_TALK, A_YES,
                       CONFIRMING, IDLE, LONG, NO, RECORDING, SHORT, TALK, THINKING, help_text, interpret)

BANNER = "OneButton listo. Pulsa el botón y habla. Pulsa otra vez cuando termines."


class Loop:
    def __init__(self, cfg: dict, dry_run: bool = False):
        from .rules import install as install_rules
        from .tts import Speaker

        self.cfg = cfg
        self.dry_run = dry_run
        self.speaker = Speaker(cfg)
        self.last_reply = ""
        self.progress_interval = float(cfg.get("progress_interval", 45))
        self.log_path = LOCAL_DIR / "session.log" if cfg.get("log_transcripts", True) else None
        self.modules: list[subprocess.Popen] = []
        from .board import Board
        self.screen = Board(int(cfg.get("screen_port") or cfg.get("pizarra_port") or 8765))
        self.screen_alive_until = 0.0
        mods = list(cfg.get("modules") or [])
        self.panels = ["conversacion"] + (["pizarra"] if "maths-screen" in mods else []) + \
            (["escritorio"] if "scribe" in mods else [])
        self.conversation = WORKSPACE_DIR / "conversacion.md"
        self.desktop_enabled = "computadora" in mods
        self.desktop_py = Path(__file__).resolve().parent.parent / "modules" / "computadora" / "desktop.py"
        self.overlay: subprocess.Popen | None = None
        install_rules(mods)
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
                                      "refractory": float(cfg["press_refractory"]), "long_hold": float(cfg["long_hold"])})
        self.recorder = Recorder(cfg)
        self.transcriber = Transcriber(cfg)
        self.agent = Agent(cfg)

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

    def screen_look(self) -> dict:
        """Theme, layout and text size for the page. The "glasses" preset suits OLED display glasses."""
        preset = self.cfg.get("screen_preset") or "auto"
        if preset == "auto":
            info = hardware.load() or {}
            preset = info.get("suggested_preset") or hardware.suggest_preset(hardware.screens())
        look = {"monitor": {"theme": "auto", "layout": "tabs", "font_size": 28},
                "glasses": {"theme": "glasses", "layout": "wide", "font_size": 30},
                "tablet": {"theme": "auto", "layout": "tabs", "font_size": 24}}.get(preset, {})
        for key in ("theme", "layout", "font_size"):
            if self.cfg.get(f"screen_{key}") not in (None, "", "auto"):
                look[key] = self.cfg[f"screen_{key}"]
        if look.get("theme") == "auto":
            look.pop("theme")
        return look

    def converse(self, who: str, text: str) -> None:
        """Append a turn to workspace/conversacion.md, which the screen shows in large type."""
        try:
            WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
            stamp = dt.datetime.now().strftime("%H:%M")
            with self.conversation.open("a", encoding="utf-8") as fh:
                fh.write(f"## {stamp} {who}\n\n{text.strip()}\n\n")
            if self.conversation.stat().st_size > 400_000:  # keep the file light: drop the oldest half
                parts = self.conversation.read_text(encoding="utf-8").split("\n## ")
                self.conversation.write_text("## " + "\n## ".join(parts[len(parts) // 2:]).lstrip("# "), encoding="utf-8")
        except OSError:
            pass

    def screen_try(self, text: str) -> bool:
        """Offer a short utterance to the screen first (panel names, "lee ..."). True if it took it."""
        if self.dry_run or len(commands.normalize(text).split()) > 4:
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
        """Speak, and let any button press cut it short. The press is consumed."""
        if self.dry_run or not self.button:
            self.speaker.say(text, clean=clean)
            return
        self.button.clear()
        finished = self.speaker.say(text, until=lambda: not self.button.events.empty(), clean=clean)
        if not finished:
            self.button.clear()

    def start_modules(self) -> None:
        """Start the screen, then any long-running helper a module ships."""
        from .rules import MODULES_DIR

        if not self.dry_run or self.cfg.get("screen_in_dry_run"):
            screen = Path(__file__).resolve().parent / "screen" / "start.py"
            env = dict(os.environ)
            if not self.cfg.get("open_browser", True):
                env["ONEBUTTON_NO_BROWSER"] = "1"
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
            self.screen.post({"type": "config", "panels": self.panels, **self.screen_look()})
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
        return None if ev is None else interpret(ev, state, self.two_buttons)

    def listen_once(self) -> str | None:
        """Wait idle for a press, record until the next press, return text. None if cancelled."""
        if self.dry_run:
            try:
                return input("\n[tú] ")
            except EOFError:
                raise KeyboardInterrupt
        while True:
            act = self.action(IDLE)
            if act == A_TALK:
                return self.record_and_transcribe()
            if act == A_HELP:
                if self.two_buttons and self.screen.available():
                    self.screen_mode()
                else:
                    self.say(help_text(self.two_buttons))
            elif act == A_REPEAT:
                self.say(self.last_reply or "No hay nada que repetir todavía.", clean=True)

    def record_and_transcribe(self) -> str | None:
        """Recording starts now. Ends on the next press; None if cancelled."""
        print("🎙️  Grabando... (pulsa para terminar)", flush=True)
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

        threading.Thread(target=watch_button, daemon=True).start()
        audio = self.recorder.record_until(stop)
        stop.set()
        if cancelled.is_set():
            self.say("Cancelado.")
            return None
        print("⏳ Transcribiendo...", flush=True)
        text = self.transcriber.transcribe(audio)
        print(f"[tú] {text}", flush=True)
        self.log("TÚ", text)
        return text

    def confirm(self, question: str) -> bool:
        """Ask aloud; yes is a held talk button (two-button setups) or a spoken confirm word."""
        if self.two_buttons:
            self.say(question + " Mantén pulsado el botón uno para decir sí, o pulsa el botón dos para cancelar. "
                     "También puedes decir 'adelante'.")
        else:
            self.say(question + " Di 'adelante' para continuar, o cualquier otra cosa para cancelar.")
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
            self.say("Menú.")
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
                    if commands.normalize(text) in ("salir", "sal", "listo", "terminar", "cerrar"):
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
            self.say("No entendí. Di el nombre de un panel, un número, o 'salir'.")
        return st

    def dictate_latex(self, text: str) -> None:
        print("🤖 Convirtiendo a LaTeX...", flush=True)
        latex = self.agent.convert_latex(text)
        if not latex:
            self.say("No pude convertirlo. Dilo otra vez.")
            return
        self.log("LATEX", f"{text} -> {latex}")
        self.screen.post({"type": "latex", "text": latex})

    # ---- the computer ------------------------------------------------------
    def desktop(self, *args: str) -> dict:
        try:
            proc = subprocess.run([sys.executable, str(self.desktop_py), *args], capture_output=True, text=True, timeout=30)
            return json.loads(proc.stdout.strip() or "{}")
        except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError) as exc:
            return {"error": str(exc)}

    def desktop_act(self, act: dict) -> None:
        a = act["action"]
        if a == "windows":
            wins = self.desktop("windows")
            titles = [w["title"] for w in wins if isinstance(w, dict)][:8] if isinstance(wins, list) else []
            self.say("Ventanas: " + ". ".join(titles) + "." if titles else "No veo ventanas.")
        elif a in ("focus", "open"):
            r = self.desktop(a, act["target"])
            self.say(r.get("focused") or r.get("opened") or r.get("error", "Hecho."))
        elif a in ("minimize", "maximize"):
            self.say(self.desktop(a).get("error", "Hecho."))
        elif a == "key":
            self.say(self.desktop("key", act["keys"]).get("error", "Hecho."), clean=True)
        elif a == "type":
            self.say(self.desktop("type", act["text"]).get("error", "Escrito."))
        elif a == "scroll":
            self.desktop("scroll", act["dir"], str(act["n"]))
        elif a == "volume":
            self.say(self.desktop("volume", act["what"]).get("error", ""))
        elif a == "screenshot":
            r = self.desktop("screenshot")
            self.say("Captura guardada." if "path" in r else r.get("error", ""))
        elif a == "describe":
            r = self.desktop("screenshot")
            if "path" in r:
                self.handle_claude(f"Lee la captura de pantalla en {r['path']} y describe en tres frases qué hay en pantalla y qué se puede hacer.")
        elif a == "right_click":
            self.desktop("click", "here", "right")
        elif a == "double_click":
            self.desktop("click", "here", "double")
        elif a == "power":
            names = {"shutdown": "apagar la computadora", "restart": "reiniciarla", "sleep": "suspenderla"}
            if self.confirm(f"Voy a {names[act['what']]}. ¿Lo hago?"):
                self.say("Hasta luego.")
                self.desktop("power", act["what"])
            else:
                self.say("Cancelado.")
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
        self.say(f"No hay {n}. Hay {len(labels)}.")

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
            self.say("No encuentro controles en esta ventana. Prueba con la rejilla.")
            return
        self._labels = labels
        sel = 0
        self.overlay_send({"labels": labels, "selected": None})
        self.say(f"{len(labels)} números. Di uno, o pulsa el dos para recorrer y mantén el uno para pulsar.")
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
                    if t in ("cancela", "cancelar", "salir", "quita", "no"):
                        return
                    n = desktop_commands.number(t.split())
                    if n:
                        self.overlay_close()
                        self.click_label(labels, n)
                        return
                    self.say("Di un número, o 'cancela'.")
        finally:
            self.overlay_close()

    def grid_mode(self) -> None:
        shot = self.desktop("screenshot")
        w, h = int(shot.get("width") or 1920), int(shot.get("height") or 1080)
        rect = [0, 0, w, h]
        sel = 0
        self.overlay_send({"grid": rect, "selected": None})
        self.say("Rejilla. Di un número del uno al nueve para acercar, tres veces para pulsar. Mantén el uno para pulsar donde está.")
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
                        if t in ("cancela", "cancelar", "salir", "no"):
                            return
                        if t in ("aqui", "pulsa", "clic", "click", "ahi"):
                            self.overlay_close()
                            self.desktop("click", str(rect[0] + rect[2] // 2), str(rect[1] + rect[3] // 2))
                            return
                        n = desktop_commands.number(t.split())
                        if n and 1 <= n <= 9:
                            chosen = n
                        else:
                            self.say("Del uno al nueve, o 'aquí'.")
                r, c = divmod(chosen - 1, 3)
                rect = [rect[0] + c * rect[2] // 3, rect[1] + r * rect[3] // 3, rect[2] // 3, rect[3] // 3]
                sel = 0
                if rect[2] < 40 or rect[3] < 40:
                    break
                self.overlay_send({"grid": rect, "selected": None})
            self.overlay_close()
            self.desktop("click", str(rect[0] + rect[2] // 2), str(rect[1] + rect[3] // 2))
            self.say("Pulsado.")
        finally:
            self.overlay_close()

    # ---- handlers --------------------------------------------------------
    def handle_update(self) -> None:
        self.say("Buscando actualizaciones.")
        try:
            rel = updater.check()
        except updater.UpdateError as exc:
            self.say(f"No pude actualizar. {exc}")
            return
        if rel is None:
            self.say("Ya tienes la versión más reciente.")
            return
        notes = rel.notes or "Sin notas de cambios."
        if not self.confirm(f"Hay una versión nueva, {rel.tag}. Cambios: {notes}. ¿La instalo?"):
            self.say("Cancelado. No cambié nada.")
            return
        try:
            updater.install(rel.tag)
        except updater.UpdateError as exc:
            self.say(f"La instalación falló y no cambié nada. {exc}")
            return
        self.say(f"Instalada la versión {rel.tag}. Se reiniciará en un momento. Si algo va mal, di 'deshacer'.")
        self.log("SISTEMA", f"instalada {rel.tag}; reiniciando")
        sys.exit(3)  # bin/onebutton restarts us on the new version

    def handle_undo(self) -> None:
        prev = updater.read_state().get("previous")
        if not prev:
            self.say("No hay una versión anterior a la que volver.")
            return
        if not self.confirm(f"Volveré a la versión {prev}. ¿Lo hago?"):
            self.say("Cancelado. No cambié nada.")
            return
        try:
            updater.undo()
        except updater.UpdateError as exc:
            self.say(f"No pude volver atrás. {exc}")
            return
        self.say(f"Listo, vuelvo a la versión {prev}. Se reiniciará en un momento.")
        self.log("SISTEMA", f"deshecho a {prev}; reiniciando")
        sys.exit(3)

    def handle_text(self, text: str) -> None:
        if self.screen_try(text):
            return
        if self.desktop_enabled and not self.dry_run:
            act = desktop_commands.parse(text)
            if act:
                self.log("EQUIPO", json.dumps(act, ensure_ascii=False))
                self.desktop_act(act)
                return
        self.handle_claude(text)

    def handle_claude(self, text: str) -> None:
        self.converse("Tú", text)
        if self.dry_run:
            reply = f"(simulado) Recibí: {text}"
        else:
            reply = self.ask_with_button(text)
        self.last_reply = reply
        self.log("BOT", reply)
        self.converse("Asistente", reply)
        print(f"\n{reply}\n", flush=True)
        self.say(reply, clean=True)

    def ask_with_button(self, text: str) -> str:
        """Run the Claude turn in a thread; a long press cancels it, a short press reassures."""
        print("🤖 Pensando...", flush=True)
        result: dict = {}

        def work():
            result["reply"] = self.agent.ask(text)

        t = threading.Thread(target=work, daemon=True)
        t.start()
        self.button.clear()
        started = time.monotonic()
        next_progress = started + self.progress_interval
        while t.is_alive():
            act = self.action(THINKING, 0.2)
            if act == A_CANCEL:
                self.agent.cancel()
                t.join(5)
                return "Cancelado."
            if act == A_REASSURE:
                hint = "Pulsa el botón dos si quieres cancelar." if self.two_buttons \
                    else "Mantén pulsado el botón si quieres cancelar."
                self.speaker.say(f"Sigo trabajando. {hint}", show=False)
            elif self.progress_interval > 0 and time.monotonic() >= next_progress:
                self.speaker.say("Sigo en ello.", show=False)
                next_progress = time.monotonic() + 2 * self.progress_interval
        return result.get("reply", "")

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
            self.speaker.say("Un momento, escuchando el ruido de la sala.", show=False)
            self.recorder.calibrate()
        self.start_modules()
        self.say(BANNER)
        if not self.dry_run:
            st = auth.status(self.cfg["claude_bin"])
            self.log("SISTEMA", f"auth: {st}")
            if not st.get("loggedIn"):
                self.say(auth.login_message(self.cfg.get("helper_name") or "la persona que te ayuda"))
        try:
            while True:
                try:
                    heard = self.listen_once()
                except KeyboardInterrupt:
                    self.say("Hasta luego.")
                    return
                if heard is None:
                    continue
                cmd = commands.classify(heard, self.cfg)
                if cmd.kind == commands.EMPTY:
                    self.say("No escuché nada. Pulsa el botón y vuelve a intentarlo.")
                elif cmd.kind == commands.UPDATE:
                    self.handle_update()
                elif cmd.kind == commands.UNDO:
                    self.handle_undo()
                elif cmd.kind == commands.REPEAT:
                    self.say(self.last_reply or "No hay nada que repetir todavía.", clean=True)
                elif cmd.kind == commands.SETUP:
                    if self.dry_run:
                        self.say("(simulado) configuración de botones")
                    else:
                        self.run_setup()
                else:
                    self.handle_text(cmd.text)
        finally:
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
    args = ap.parse_args(argv)
    cfg = load()
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
