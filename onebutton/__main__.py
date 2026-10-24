"""The OneButton loop.

    press button -> record -> transcribe -> local command or Claude turn -> speak reply

Local commands (update, undo, repeat) never reach the agent. Anything that
changes the installed version is read aloud first and waits for a spoken
confirmation word; anything else said counts as "no".
"""

from __future__ import annotations

import argparse
import sys
import threading
import time

from . import __version__, commands, updater
from .config import LOCAL_DIR, WORKSPACE_DIR, load

BANNER = "OneButton listo. Pulsa el botón y habla. Pulsa otra vez cuando termines."


class Loop:
    def __init__(self, cfg: dict, dry_run: bool = False):
        from .tts import Speaker

        self.cfg = cfg
        self.speaker = Speaker(cfg)
        self.last_reply = ""
        self.dry_run = dry_run
        if dry_run:
            self.listener = self.recorder = self.transcriber = self.agent = None
            return
        from .agent import Agent
        from .audio import ButtonListener, Recorder
        from .stt import Transcriber

        WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
        self.listener = ButtonListener(cfg["button_key"])
        self.recorder = Recorder(cfg)
        self.transcriber = Transcriber(cfg)
        self.agent = Agent(cfg)

    # ---- input -----------------------------------------------------------
    def listen_once(self) -> str:
        """Block until the button is pressed, record until pressed again, return text."""
        if self.dry_run:
            try:
                return input("\n[tú] ")
            except EOFError:
                raise KeyboardInterrupt
        self.listener.wait()
        print("🎙️  Grabando...", flush=True)
        stop = threading.Event()

        def watch_button():
            self.listener.wait()
            stop.set()

        threading.Thread(target=watch_button, daemon=True).start()
        audio = self.recorder.record_until(stop)
        stop.set()
        print("⏳ Transcribiendo...", flush=True)
        text = self.transcriber.transcribe(audio)
        print(f"[tú] {text}", flush=True)
        return text

    def confirm(self, question: str) -> bool:
        self.speaker.say(question + " Di 'adelante' para continuar, o cualquier otra cosa para cancelar.")
        heard = self.listen_once()
        cmd = commands.classify(heard, self.cfg, awaiting_confirmation=True)
        return cmd.kind == commands.CONFIRM

    # ---- handlers --------------------------------------------------------
    def handle_update(self) -> None:
        self.speaker.say("Buscando actualizaciones.")
        try:
            rel = updater.check()
        except updater.UpdateError as exc:
            self.speaker.say(f"No pude actualizar. {exc}")
            return
        if rel is None:
            self.speaker.say("Ya tienes la versión más reciente.")
            return
        notes = rel.notes or "Sin notas de cambios."
        if not self.confirm(f"Hay una versión nueva, {rel.tag}. Cambios: {notes}. ¿La instalo?"):
            self.speaker.say("Cancelado. No cambié nada.")
            return
        try:
            updater.install(rel.tag)
        except updater.UpdateError as exc:
            self.speaker.say(f"La instalación falló y no cambié nada. {exc}")
            return
        self.speaker.say(f"Instalada la versión {rel.tag}. Si algo va mal, di 'deshacer'.")

    def handle_undo(self) -> None:
        state = updater.read_state()
        prev = state.get("previous")
        if not prev:
            self.speaker.say("No hay una versión anterior a la que volver.")
            return
        if not self.confirm(f"Volveré a la versión {prev}. ¿Lo hago?"):
            self.speaker.say("Cancelado. No cambié nada.")
            return
        try:
            updater.undo()
        except updater.UpdateError as exc:
            self.speaker.say(f"No pude volver atrás. {exc}")
            return
        self.speaker.say(f"Listo, estás de nuevo en la versión {prev}.")

    def handle_text(self, text: str) -> None:
        if self.dry_run:
            reply = f"(simulado) Recibí: {text}"
        else:
            print("🤖 Pensando...", flush=True)
            reply = self.agent.ask(text)
        self.last_reply = reply
        print(f"\n{reply}\n", flush=True)
        self.speaker.say(reply, show=False)

    # ---- main ------------------------------------------------------------
    def run(self) -> None:
        self.speaker.say(BANNER)
        while True:
            try:
                heard = self.listen_once()
            except KeyboardInterrupt:
                self.speaker.say("Hasta luego.")
                return
            cmd = commands.classify(heard, self.cfg)
            if cmd.kind == commands.EMPTY:
                self.speaker.say("No escuché nada. Pulsa el botón y vuelve a intentarlo.")
            elif cmd.kind == commands.UPDATE:
                self.handle_update()
            elif cmd.kind == commands.UNDO:
                self.handle_undo()
            elif cmd.kind == commands.REPEAT:
                self.speaker.say(self.last_reply or "No hay nada que repetir todavía.")
            else:
                self.handle_text(cmd.text)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="onebutton", description="Voice-first computing with one button.")
    ap.add_argument("--version", action="version", version=f"onebutton {__version__}")
    ap.add_argument("--dry-run", action="store_true", help="Type instead of speaking; no audio, no Claude. For testing the loop.")
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
