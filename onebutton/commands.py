"""Classify a transcript as a local voice command or as text for the agent.

Pure functions, no I/O, so they are easy to test. Matching is deliberately
forgiving: lower-case, accents stripped, trailing punctuation ignored, and a
command word is accepted on its own or as the whole short utterance.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

UPDATE, UPDATE_CLAUDE, LOGIN, UNDO, REPEAT, SETUP, LANGUAGE, CONFIRM, CANCEL, TEXT, EMPTY = (
    "update", "update_claude", "login", "undo", "repeat", "setup", "language", "confirm", "cancel", "text", "empty",
)
# Every command is understood in Spanish and in English, whichever one the computer speaks.
LOGIN_WORDS = ["inicia sesion", "iniciar sesion", "inicia la sesion", "entra en claude", "conectate a claude",
               "login", "vuelve a entrar", "inicia sesion en claude",
               "sign in", "log in", "sign in to claude", "log in to claude", "sign in again", "log in again"]
SETUP_WORDS = ["configura los botones", "configurar botones", "configura el equipo", "configuracion",
               "set up the buttons", "setup the buttons", "configure the buttons", "button setup"]
UPDATE_CLAUDE_WORDS = ["actualiza claude", "actualizar claude", "actualiza claude code", "actualiza a claude",
                       "actualiza el claude", "mejora claude",
                       "update claude", "update claude code", "upgrade claude", "upgrade claude code"]
# "speak Spanish", "habla en inglés": the language the computer speaks from now on.
LANGUAGE_WORDS = {
    "en": ["speak english", "speak in english", "talk in english", "switch to english", "english please",
           "habla ingles", "habla en ingles", "hablame en ingles", "cambia a ingles", "en ingles por favor"],
    "es": ["speak spanish", "speak in spanish", "talk in spanish", "switch to spanish", "spanish please",
           "habla espanol", "habla en espanol", "hablame en espanol", "cambia a espanol", "en espanol por favor"],
}

# The writing desk: from "nuevo escrito" until "fin del dictado" every utterance goes to the
# assistant untouched, so a dictated sentence that starts with "baja" or "open" is written
# down and not carried out on the computer.
DICTATION_START = re.compile(
    r"^(?:(?:empecemos|empieza|empezar|comienza|quiero|vamos a|inicia|crea|haz|abre|abrir|sigue con|continua|retoma)"
    r" (?:con )?(?:un |el |mi |otro |a )?(?:nuevo )?(?:escrito|articulo|ensayo|libro|capitulo|manuscrito|dictado|dictar)"
    r"|nuevo (?:escrito|articulo|ensayo|libro|capitulo|manuscrito)|dictado|modo dictado|voy a dictar|empiezo a dictar"
    r"|(?:start|begin|open|new|continue|resume|let s start|let s write|i want to write)"
    r" (?:a |an |the |my |another )?(?:new )?(?:piece|paper|article|essay|book|chapter|manuscript|draft|dictation|writing)"
    r"|dictation|dictation mode|start dictating|take dictation|i m going to dictate)\b")
DICTATION_STOP = re.compile(
    r"^(?:fin del dictado|termina el dictado|terminar dictado|fin de dictado|deja de dictar|cierra el escrito"
    r"|salir del dictado|sal del dictado|ya termine de dictar"
    r"|end (?:of )?dictation|stop dictation|stop dictating|end dictation|finish dictation|close the (?:paper|piece|draft|manuscript)"
    r"|exit dictation|done dictating|i m done dictating)$")


def dictation(transcript: str) -> str | None:
    """"start" when the utterance opens a piece of writing, "stop" when it ends dictation, else None."""
    t = normalize(transcript)
    if DICTATION_STOP.match(t):
        return "stop"
    if len(t.split()) <= 12 and DICTATION_START.match(t):
        return "start"
    return None


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
    for code, words in LANGUAGE_WORDS.items():
        if _matches(t, words):
            return Command(LANGUAGE, code)
    return Command(TEXT, t)
