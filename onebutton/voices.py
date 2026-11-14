"""Choose a voice that speaks the configured language. Pure, tested.

Every speech engine has a default voice, and the default follows the system's own
language: on an English Windows or macOS, Spanish text handed to the default voice
is read with English pronunciation. So the voice is always chosen by language from
what the engine says is installed, and "nothing installed in that language" is an
answer of its own (None) that the caller handles by using another engine.
"""

from __future__ import annotations

import re

# Preferred countries per language, best first. Any voice of the language beats none.
CULTURES = {"es": ["es-MX", "es-US", "es-419"], "en": ["en-US", "en-GB"], "fr": ["fr-CA", "fr-FR"]}
# Piper voices (https://huggingface.co/rhasspy/piper-voices): offline, the same on every system.
PIPER = {"es": "es_MX-claude-high", "en": "en_US-lessac-medium", "fr": "fr_FR-siwis-medium"}

_BETTER = re.compile(r"natural|neural|premium|enhanced|mejorada", re.IGNORECASE)
# macOS lists dozens of voices per language, novelty ones included; these are the everyday ones.
_EVERYDAY = {"paulina", "mónica", "monica", "samantha", "alex", "daniel", "karen", "thomas", "amélie", "amelie"}
_SAY_LINE = re.compile(r"^(.+?)\s+([a-z]{2,3}[_-][A-Za-z0-9]{2,4})\s+#")


def _tag(lang: str) -> str:
    return (lang or "").replace("_", "-").lower()


def culture(lang: str) -> str:
    """'es' -> 'es-MX'; a full tag is kept."""
    tag = _tag(lang)
    if "-" in tag:
        family, region = tag.split("-", 1)
        return f"{family}-{region.upper()}"
    return (CULTURES.get(tag) or [tag])[0]


def pick(voices: list[dict], lang: str, wanted: str = "") -> dict | None:
    """The voice to use, or None when nothing installed speaks `lang`.

    voices: [{"engine", "name", "lang"}], engines in order of preference.
    wanted: `tts_voice` from the configuration, part of a voice's name. A name that is
    not installed falls back to the language instead of to the system default.
    """
    if wanted:
        for v in voices:
            if wanted.lower() in v["name"].lower():
                return v
    family = _tag(lang).split("-")[0]
    same = [v for v in voices if _tag(v["lang"]).split("-")[0] == family]
    if not same:
        return None
    order = [_tag(lang)] + [c.lower() for c in CULTURES.get(family, [])]

    def rank(v: dict) -> tuple[int, int]:
        tag = _tag(v["lang"])
        country = order.index(tag) if tag in order else len(order)
        name = v["name"]
        # macOS spells its synthetic voices "Eddy (Spanish (Mexico))"; the plain names are the good ones.
        quality = 0 if _BETTER.search(name) else 1 if name.lower() in _EVERYDAY else 3 if "(" in name else 2
        return country, quality

    return min(same, key=rank)   # min keeps the first of equals: the engine listed first


def parse_say(text: str) -> list[dict]:
    """Output of macOS `say -v ?`: 'Paulina             es_MX    # Hola...' per line."""
    out = []
    for line in text.splitlines():
        m = _SAY_LINE.match(line)
        if m:
            out.append({"engine": "say", "name": m.group(1).strip(), "lang": m.group(2).replace("_", "-")})
    return out


def parse_windows(text: str) -> list[dict]:
    """Output of the PowerShell listing in tts.py: 'engine|language|name' per line."""
    out = []
    for line in text.splitlines():
        parts = line.strip().split("|", 2)
        if len(parts) == 3 and parts[0] in ("winrt", "sapi") and parts[2]:
            out.append({"engine": parts[0], "name": parts[2].strip(), "lang": parts[1].strip()})
    return out


def piper_voice(lang: str) -> str | None:
    """The Piper voice downloaded for a language when the system has none of its own."""
    return PIPER.get(_tag(lang).split("-")[0])
