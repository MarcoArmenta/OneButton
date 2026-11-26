"""Utterances, in Spanish or English, that mean a direct action on the computer. Pure, tested.

These are the fast path: no Claude turn, no screenshot. Anything that does not
parse here goes to Claude, which can still do it by looking at the screen.

    parse("ve a chrome")          -> {"action": "focus", "target": "chrome"}
    parse("click seven")          -> {"action": "click_number", "n": 7}
    parse("escribe hola juan")    -> {"action": "type", "text": "hola juan"}
    parse("baja un poco")         -> {"action": "scroll", "dir": "down", "n": 2}
    parse("otra vez")             -> {"action": "scroll_again"}
    parse("apaga la computadora") -> {"action": "power", "what": "shutdown", "confirm": True}

Scrolling is by voice only: the buttons belong to OneButton and never reach
the application. "Baja" moves half a screen, "baja un poco" a little, "baja
mucho" a whole screen, and "otra vez" repeats the last move.
"""

from __future__ import annotations

import re

from .commands import normalize

_NUM = {"uno": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6, "siete": 7, "ocho": 8, "nueve": 9,
        "diez": 10, "once": 11, "doce": 12, "trece": 13, "catorce": 14, "quince": 15, "dieciseis": 16,
        "diecisiete": 17, "dieciocho": 18, "diecinueve": 19, "veinte": 20, "treinta": 30, "cuarenta": 40,
        "cincuenta": 50, "sesenta": 60,
        "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
        "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16,
        "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
        "sixty": 60}


def number(words: list[str]) -> int | None:
    """The first number in the words: digits, "treinta y dos", "thirty two"."""
    for i, w in enumerate(words):
        if w.isdigit():
            return int(w)
        if w in _NUM:
            n = _NUM[w]
            if n >= 20:
                rest = words[i + 1:]
                if rest[:1] == ["y"]:
                    rest = rest[1:]
                if rest and rest[0] in _NUM and _NUM[rest[0]] < 10:
                    n += _NUM[rest[0]]
            return n
    return None


KEYS = {
    "intro": "enter", "enter": "enter", "aceptar": "enter", "escape": "esc", "escapa": "esc", "cancelar tecla": "esc",
    "tabulador": "tab", "tab": "tab", "borrar": "backspace", "retroceso": "backspace", "suprimir": "delete",
    "espacio": "space", "inicio": "home", "fin": "end", "arriba": "up", "abajo": "down", "izquierda": "left",
    "derecha": "right", "pagina arriba": "pageup", "pagina abajo": "pagedown",
    "pagina siguiente": "pagedown", "siguiente pagina": "pagedown", "pagina anterior": "pageup",
    "copiar": "ctrl+c", "pegar": "ctrl+v", "cortar": "ctrl+x", "deshacer tecla": "ctrl+z", "guardar": "ctrl+s",
    "seleccionar todo": "ctrl+a", "buscar": "ctrl+f", "nueva pestana": "ctrl+t", "cerrar pestana": "ctrl+w",
    "pestana siguiente": "ctrl+tab", "pestana anterior": "ctrl+shift+tab", "recargar": "f5",
    "pantalla completa": "f11", "escritorio": "win+d", "menu inicio": "win",
    # English
    "return": "enter", "backspace": "backspace", "delete": "delete", "space": "space", "home": "home", "end": "end",
    "up": "up", "down": "down", "left": "left", "right": "right", "page up": "pageup", "page down": "pagedown",
    "next page": "pagedown", "previous page": "pageup",
    "copy": "ctrl+c", "paste": "ctrl+v", "cut": "ctrl+x", "undo key": "ctrl+z", "save": "ctrl+s",
    "select all": "ctrl+a", "find": "ctrl+f", "new tab": "ctrl+t", "close tab": "ctrl+w",
    "next tab": "ctrl+tab", "previous tab": "ctrl+shift+tab", "reload": "f5", "refresh": "f5",
    "full screen": "f11", "fullscreen": "f11", "show desktop": "win+d", "start menu": "win",
}

# How far a scroll goes, in the units of desktop.py scroll (about a tenth of a screen each).
SCROLL_LITTLE, SCROLL_DEFAULT, SCROLL_LOT = 2, 5, 10
_LITTLE = {"un poco", "poco", "un poquito", "poquito", "tantito", "un tantito", "un poco mas", "un poquito mas",
           "solo un poco", "a little", "a bit", "a little bit", "a tad", "slightly", "just a little", "just a bit",
           "a little more", "a bit more", "a little bit more"}
_SAME = {"mas", "otra vez", "de nuevo", "more", "some more", "again"}
_LOT = {"mucho", "mucho mas", "bastante", "una pagina", "toda la pagina", "una pantalla",
        "a lot", "a lot more", "much more", "way more", "a page", "a whole page", "one page", "a screen"}


def _amount(said: str | None) -> int | None:
    """Units for what followed "baja" / "scroll down"; None when it was not an amount at all."""
    s = (said or "").strip()
    if not s:
        return SCROLL_DEFAULT
    if s in _LITTLE:
        return SCROLL_LITTLE
    if s in _SAME:
        return SCROLL_DEFAULT
    if s in _LOT:
        return SCROLL_LOT
    m = re.match(r"^(\w+(?: y \w+| \w+)?)(?: lineas| linea| veces| vez| lines| line| times)?$", s)
    return number(m.group(1).split()) if m else None


_PATTERNS: list[tuple[re.Pattern, callable]] = []


def _p(regex: str):
    def deco(fn):
        _PATTERNS.append((re.compile(r"^(?:" + regex + r")$"), fn))
        return fn
    return deco


@_p(r"(?:que )?ventanas(?: hay| tengo| abiertas)?|lista(?: de)? ventanas|cuales ventanas"
    r"|(?:what |which )?windows(?: are)?(?: open| there)?|list(?: of)?(?: the)? windows")
def _windows(m): return {"action": "windows"}

@_p(r"(?:muestra |ensena |pon |dame )?(?:los )?numeros|etiquetas|que puedo pulsar"
    r"|(?:show |give me )?(?:the )?numbers|labels|what can i (?:click|press)")
def _numbers(m): return {"action": "overlay"}

# volume before scrolling: "sube el volumen" is not "sube"
@_p(r"(?:sube|subir|mas) (?:el )?volumen|mas alto|mas fuerte"
    r"|volume up|turn (?:it |the volume )?up|louder|(?:raise|increase) the volume")
def _vol_up(m): return {"action": "volume", "what": "up"}

@_p(r"(?:baja|bajar|menos) (?:el )?volumen|mas bajo|mas flojo"
    r"|volume down|turn (?:it |the volume )?down|quieter|softer|(?:lower|decrease) the volume")
def _vol_down(m): return {"action": "volume", "what": "down"}

@_p(r"silencio|silenciar|mute|quita el sonido|pon el sonido|quita el silencio|unmute")
def _mute(m): return {"action": "volume", "what": "mute"}

# scrolling before window switching: "ve hacia arriba" is not a window called "hacia arriba"
_GO = r"(?:ve |vete |ir |vamos |vuelve |regresa |go |scroll |move |jump |back )?"

@_p(_GO + r"(?:al|a la|hasta el|to the|to) (?:principio|inicio|comienzo|tope|top|beginning|start)"
    r"(?: del documento| de la pagina| del pdf| del todo| of the (?:page|document|pdf))?|hasta arriba(?: del todo)?")
def _scroll_top(m): return {"action": "key", "keys": "ctrl+home"}

@_p(_GO + r"(?:al|a la|hasta el|to the|to) (?:final|fin|fondo|bottom|end)"
    r"(?: del documento| de la pagina| del pdf| del todo| of the (?:page|document|pdf))?|hasta abajo(?: del todo)?")
def _scroll_bottom(m): return {"action": "key", "keys": "ctrl+end"}

@_p(r"(?:sube|subir|subele|sigue subiendo|desplaza(?: hacia)? arriba|" + _GO + r"(?:hacia|para|mas) arriba"
    r"|scroll(?: back)? up|go(?: back)? up|move up|back up|further up|higher)(?: (?P<amt>.+))?")
def _scroll_up(m):
    n = _amount(m.group("amt"))
    return {"action": "scroll", "dir": "up", "n": n} if n else None

@_p(r"(?:baja|bajar|bajale|sigue bajando|desplaza(?: hacia)? abajo|" + _GO + r"(?:hacia|para|mas) abajo"
    r"|scroll down|go down|move down|further down|lower|keep going down)(?: (?P<amt>.+))?")
def _scroll_down(m):
    n = _amount(m.group("amt"))
    return {"action": "scroll", "dir": "down", "n": n} if n else None

@_p(r"otra vez|de nuevo|otra|mas|un poco mas|otro poco|again|once more|one more time|more|a bit more|a little more")
def _scroll_again(m): return {"action": "scroll_again"}   # the loop repeats the last scroll, if there was one just now

@_p(r"(?:ve|vete|ir|cambia|cambiar|pasa|pasar|salta|llevame|muestra|muestrame|ensename)(?: a| al| a la| la| el)? (?P<t>.+)"
    r"|(?:go to|switch to|change to|take me to|show me|bring up)(?: the)? (?P<t2>.+)")
def _focus(m): return {"action": "focus", "target": m.group("t") or m.group("t2")}

@_p(r"(?:abre|abrir|lanza|ejecuta|inicia)(?: el| la| un| una)? (?P<t>.+)|(?:open|launch)(?: the| a| an)? (?P<t2>.+)")
def _open(m): return {"action": "open", "target": m.group("t") or m.group("t2")}

@_p(r"cierra(?: esta| la)? ventana|cerrar ventana|cierra esto|cierralo|close(?: this| the)? window|close this|close it")
def _close(m): return {"action": "key", "keys": "alt+f4"}

@_p(r"minimiza(?: esta| la)?(?: ventana)?|minimizar|minimi[sz]e(?: this| the)?(?: window)?")
def _min(m): return {"action": "minimize"}

@_p(r"maximiza(?: esta| la)?(?: ventana)?|maximizar|agranda(?: la)?(?: ventana)?|maximi[sz]e(?: this| the)?(?: window)?")
def _max(m): return {"action": "maximize"}

@_p(r"(?:pulsa|pulsar|clic|click|toca|aprieta|elige|selecciona)(?: en)?(?: el| la| al)? (?:numero )?(?P<n>\w+(?: y \w+)?)"
    r"|(?:click|press|tap|choose|select|pick)(?: on)?(?: the)? (?:number )?(?P<n2>\w+(?: \w+)?)")
def _click_number(m):
    n = number((m.group("n") or m.group("n2")).split())
    return {"action": "click_number", "n": n} if n else None

@_p(r"(?:doble )?(?:clic|click) derecho|boton derecho|menu contextual|right click|context menu")
def _right(m): return {"action": "right_click"}

@_p(r"doble (?:clic|click)|double click")
def _double(m): return {"action": "double_click"}

@_p(r"rejilla|cuadricula|malla(?: de puntos)?|grid")
def _grid(m): return {"action": "grid"}

@_p(r"(?:escribe|teclea|dicta|escribir|type) (?P<t>.+)")
def _type(m): return {"action": "type", "text": m.group("t")}

@_p(r"(?:(?:pulsa|presiona|tecla|teclea|press|hit|key) (?:la tecla |the )?)?(?P<k>"
    + "|".join(sorted(map(re.escape, KEYS), key=len, reverse=True)) + r")(?: key)?")
def _key(m): return {"action": "key", "keys": KEYS[m.group("k")]}

@_p(r"(?:control|ctrl) (?P<k>[a-z0-9]|f\d{1,2})")
def _ctrl(m): return {"action": "key", "keys": "ctrl+" + m.group("k")}

@_p(r"(?:alt) (?P<k>[a-z0-9]|f\d{1,2}|tab)")
def _alt(m): return {"action": "key", "keys": "alt+" + m.group("k")}

@_p(r"apaga(?:r)?(?: la)?(?: computadora| el ordenador| el equipo| la compu)?|apagar todo"
    r"|shut ?down(?: the)?(?: computer| pc| machine)?|turn off the computer|power off")
def _shutdown(m): return {"action": "power", "what": "shutdown", "confirm": True}

@_p(r"reinicia(?:r)?(?: la)?(?: computadora| el ordenador| el equipo)?|(?:restart|reboot)(?: the)?(?: computer| pc| machine)?")
def _restart(m): return {"action": "power", "what": "restart", "confirm": True}

@_p(r"suspende(?:r)?(?: la)?(?: computadora| el ordenador| el equipo)?|a dormir|hiberna(?:r)?"
    r"|sleep|suspend(?: the computer)?|hibernate|put the computer to sleep")
def _sleep(m): return {"action": "power", "what": "sleep", "confirm": True}

@_p(r"bloquea(?: la)?(?: pantalla| computadora| sesion)?|lock(?: the)?(?: screen| computer)?")
def _lock(m): return {"action": "key", "keys": "win+l"}

@_p(r"captura(?: de pantalla)?|pantallazo|haz una captura|(?:take a )?screenshot|screen capture")
def _shot(m): return {"action": "screenshot"}

@_p(r"(?:que hay en|lee|describe|que dice)(?: la)? pantalla"
    r"|what(?: s| is) on (?:the |my )?screen|(?:read|describe) the screen")
def _describe(m): return {"action": "describe"}

# words that mean the same thing as a verb above but must never be stolen from Claude or the page
_RESERVED_TARGETS = {"pizarron", "pizarra", "escritorio", "conversacion", "escrito", "manuscrito",
                     "board", "blackboard", "desk", "writing desk", "conversation", "chat", "manuscript",
                     "paper", "draft"}


_ARTICLES = re.compile(r"^(?:a |al |a la |a el |la |el |los |las |un |una |mi |el programa |la aplicacion |la app "
                       r"|the |my |an |the app |the program )+")
_POLITE = re.compile(r"^(?:por favor|please) | (?:por favor|please)$")


def parse(text: str) -> dict | None:
    t = _POLITE.sub("", normalize(text))
    if not t or len(t.split()) > 12:
        return None
    for rx, fn in _PATTERNS:
        m = rx.match(t)
        if not m:
            continue
        act = fn(m)
        if act is None:
            continue  # the verb matched but the argument did not; try the next pattern
        if "target" in act:
            act["target"] = _ARTICLES.sub("", act["target"]).strip()
            if act["target"] in _RESERVED_TARGETS or not act["target"]:
                return None
        return act
    return None
