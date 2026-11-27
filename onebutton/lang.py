"""The language the computer speaks in.

OneButton understands English and Spanish at the same time (see stt.py and the
command parsers), but it speaks one of them. Every phrase the loop says is
written in place in both, `L("Cancelled.", "Cancelado.")`, and this module
picks. The choice is `speak_language` in the config, changed by voice with
"speak Spanish" or "habla en inglés".
"""

from __future__ import annotations

SUPPORTED = ("en", "es")
NAMES = {"en": {"en": "English", "es": "Spanish"}, "es": {"en": "inglés", "es": "español"}}

_current = "en"


def set_language(code: str | None) -> str:
    """Set the spoken language; anything unknown means English. Returns the code in use."""
    global _current
    code = (code or "en").lower()[:2]
    _current = code if code in SUPPORTED else "en"
    return _current


def language() -> str:
    return _current


def L(en: str, es: str) -> str:
    """The phrase in the language being spoken."""
    return es if _current == "es" else en


def helper(cfg: dict) -> str:
    """Who to call when a human is needed: the configured name, or a plain description."""
    return cfg.get("helper_name") or L("the person who helps you", "la persona que te ayuda")


def name(code: str) -> str:
    """A language's name, said in the language being spoken."""
    return NAMES[_current].get(code, code)
