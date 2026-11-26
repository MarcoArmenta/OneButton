"""One or two buttons, two gestures each.

Events are (button, gesture) tuples: button is "talk" or "no", gesture is
"short" or "long" (held about 1.5 s). They are put on a queue.

Two sources, chosen by `button_source` in the config:

- global: pynput listens system-wide. Works out of the box on Windows. Needs
  Input Monitoring permission on macOS and X11 on Linux (Wayland does not
  allow global key capture).
- terminal: keys are read from the terminal, which must stay focused. Works
  everywhere, needs no permissions. A held key auto-repeats, so a burst of
  repeats within a short window counts as a long press.

"auto" tries global and falls back to terminal.

The button is a keyboard key, and with global capture the key would also reach
whatever window has the focus: a space bar pages a PDF down, Enter submits a
form. With `exclusive` (the default) the button keys are swallowed, so they
mean something to OneButton only. Keys that a program types (desktop.py
pressing Enter for him) are not the button: they pass through to the
application and are not counted as presses. Swallowing works on Windows and
macOS; X11 has no way to do it for one key.
"""

from __future__ import annotations

import os
import queue
import select
import sys
import threading
import time

from .gestures import LONG, NO, SHORT, TALK
from .presses import PressFilter

LONG_PRESS_SECONDS = 1.5
BURST_WINDOW = 0.7       # terminal mode: window after first keypress
BURST_COUNT = 6          # terminal mode: repeats within window that mean "held"

_TERMINAL_CHARS = {"space": {" "}, "enter": {"\r", "\n"}, "tab": {"\t"}}

_WIN_KEY_DOWN = (0x0100, 0x0104)   # WM_KEYDOWN, WM_SYSKEYDOWN
_WIN_INJECTED = 0x12               # LLKHF_INJECTED | LLKHF_LOWER_IL_INJECTED: typed by a program, not a finger


def win32_filter(vk_to_button: dict, down, up, suppress):
    """The low-level keyboard filter for Windows, as pynput wants it.

    A physical press of a button key is counted (`down(name)` / `up(name)`) and swallowed
    (`suppress()`, which in pynput raises, so nothing after it runs). An injected one is
    neither: returning False keeps it from the listener and lets the application have it.
    Any other key is none of our business.
    """
    def event_filter(msg, data):
        name = vk_to_button.get(data.vkCode)
        if name is None:
            return True
        if data.flags & _WIN_INJECTED:
            return False
        (down if msg in _WIN_KEY_DOWN else up)(name)
        suppress()
        return False
    return event_filter


def darwin_intercept(keycodes: set, keycode_of, pid_of):
    """The event-tap callback for macOS: returning None swallows the event.

    Only presses from the keyboard itself (source pid 0) are swallowed; what a program posts
    goes through. pynput has already told the listener about the event by the time this runs.
    """
    def intercept(event_type, event):
        if keycode_of(event) in keycodes and pid_of(event) == 0:
            return None
        return event
    return intercept


class Button:
    def __init__(self, keys: dict[str, str | None], source: str = "auto", filters: dict | None = None,
                 exclusive: bool = True):
        """keys maps button name ("talk", "no") to a key name ("space", "enter", "a"); None disables.

        filters: min_hold, bounce, refractory, long_hold in seconds (see presses.py).
        exclusive: swallow the button keys so no other application sees them.
        """
        self.exclusive = exclusive
        self.events: queue.Queue[tuple[str, str]] = queue.Queue()
        self.keys = {name: k for name, k in keys.items() if k}
        self.filters = dict(filters or {})
        self.source = source
        self._drain_only = False
        if source in ("auto", "global"):
            try:
                try:
                    self._start_global(self.exclusive)
                except Exception as exc:
                    if not self.exclusive:
                        raise
                    # Swallowing needs more permission than listening (Accessibility on macOS).
                    # Better a button that works and also reaches the application than no button.
                    print(f"[button] no puedo reservar las teclas del botón ({exc}); las verán también las aplicaciones.",
                          file=sys.stderr)
                    self.exclusive = False
                    self._start_global(False)
                self.source = "global"
                self._drain_only = True
            except Exception as exc:
                if source == "global":
                    raise
                print(f"[button] captura global no disponible ({exc}); usando la terminal.", file=sys.stderr)
                self.source = "terminal"
        if self.source == "terminal" or self._drain_only:
            self._start_terminal(drain_only=self._drain_only)

    @property
    def two_buttons(self) -> bool:
        return NO in self.keys

    # ---- API -----------------------------------------------------------
    def wait(self, timeout: float | None = None) -> tuple[str, str] | None:
        try:
            return self.events.get(timeout=timeout)
        except queue.Empty:
            return None

    def poll(self) -> tuple[str, str] | None:
        return self.wait(0)

    def clear(self) -> None:
        while self.poll() is not None:
            pass

    # ---- global (pynput) -----------------------------------------------
    def _start_global(self, swallow: bool = True) -> None:
        from pynput import keyboard

        def to_key(name: str):
            return getattr(keyboard.Key, name, None) or keyboard.KeyCode.from_char(name)

        key_to_button = {to_key(k): name for name, k in self.keys.items()}
        filters = {name: PressFilter(**self.filters) for name in self.keys}
        lock = threading.Lock()

        def down(name):
            with lock:
                filters[name].down(time.monotonic())

        def up(name):
            with lock:
                filters[name].up(time.monotonic())

        def on_press(k):
            name = key_to_button.get(k)
            if name is not None:
                down(name)

        def on_release(k):
            name = key_to_button.get(k)
            if name is not None:
                up(name)

        def watcher():  # the filter decides, every 20 ms, what the raw presses meant
            while True:
                time.sleep(0.02)
                with lock:
                    now = time.monotonic()
                    for name, f in filters.items():
                        for kind, _ in f.tick(now):
                            self.events.put((name, kind))

        def vk(name: str) -> int | None:
            """The platform's key code for a key name, when pynput knows it."""
            k = to_key(name)
            code = getattr(getattr(k, "value", k), "vk", None)
            if code is None and os.name == "nt" and len(name) == 1 and name.isalnum():
                code = ord(name.upper())   # on Windows a letter's or digit's virtual key is its character
            return code

        extra = {}
        codes = {vk(k): name for name, k in self.keys.items() if vk(k) is not None}
        if swallow and codes and os.name == "nt":
            extra["win32_event_filter"] = win32_filter(codes, down, up, lambda: listener.suppress_event())
        elif swallow and codes and sys.platform == "darwin":
            import Quartz
            extra["darwin_intercept"] = darwin_intercept(
                set(codes),
                lambda ev: Quartz.CGEventGetIntegerValueField(ev, Quartz.kCGKeyboardEventKeycode),
                lambda ev: Quartz.CGEventGetIntegerValueField(ev, Quartz.kCGEventSourceUnixProcessID))

        listener = keyboard.Listener(on_press=on_press, on_release=on_release, **extra)
        listener.daemon = True
        listener.start()
        time.sleep(0.2)
        if not listener.is_alive():
            raise RuntimeError("pynput listener did not start")
        threading.Thread(target=watcher, daemon=True).start()

    # ---- terminal ------------------------------------------------------
    def _char_map(self) -> dict[str, str]:
        m: dict[str, str] = {}
        for name, k in self.keys.items():
            for ch in _TERMINAL_CHARS.get(k, {k[:1]}):
                m[ch] = name
        return m

    def _start_terminal(self, drain_only: bool) -> None:
        if not sys.stdin.isatty():
            if not drain_only:
                raise RuntimeError("la terminal no es interactiva; no puedo leer el botón")
            return
        if os.name == "nt":
            self._start_terminal_windows(drain_only)
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
        chars = self._char_map()

        def read_chars() -> str:
            return os.read(fd, 64).decode(errors="ignore")

        def swallow(seconds: float) -> None:
            end = time.monotonic() + seconds
            while time.monotonic() < end:
                r, _, _ = select.select([fd], [], [], 0.05)
                if r:
                    os.read(fd, 256)

        def available() -> bool:
            return bool(select.select([fd], [], [], 0)[0])

        if not drain_only:
            threading.Thread(target=self._burst_reader, args=(chars, available, read_chars, swallow), daemon=True).start()
        else:
            threading.Thread(target=self._drain, args=(available, read_chars), daemon=True).start()

    def _start_terminal_windows(self, drain_only: bool) -> None:
        import msvcrt

        chars = self._char_map()

        def available() -> bool:
            return bool(msvcrt.kbhit())

        def read_chars() -> str:
            out = []
            while msvcrt.kbhit():
                out.append(msvcrt.getwch())
            return "".join(out)

        def swallow(seconds: float) -> None:
            end = time.monotonic() + seconds
            while time.monotonic() < end:
                read_chars()
                time.sleep(0.02)

        if not drain_only:
            threading.Thread(target=self._burst_reader, args=(chars, available, read_chars, swallow), daemon=True).start()
        else:
            threading.Thread(target=self._drain, args=(available, read_chars), daemon=True).start()

    @staticmethod
    def _drain(available, read_chars) -> None:
        while True:
            if available():
                read_chars()
            time.sleep(0.02)

    def _burst_reader(self, chars: dict[str, str], available, read_chars, swallow) -> None:
        """Per-button burst detection: one key within the window = short; a burst of repeats = long."""
        burst: dict[str, list] = {}  # name -> [start, count]
        refractory = float(self.filters.get("refractory", 0.35))
        last_emit = -1e9
        while True:
            now = time.monotonic()
            if available():
                for ch in read_chars():
                    name = chars.get(ch)
                    if name is None:
                        continue
                    if name not in burst and now - last_emit < refractory:
                        continue  # a tap right after an event is tremor, not intent
                    b = burst.setdefault(name, [now, 0])
                    b[1] += 1
                    if b[1] >= BURST_COUNT:
                        self.events.put((name, LONG))
                        last_emit = now
                        burst.clear()
                        swallow(0.8)   # the rest of this read and the release tail are discarded
                        break
            for name in list(burst):
                if now - burst[name][0] >= BURST_WINDOW:
                    self.events.put((name, SHORT))
                    last_emit = now
                    burst.pop(name, None)
            time.sleep(0.01)
