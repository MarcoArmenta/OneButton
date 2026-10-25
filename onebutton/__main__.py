"""The OneButton loop.

    press -> record -> press -> transcribe -> command or Claude turn -> speak

One or two buttons, two gestures each; see gestures.py for the mapping. With
two buttons, yes and no never depend on speech recognition. Local commands
("actualiza", "deshacer", "repite") never reach the agent, and anything that
changes the installed version is read aloud and waits for a yes.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
import threading
import time

from . import __version__, auth, commands, updater
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
        self.board = None
        if "maths-screen" in (cfg.get("modules") or []):
            from .board import Board
            self.board = Board(int(cfg.get("pizarra_port", 8765)))
        install_rules(list(cfg.get("modules") or []))
        self.two_buttons = bool(cfg.get("button2_key"))
        if dry_run:
            self.button = self.recorder = self.transcriber = self.agent = None
            return
        from .agent import Agent
        from .button import Button
        from .audio import Recorder
        from .stt import Transcriber

        self.button = Button({"talk": cfg["button_key"], "no": cfg.get("button2_key")},
                             cfg.get("button_source", "auto"))
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
        """Start any long-running helper a module ships (e.g. the maths blackboard server)."""
        from .rules import MODULES_DIR

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
                if self.two_buttons and self.board and self.board.available():
                    self.board_mode()
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

    # ---- board mode --------------------------------------------------------
    def board_mode(self) -> None:
        """Hold of button 2 with the blackboard running: buttons and voice drive the board.

        Button 2 short steps, button 1 held selects, button 1 short records a
        number, a menu word or content. Button 2 held leaves. The page does the
        rest and speaks for itself; see modules/maths-screen/board.js.
        """
        self.say("Pizarra.")
        self.log("SISTEMA", "modo pizarra")
        self.board.post({"type": "enter"})
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
                    if commands.normalize(text) in ("salir", "sal", "listo", "terminar"):
                        return
                    self.board_voice(text)
                else:
                    self.board.post({"type": "button", "button": button, "gesture": gesture})
        finally:
            self.board.post({"type": "exit"})
            self.say("Salgo de la pizarra.")

    def board_voice(self, text: str) -> None:
        st = self.board.state()
        if st.get("awaiting"):
            self.dictate_latex(text)
            return
        seq = self.board.post({"type": "voice", "text": text})
        st = self.board.wait_handled(seq)
        if st.get("handled") is False and st.get("selected"):
            self.dictate_latex(text)  # free-form edit of the selection

    def dictate_latex(self, text: str) -> None:
        print("🤖 Convirtiendo a LaTeX...", flush=True)
        latex = self.agent.convert_latex(text)
        if not latex:
            self.say("No pude convertirlo. Dilo otra vez.")
            return
        self.log("LATEX", f"{text} -> {latex}")
        self.board.post({"type": "latex", "text": latex})

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
        if self.dry_run:
            reply = f"(simulado) Recibí: {text}"
        else:
            reply = self.ask_with_button(text)
        self.last_reply = reply
        self.log("BOT", reply)
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
    def run(self) -> None:
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
    args = ap.parse_args(argv)
    cfg = load()
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
