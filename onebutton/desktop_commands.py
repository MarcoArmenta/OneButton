"""Spanish utterances that mean a direct action on the computer. Pure, tested.

These are the fast path: no Claude turn, no screenshot. Anything that does not
parse here goes to Claude, which can still do it by looking at the screen.

    parse("ve a chrome")          -> {"action": "focus", "target": "chrome"}
    parse("pulsa el siete")       -> {"action": "click_number", "n": 7}
    parse("escribe hola juan")    -> {"action": "type", "text": "hola juan"}
    parse("apaga la computadora") -> {"action": "power", "what": "shutdown", "confirm": True}
"""

from __future__ import annotations

import re

from .commands import normalize

_NUM = {"uno": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6, "siete": 7, "ocho": 8, "nueve": 9,
        "diez": 10, "once": 11, "doce": 12, "trece": 13, "catorce": 14, "quince": 15, "dieciseis": 16,
        "diecisiete": 17, "dieciocho": 18, "diecinueve": 19, "veinte": 20, "treinta": 30, "cuarenta": 40,
        "cincuenta": 50, "sesenta": 60}


def number(words: list[str]) -> int | None:
    for i, w in enumerate(words):
        if w.isdigit():
            return int(w)
        if w in _NUM:
            n = _NUM[w]
            if n >= 20 and i + 2 < len(words) and words[i + 1] == "y" and words[i + 2] in _NUM and _NUM[words[i + 2]] < 10:
                n += _NUM[words[i + 2]]
            return n
    return None


KEYS = {
    "intro": "enter", "enter": "enter", "aceptar": "enter", "escape": "esc", "escapa": "esc", "cancelar tecla": "esc",
    "tabulador": "tab", "tab": "tab", "borrar": "backspace", "retroceso": "backspace", "suprimir": "delete",
    "espacio": "space", "inicio": "home", "fin": "end", "arriba": "up", "abajo": "down", "izquierda": "left",
    "derecha": "right", "pagina arriba": "pageup", "pagina abajo": "pagedown",
    "copiar": "ctrl+c", "pegar": "ctrl+v", "cortar": "ctrl+x", "deshacer tecla": "ctrl+z", "guardar": "ctrl+s",
    "seleccionar todo": "ctrl+a", "buscar": "ctrl+f", "nueva pestana": "ctrl+t", "cerrar pestana": "ctrl+w",
    "pestana siguiente": "ctrl+tab", "pestana anterior": "ctrl+shift+tab", "recargar": "f5",
    "pantalla completa": "f11", "escritorio": "win+d", "menu inicio": "win",
}

_PATTERNS: list[tuple[re.Pattern, callable]] = []


def _p(regex: str):
    def deco(fn):
        _PATTERNS.append((re.compile(r"^(?:" + regex + r")$"), fn))
        return fn
    return deco


@_p(r"(?:que )?ventanas(?: hay| tengo| abiertas)?|lista(?: de)? ventanas|cuales ventanas")
def _windows(m): return {"action": "windows"}

@_p(r"(?:muestra |ensena |pon |dame )?(?:los )?numeros|etiquetas|que puedo pulsar")
def _numbers(m): return {"action": "overlay"}

@_p(r"(?:ve|vete|ir|cambia|cambiar|pasa|pasar|salta|llevame|muestra|muestrame|ensename)(?: a| al| a la| la| el)? (?P<t>.+)")
def _focus(m): return {"action": "focus", "target": m.group("t")}

@_p(r"(?:abre|abrir|lanza|ejecuta|inicia)(?: el| la| un| una)? (?P<t>.+)")
def _open(m): return {"action": "open", "target": m.group("t")}

@_p(r"cierra(?: esta| la)? ventana|cerrar ventana|cierra esto|cierralo")
def _close(m): return {"action": "key", "keys": "alt+f4"}

@_p(r"minimiza(?: esta| la)?(?: ventana)?|minimizar")
def _min(m): return {"action": "minimize"}

@_p(r"maximiza(?: esta| la)?(?: ventana)?|maximizar|agranda(?: la)?(?: ventana)?")
def _max(m): return {"action": "maximize"}

@_p(r"(?:pulsa|pulsar|clic|click|toca|aprieta|elige|selecciona)(?: en)?(?: el| la| al)? (?:numero )?(?P<n>\w+(?: y \w+)?)")
def _click_number(m):
    n = number(m.group("n").split())
    return {"action": "click_number", "n": n} if n else None

@_p(r"(?:doble )?(?:clic|click) derecho|boton derecho|menu contextual")
def _right(m): return {"action": "right_click"}

@_p(r"doble (?:clic|click)")
def _double(m): return {"action": "double_click"}

@_p(r"rejilla|cuadricula|malla(?: de puntos)?")
def _grid(m): return {"action": "grid"}

@_p(r"(?:sube|subir|mas) (?:el )?volumen|mas alto|mas fuerte")
def _vol_up(m): return {"action": "volume", "what": "up"}

@_p(r"(?:baja|bajar|menos) (?:el )?volumen|mas bajo|mas flojo")
def _vol_down(m): return {"action": "volume", "what": "down"}

@_p(r"silencio|silenciar|mute|quita el sonido|pon el sonido|quita el silencio")
def _mute(m): return {"action": "volume", "what": "mute"}

@_p(r"(?:sube|subir|desplaza arriba|hacia arriba)(?: (?P<n>\w+))?(?: lineas| veces)?")
def _scroll_up(m): return {"action": "scroll", "dir": "up", "n": number((m.group("n") or "").split()) or 5}

@_p(r"(?:baja|bajar|desplaza abajo|hacia abajo|sigue bajando)(?: (?P<n>\w+))?(?: lineas| veces)?")
def _scroll_down(m): return {"action": "scroll", "dir": "down", "n": number((m.group("n") or "").split()) or 5}

@_p(r"(?:escribe|teclea|dicta|escribir) (?P<t>.+)")
def _type(m): return {"action": "type", "text": m.group("t")}

@_p(r"(?:pulsa |presiona |tecla |teclea )?(?P<k>" + "|".join(sorted(map(re.escape, KEYS), key=len, reverse=True)) + r")")
def _key(m): return {"action": "key", "keys": KEYS[m.group("k")]}

@_p(r"(?:control|ctrl) (?P<k>[a-z0-9]|f\d{1,2})")
def _ctrl(m): return {"action": "key", "keys": "ctrl+" + m.group("k")}

@_p(r"(?:alt) (?P<k>[a-z0-9]|f\d{1,2}|tab)")
def _alt(m): return {"action": "key", "keys": "alt+" + m.group("k")}

@_p(r"apaga(?:r)?(?: la)?(?: computadora| el ordenador| el equipo| la compu)?|apagar todo")
def _shutdown(m): return {"action": "power", "what": "shutdown", "confirm": True}

@_p(r"reinicia(?:r)?(?: la)?(?: computadora| el ordenador| el equipo)?")
def _restart(m): return {"action": "power", "what": "restart", "confirm": True}

@_p(r"suspende(?:r)?(?: la)?(?: computadora| el ordenador| el equipo)?|a dormir|hiberna(?:r)?")
def _sleep(m): return {"action": "power", "what": "sleep", "confirm": True}

@_p(r"bloquea(?: la)?(?: pantalla| computadora| sesion)?")
def _lock(m): return {"action": "key", "keys": "win+l"}

@_p(r"captura(?: de pantalla)?|pantallazo|haz una captura")
def _shot(m): return {"action": "screenshot"}

@_p(r"(?:que hay en|lee|describe|que dice)(?: la)? pantalla")
def _describe(m): return {"action": "describe"}

# words that mean the same thing as a verb above but must never be stolen from Claude
_RESERVED_TARGETS = {"pizarra", "escritorio", "conversacion", "escrito", "manuscrito"}


_ARTICLES = re.compile(r"^(?:a |al |a la |a el |la |el |los |las |un |una |mi |el programa |la aplicacion |la app )+")


def parse(text: str) -> dict | None:
    t = normalize(text)
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
