"""One button, two gestures.

A short press and a long press (held about 1.5 s) are the whole vocabulary.
Events are put on a queue as "short" or "long".

Two sources, chosen by `button_source` in the config:

- global: pynput listens system-wide. Needs Input Monitoring permission on
  macOS and X11 on Linux (Wayland does not allow global key capture).
- terminal: the key is read from the terminal, which must stay focused. Works
  everywhere, needs no permissions. A held key auto-repeats, so a burst of
  repeats within a short window counts as a long press.

"auto" tries global and falls back to terminal.
"""

from __future__ import annotations

import os
import queue
import select
import sys
import threading
import time

SHORT, LONG = "short", "long"
LONG_PRESS_SECONDS = 1.5
BURST_WINDOW = 0.7       # terminal mode: window after first keypress
BURST_COUNT = 6          # terminal mode: repeats within window that mean "held"


class Button:
    def __init__(self, key_name: str = "space", source: str = "auto"):
        self.events: queue.Queue[str] = queue.Queue()
        self.key_name = key_name
        self.source = source
        self._drain_only = False
        if source in ("auto", "global"):
            try:
                self._start_global()
                self.source = "global"
                self._drain_only = True
            except Exception as exc:
                if source == "global":
                    raise
                print(f"[button] captura global no disponible ({exc}); usando la terminal.", file=sys.stderr)
                self.source = "terminal"
        if self.source == "terminal" or self._drain_only:
            self._start_terminal(drain_only=self._drain_only)

    # ---- API -----------------------------------------------------------
    def wait(self, timeout: float | None = None) -> str | None:
        try:
            return self.events.get(timeout=timeout)
        except queue.Empty:
            return None

    def poll(self) -> str | None:
        return self.wait(0)

    def clear(self) -> None:
        while self.poll() is not None:
            pass

    # ---- global (pynput) -----------------------------------------------
    def _start_global(self) -> None:
        from pynput import keyboard

        key = getattr(keyboard.Key, self.key_name, None) or keyboard.KeyCode.from_char(self.key_name)
        state = {"down_at": None, "long_sent": False}
        lock = threading.Lock()

        def on_press(k):
            if k != key:
                return
            with lock:
                if state["down_at"] is None:          # ignore auto-repeat while held
                    state["down_at"] = time.monotonic()
                    state["long_sent"] = False

        def on_release(k):
            if k != key:
                return
            with lock:
                down = state["down_at"]
                state["down_at"] = None
                if down is None or state["long_sent"]:
                    return
                self.events.put(LONG if time.monotonic() - down >= LONG_PRESS_SECONDS else SHORT)

        def watcher():  # fire LONG as soon as the threshold is crossed, without waiting for release
            while True:
                time.sleep(0.1)
                with lock:
                    d = state["down_at"]
                    if d is not None and not state["long_sent"] and time.monotonic() - d >= LONG_PRESS_SECONDS:
                        state["long_sent"] = True
                        self.events.put(LONG)

        listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        listener.daemon = True
        listener.start()
        time.sleep(0.2)
        if not listener.is_alive():
            raise RuntimeError("pynput listener did not start")
        threading.Thread(target=watcher, daemon=True).start()

    # ---- terminal ------------------------------------------------------
    def _start_terminal(self, drain_only: bool) -> None:
        if not sys.stdin.isatty():
            if not drain_only:
                raise RuntimeError("la terminal no es interactiva; no puedo leer el botón")
            return
        import termios
        import tty

        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        tty.setcbreak(fd)
        new = termios.tcgetattr(fd)
        new[3] &= ~termios.ECHO
        termios.tcsetattr(fd, termios.TCSANOW, new)
        import atexit
        atexit.register(lambda: termios.tcsetattr(fd, termios.TCSANOW, old))
        target = " " if self.key_name == "space" else self.key_name[:1]

        def reader():
            burst_start = None
            count = 0
            while True:
                timeout = None if burst_start is None else max(0.0, burst_start + BURST_WINDOW - time.monotonic())
                r, _, _ = select.select([fd], [], [], timeout)
                now = time.monotonic()
                if r:
                    ch = os.read(fd, 64).decode(errors="ignore")
                    hits = ch.count(target)
                    if drain_only or hits == 0:
                        continue
                    if burst_start is None:
                        burst_start, count = now, hits
                    else:
                        count += hits
                    if count >= BURST_COUNT:
                        self.events.put(LONG)
                        self._swallow(fd, 0.8)
                        burst_start, count = None, 0
                elif burst_start is not None:
                    self.events.put(SHORT)
                    burst_start, count = None, 0

        threading.Thread(target=reader, daemon=True).start()

    @staticmethod
    def _swallow(fd: int, seconds: float) -> None:
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            r, _, _ = select.select([fd], [], [], 0.05)
            if r:
                os.read(fd, 256)
