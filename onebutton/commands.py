"""Classify a transcript as a local voice command or as text for the agent.

Pure functions, no I/O, so they are easy to test. Matching is deliberately
forgiving: lower-case, accents stripped, trailing punctuation ignored, and a
command word is accepted on its own or as the whole short utterance.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

UPDATE, UPDATE_CLAUDE, LOGIN, UNDO, REPEAT, SETUP, CONFIRM, CANCEL, TEXT, EMPTY = (
    "update", "update_claude", "login", "undo", "repeat", "setup", "confirm", "cancel", "text", "empty",
)
LOGIN_WORDS = ["inicia sesion", "iniciar sesion", "inicia la sesion", "entra en claude", "conectate a claude",
               "login", "vuelve a entrar", "inicia sesion en claude"]
SETUP_WORDS = ["configura los botones", "configurar botones", "configura el equipo", "configuracion"]
UPDATE_CLAUDE_WORDS = ["actualiza claude", "actualizar claude", "actualiza claude code", "actualiza a claude",
                       "actualiza el claude", "mejora claude"]


@dataclass(frozen=True)
class Command:
    kind: str
    text: str = ""


def normalize(s: str) -> str:
    s = unicodedata.normalize("NFD", s.lower())
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    s = re.sub(r"[^\w\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _matches(utterance: str, words: list[str]) -> bool:
    u = normalize(utterance)
    if not u:
        return False
    for w in words:
        nw = normalize(w)
        if u == nw:
            return True
        # Allow a short wrapper such as "por favor actualiza" or "actualiza ya".
        if len(u.split()) <= 4 and re.search(rf"\b{re.escape(nw)}\b", u):
            return True
    return False


def classify(transcript: str, cfg: dict, awaiting_confirmation: bool = False) -> Command:
    """Map a transcript to a Command.

    When awaiting_confirmation is True, confirm and cancel words are checked
    first and anything else is treated as a cancel: silence or an unrelated
    sentence must never count as "yes".
    """
    t = transcript.strip()
    if not normalize(t):
        return Command(EMPTY)
    if awaiting_confirmation:
        if _matches(t, cfg["confirm_words"]):
            return Command(CONFIRM)
        return Command(CANCEL, t)
    if _matches(t, cfg.get("update_claude_words") or UPDATE_CLAUDE_WORDS):
        return Command(UPDATE_CLAUDE)   # before UPDATE: "actualiza claude" contains "actualiza"
    if _matches(t, cfg["update_words"]):
        return Command(UPDATE)
    if _matches(t, cfg.get("login_words") or LOGIN_WORDS):
        return Command(LOGIN)
    if _matches(t, cfg["undo_words"]):
        return Command(UNDO)
    if _matches(t, cfg["repeat_words"]):
        return Command(REPEAT)
    if _matches(t, cfg.get("setup_words") or SETUP_WORDS):
        return Command(SETUP)
    return Command(TEXT, t)
