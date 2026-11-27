"""Several Claude Code conversations at once, in the same workspace.

Each conversation is a Claude Code session of its own (`--session-id` on the first
turn, `--resume` afterwards), numbered one, two, three... as the user opens them.
A turn runs in the background, so while one conversation is working the user can
open another and talk. Pure logic here: parsing the voice commands, the registry,
the spoken summaries. The loop does the speaking and the threads.
"""

from __future__ import annotations

import re
import threading
import uuid
from collections import deque
from dataclasses import dataclass, field

from .commands import normalize
from .lang import L, language

NEW, SWITCH, CLOSE, LIST = "new", "switch", "close", "list"
IDLE, WORKING, DONE = "idle", "working", "done"  # done = has replies nobody has heard yet

NUMBERS = {"uno": 1, "una": 1, "primera": 1, "dos": 2, "segunda": 2, "tres": 3, "tercera": 3, "cuatro": 4,
           "cuarta": 4, "cinco": 5, "quinta": 5, "seis": 6, "sexta": 6, "siete": 7, "septima": 7, "ocho": 8,
           "octava": 8, "nueve": 9, "novena": 9, "diez": 10, "decima": 10,
           "one": 1, "first": 1, "two": 2, "second": 2, "three": 3, "third": 3, "four": 4, "fourth": 4,
           "five": 5, "fifth": 5, "six": 6, "sixth": 6, "seven": 7, "seventh": 7, "eight": 8, "eighth": 8,
           "nine": 9, "ninth": 9, "ten": 10, "tenth": 10}
SPOKEN = {"es": {1: "uno", 2: "dos", 3: "tres", 4: "cuatro", 5: "cinco", 6: "seis", 7: "siete", 8: "ocho",
                 9: "nueve", 10: "diez"},
          "en": {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight",
                 9: "nine", 10: "ten"}}

_NUM = r"(?P<n>\d{1,2}|" + "|".join(NUMBERS) + r")"
_CONV = r"(?:conversacion|charla|sesion)"
_CONV_EN = r"(?:conversation|chat|session)"
_PATTERNS = [
    (NEW, re.compile(rf"^(?:abre |empieza |inicia |crea |quiero )?(?:una |otra )?(?:nueva {_CONV}|{_CONV} nueva|otra {_CONV})(?: nueva)?$")),
    (CLOSE, re.compile(rf"^(?:cierra|termina|borra|quita|elimina)(?: esta| la| esa)? {_CONV}(?: {_NUM})?$")),
    (LIST, re.compile(rf"^(?:que|cuales|cuantas) {_CONV}(?:es)? (?:hay|tengo|estan abiertas)$|^(?:lista|listado) de {_CONV}(?:es)?$|^(?:en que|cual) {_CONV} estoy$")),
    (SWITCH, re.compile(rf"^(?:ve a |vamos a |cambia a |cambiar a |pasa a |vuelve a |volver a |regresa a |abre |muestra )?(?:la )?{_CONV} (?:numero )?{_NUM}$")),
    (SWITCH, re.compile(rf"^(?:ve a |vamos a |cambia a |pasa a |vuelve a |regresa a )(?:la )?{_NUM}$")),
    # English
    (NEW, re.compile(rf"^(?:open |start |begin |create |i want )?(?:a |another )?(?:new {_CONV_EN}|another {_CONV_EN})$")),
    (CLOSE, re.compile(rf"^(?:close|end|finish|delete|remove)(?: this| the| that)? {_CONV_EN}(?: (?:number )?{_NUM})?$")),
    (LIST, re.compile(rf"^(?:what|which|how many) {_CONV_EN}s (?:are there|are open|do i have)$|^list(?: of)?(?: the)? {_CONV_EN}s$"
                      rf"|^(?:which|what) {_CONV_EN} am i in$")),
    (SWITCH, re.compile(rf"^(?:go to |switch to |change to |back to |go back to |return to |open |show )?(?:the )?{_CONV_EN} (?:number )?{_NUM}$")),
    (SWITCH, re.compile(rf"^(?:go to |switch to |back to |go back to |return to )(?:the )?(?:number )?{_NUM}(?: one)?$")),
]


def parse(text: str) -> dict | None:
    """'nueva conversación' -> {kind: new}; 'conversación dos' -> {kind: switch, n: 2}; None otherwise."""
    t = normalize(text)
    if not t or len(t.split()) > 6:
        return None
    for kind, rx in _PATTERNS:
        m = rx.match(t)
        if not m:
            continue
        out = {"kind": kind}
        n = m.groupdict().get("n")
        if n:
            out["n"] = int(n) if n.isdigit() else NUMBERS[n]
        return out
    return None


def spoken(n: int) -> str:
    return SPOKEN[language()].get(n, str(n))


@dataclass
class Conversation:
    n: int
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""                # the first thing the user said, for the summary
    state: str = IDLE
    last_reply: str = ""
    dictating: bool = False        # the writing desk is taking his words down (see commands.dictation)
    announced: bool = True         # a background finish is announced once
    replies: deque = field(default_factory=deque)   # finished turns nobody has heard yet
    lock: threading.Lock = field(default_factory=threading.Lock)

    @property
    def file(self) -> str:
        return f"conversaciones/{self.n}.md"

    def add_reply(self, text: str) -> None:
        """Called from the agent's reader thread when a turn finishes."""
        with self.lock:
            self.replies.append(text)
            self.last_reply = text
            self.state = DONE
            self.announced = False

    def take_replies(self) -> list[str]:
        with self.lock:
            out = list(self.replies)
            self.replies.clear()
            self.state = IDLE
            self.announced = True
            return out


class Registry:
    def __init__(self):
        self.items: list[Conversation] = [Conversation(1)]
        self.current: Conversation = self.items[0]
        self._next = 2

    def get(self, n: int) -> Conversation | None:
        return next((c for c in self.items if c.n == n), None)

    def new(self) -> Conversation:
        c = Conversation(self._next)
        self._next += 1
        self.items.append(c)
        self.current = c
        return c

    def switch(self, n: int) -> Conversation | None:
        c = self.get(n)
        if c:
            self.current = c
        return c

    def close(self, n: int | None = None) -> Conversation | None:
        """Remove a conversation; the current one by default. Returns the removed one or None.

        The registry never goes empty: closing the last one opens a fresh number.
        """
        c = self.current if n is None else self.get(n)
        if not c:
            return None
        self.items.remove(c)
        if not self.items:
            self.new()
        elif c is self.current:
            self.current = self.items[-1]
        return c

    def working(self) -> list[Conversation]:
        return [c for c in self.items if c.state == WORKING]

    def unannounced(self) -> list[Conversation]:
        return [c for c in self.items if c.replies and not c.announced]

    def summary(self) -> str:
        def what(c: Conversation) -> str:
            return {WORKING: L("is working", "está trabajando"),
                    DONE: L("has finished and you have not heard it", "terminó y no la has oído")}.get(
                        c.state, L("is free", "está libre"))

        if len(self.items) == 1:
            c = self.items[0]
            return L(f"There is one conversation, number {spoken(c.n)}, and it {what(c)}.",
                     f"Hay una sola conversación, la {spoken(c.n)}, y {what(c)}.")
        parts = [L(f"There are {spoken(len(self.items))} conversations.", f"Hay {spoken(len(self.items))} conversaciones.")]
        for c in self.items:
            about = L(f", about {c.title}", f", sobre {c.title}") if c.title else ""
            parts.append(L(f"Number {spoken(c.n)}{about}, {what(c)}.", f"La {spoken(c.n)}{about}, {what(c)}."))
        parts.append(L(f"You are in number {spoken(self.current.n)}.", f"Estás en la {spoken(self.current.n)}."))
        return " ".join(parts)


def short_title(text: str, words: int = 6) -> str:
    ws = text.strip().split()
    return " ".join(ws[:words]) + ("..." if len(ws) > words else "")
