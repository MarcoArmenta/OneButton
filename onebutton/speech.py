"""Turn an assistant reply into something a speech engine can read aloud.

Markdown, code, URLs and LaTeX are fine on screen and awful in the ear. The
screen keeps the original; this is only what gets spoken.
"""

from __future__ import annotations

import re

_FENCE = re.compile(r"```.*?```", re.DOTALL)
_DISPLAY_MATH = re.compile(r"\$\$.*?\$\$|\\\[.*?\\\]", re.DOTALL)
_INLINE_MATH = re.compile(r"(?<!\$)\$(?!\$)([^$\n]{1,200}?)\$(?!\$)|\\\((.*?)\\\)")
_URL = re.compile(r"https?://\S+|www\.\S+")
_INLINE_CODE = re.compile(r"`([^`\n]*)`")
_HEADER = re.compile(r"^\s{0,3}#{1,6}\s*", re.MULTILINE)
_BULLET = re.compile(r"^\s*(?:[-*+•]|\d+[.)])\s+", re.MULTILINE)
_EMPH = re.compile(r"(\*\*|__|\*|_)(?=\S)(.+?)(?<=\S)\1")
_TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$", re.MULTILINE)
_TABLE_SEP = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$", re.MULTILINE)
_LINK = re.compile(r"\[([^\]]+)\]\([^)]+\)")
_EMOJI = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F000-\U0001F2FF⬀-⯿️]"
)
_MULTISPACE = re.compile(r"[ \t]+")
_MULTINEWLINE = re.compile(r"\n{3,}")

_SYMBOLS = {
    "≤": " menor o igual que ", "≥": " mayor o igual que ", "≠": " distinto de ",
    "→": " flecha ", "←": " flecha izquierda ", "⇒": " implica ", "⇔": " si y sólo si ",
    "∞": " infinito ", "∑": " suma ", "∏": " producto ", "∫": " integral ",
    "√": " raíz de ", "≈": " aproximadamente ", "±": " más menos ", "×": " por ",
    "·": " por ", "°": " grados ", "%": " por ciento ", "&": " y ", "~": "",
    "π": " pi ", "α": " alfa ", "β": " beta ", "γ": " gamma ", "δ": " delta ",
    "ε": " épsilon ", "λ": " lambda ", "μ": " mu ", "σ": " sigma ", "φ": " fi ", "ω": " omega ",
}


def clean_for_speech(text: str, lang: str = "es") -> str:
    code_note = " código en pantalla. " if lang.startswith("es") else " code on screen. "
    math_note = " fórmula en pantalla. " if lang.startswith("es") else " formula on screen. "
    link_note = " enlace en pantalla " if lang.startswith("es") else " link on screen "
    table_note = " tabla en pantalla. " if lang.startswith("es") else " table on screen. "

    t = text or ""
    t = _FENCE.sub(code_note, t)
    t = _DISPLAY_MATH.sub(math_note, t)
    t = _INLINE_MATH.sub(math_note, t)
    t = _LINK.sub(r"\1", t)
    t = _URL.sub(link_note, t)
    t = _INLINE_CODE.sub(r"\1", t)
    if _TABLE_ROW.search(t):
        t = _TABLE_SEP.sub("", t)
        rows = _TABLE_ROW.findall(t)
        t = _TABLE_ROW.sub("", t)
        t = t.rstrip() + "\n" + table_note if rows else t
    t = _HEADER.sub("", t)
    t = _BULLET.sub("", t)
    t = _EMPH.sub(r"\2", t)
    t = _EMOJI.sub("", t)
    for sym, word in _SYMBOLS.items():
        t = t.replace(sym, word)
    t = _MULTISPACE.sub(" ", t)
    t = re.sub(r"\s+([.,;:!?])", r"\1", t)
    t = re.sub(r"([.,;:!?])\s*\.", r"\1", t)
    t = _MULTINEWLINE.sub("\n\n", t)
    return t.strip()
