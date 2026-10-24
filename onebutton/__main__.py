"""The OneButton loop.

    short press -> record -> short press -> transcribe -> command or Claude turn -> speak

One button, two gestures. Short press starts and stops recording, and stops
speech. Long press (held ~1.5 s) cancels whatever is happening: a recording,
a Claude turn, or a pending confirmation. Local commands ("actualiza",
"deshacer", "repite") never reach the agent, and anything that changes the
installed version is read aloud and waits for a spoken confirmation word.
"""

from __future__ import annotations

import argparse
import datetime as dt
import subprocess
import sys
import threading
import time

from . import __version__, commands, updater
from .button import LONG, SHORT
from .config import LOCAL_DIR, WORKSPACE_DIR, load

BANNER = "OneButton listo. Pulsa el botón y habla. Pulsa otra vez cuando termines."
HELP = ("Pulsa una vez para hablar y otra vez para terminar. "
        "Mantén pulsado para cancelar. Di 'repite' para oír la última respuesta, "
        "'actualiza' para buscar mejoras, o 'deshacer' para volver a la versión anterior.")


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
        install_rules(list(cfg.get("modules") or []))
        if dry_run:
            self.button = self.recorder = self.transcriber = self.agent = None
            return
        from .agent import Agent
        from .button import Button
        from .audio import Recorder
        from .stt import Transcriber

        self.button = Button(cfg["button_key"], cfg.get("button_source", "auto"))
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
    def listen_once(self) -> str | None:
        """Wait for a press, record until the next press, return text. None if cancelled."""
        if self.dry_run:
            try:
                return input("\n[tú] ")
            except EOFError:
                raise KeyboardInterrupt
        while True:
            ev = self.button.wait()
            if ev == SHORT:
                break
            if ev == LONG:
                self.say(HELP)
        print("🎙️  Grabando... (pulsa para terminar)", flush=True)
        stop = threading.Event()
        cancelled = threading.Event()

        def watch_button():
            while not stop.is_set():
                ev = self.button.wait(0.1)
                if ev == SHORT:
                    stop.set()
                elif ev == LONG:
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
        self.say(question + " Di 'adelante' para continuar, o cualquier otra cosa para cancelar.")
        heard = self.listen_once()
        if heard is None:
            return False
        return commands.classify(heard, self.cfg, awaiting_confirmation=True).kind == commands.CONFIRM

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
            ev = self.button.wait(0.2)
            if ev == LONG:
                self.agent.cancel()
                t.join(5)
                return "Cancelado."
            if ev == SHORT:
                self.speaker.say("Sigo trabajando. Mantén pulsado el botón si quieres cancelar.", show=False)
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
    args = ap.parse_args(argv)
    cfg = load()
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
