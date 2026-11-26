"""Voice-guided first run: learn the buttons, check the microphone, read the screens.

Runs when local/hardware.json is missing, or with `python -m onebutton --setup`,
or when the user says "configura los botones". Writes the result into
local/config.yaml (merging) and local/hardware.json. Everything is spoken, and
a helper can watch the terminal.

Buttons are learned by side, so whoever places them never has to say which is
which: "pulsa el de la izquierda", "ahora el de la derecha". The right one talks
unless the user presses the left one when offered the swap.
"""

from __future__ import annotations

import time

import yaml

from . import hardware
from .config import LOCAL_DIR
from .lang import L

KEY_NAMES = {" ": "space", "\r": "enter", "\n": "enter", "\t": "tab"}
TALK_SIDE_DEFAULT = "right"


def _wait_key(seconds: float):
    """Return the pynput key pressed within `seconds`, or None. Falls back to terminal input."""
    try:
        from pynput import keyboard
    except ImportError:
        keyboard = None
    if keyboard is not None:
        got = {}

        def on_press(k):
            got["key"] = k
            return False  # stop listener

        with keyboard.Listener(on_press=on_press) as listener:
            end = time.monotonic() + seconds
            while listener.is_alive() and time.monotonic() < end:
                time.sleep(0.05)
        k = got.get("key")
        if k is None:
            return None
        name = getattr(k, "name", None)
        if name:
            return name
        ch = getattr(k, "char", None)
        return KEY_NAMES.get(ch, ch)
    return None


def learn_buttons(say, wait_key=None, pause=time.sleep) -> dict:
    """Ask for the left button, then the right one, then which side talks.

    Returns {"talk": key, "no": key | None, "sides": {"left": key, "right": key}, "talk_side": side}
    with only the keys that were actually pressed. `wait_key(seconds)` and `pause` are
    injectable for tests.
    """
    wait_key = wait_key or _wait_key
    out: dict = {}
    say(L("Let us get to know your equipment. First the buttons.", "Vamos a conocer tu equipo. Primero los botones."))
    say(L("Press the button on the left. If you only have one button, press that one.",
          "Pulsa el botón de la izquierda. Si sólo tienes un botón, pulsa ese."))
    left = None
    for _ in range(3):
        left = wait_key(20)
        if left:
            break
        say(L("I did not detect anything. Press the button on the left, or the only one you have.",
              "No detecté nada. Pulsa el botón de la izquierda, o el único que tengas."))
    if not left:
        say(L("I did not detect any button. I will keep the previous settings.",
              "No detecté ningún botón. Seguiré con la configuración anterior."))
        return out
    say(L(f"Left button registered: {left}.", f"Botón izquierdo registrado: {left}."))
    pause(1.0)

    say(L("Now the one on the right. If you only have one, do nothing and wait.",
          "Ahora el de la derecha. Si sólo tienes uno, no hagas nada y espera."))
    right = wait_key(12)
    while right == left:
        say(L("That is the same button. If you have another on the right, press it; if not, wait.",
              "Ese es el mismo botón. Si tienes otro a la derecha, púlsalo; si no, espera."))
        right = wait_key(10)
    if not right:
        say(L("All right, a single button. Pressing is talking; holding it is cancelling.",
              "De acuerdo, un solo botón. Pulsar es hablar; mantenerlo pulsado es cancelar."))
        out.update({"talk": left, "no": None, "sides": {"left": left}, "talk_side": "left"})
        return out
    say(L(f"Right button registered: {right}.", f"Botón derecho registrado: {right}."))
    pause(1.0)

    talk_side = TALK_SIDE_DEFAULT
    say(L("The right one will be for talking and for saying yes. The left one, for saying no and opening the menu. "
          "If you would rather talk with the left one, press it now. If this is fine, do nothing and wait.",
          "El derecho será para hablar y para decir sí. El izquierdo, para decir no y abrir el menú. "
          "Si prefieres hablar con el izquierdo, púlsalo ahora. Si así está bien, no hagas nada y espera."))
    k = wait_key(8)
    while k and k not in (left, right):
        k = wait_key(4)
    if k == left:
        talk_side = "left"
        say(L("All right: you talk with the left one, and the right one is no.",
              "De acuerdo: hablas con el izquierdo, y el derecho es no."))
    else:
        say(L("All right: you talk with the right one, and the left one is no.",
              "De acuerdo: hablas con el derecho, y el izquierdo es no."))
    talk, no = (right, left) if talk_side == "right" else (left, right)
    out.update({"talk": talk, "no": no, "sides": {"left": left, "right": right}, "talk_side": talk_side})
    return out


def describe_screens(scr: list[dict], preset: str, page: dict | None) -> str:
    if not scr:
        return L("I see no screen; the page will open wherever the browser likes.",
                 "No veo ninguna pantalla; la página se abrirá donde el navegador quiera.")
    if preset == "glasses":
        return L("I see a very wide screen; I will use glasses mode.", "Veo una pantalla muy ancha; usaré el modo gafas.")
    if len(scr) == 1:
        return L("I see one screen; I will use monitor mode.", "Veo una pantalla; usaré el modo monitor.")
    second = page and not page.get("primary")
    return L(f"I see {len(scr)} screens. The page will go full screen on the {'second' if second else 'main'} one, "
             f"and the terminal stays on the other.",
             f"Veo {len(scr)} pantallas. La página irá a pantalla completa en {'la segunda' if second else 'la principal'}, "
             f"y la terminal se queda en la otra.")


def run(cfg: dict, speaker, transcriber_factory=None, recorder_factory=None, wait_key=None) -> dict:
    say = speaker.say
    result = {"buttons": {}}

    # ---- buttons ----
    learned = learn_buttons(say, wait_key)
    if learned.get("talk"):
        result["buttons"] = {"talk": learned["talk"], "no": learned.get("no")}
        result["button_sides"] = learned["sides"]
        result["talk_side"] = learned["talk_side"]

    # ---- microphone ----
    info = hardware.detect(cfg.get("screen_display", "auto"))
    mics = info["microphones"]
    if not mics:
        say(L("I cannot find any microphone. One has to be plugged in.", "No encuentro ningún micrófono. Hay que conectar uno."))
    elif transcriber_factory and recorder_factory:
        say(L("Now the microphone. When you hear the signal, say: hello, my name is, and your name.",
              "Ahora el micrófono. Cuando oigas la señal, di: hola, me llamo, y tu nombre."))
        ok = False
        for mic in sorted(mics, key=lambda m: not m["default"]):
            cfg_try = dict(cfg, input_device=mic["index"], silence_timeout=4, max_recording=6)
            try:
                rec = recorder_factory(cfg_try)
                rec.calibrate(0.5)
                say(L("Now.", "Ahora."))
                import threading
                audio = rec.record_until(threading.Event())
                text = transcriber_factory(cfg).transcribe(audio)
            except Exception as exc:
                print(f"[setup] micrófono {mic['name']}: {exc}")
                continue
            if text.strip():
                say(L(f"I heard you say: {text}.", f"Te oí decir: {text}."))
                result["input_device"] = mic["index"] if not mic["default"] else None
                ok = True
                break
            say(L(f"I heard nothing with the microphone {mic['name']}. I will try another.",
                  f"No oí nada con el micrófono {mic['name']}. Probaré otro."))
        if not ok:
            say(L("I could not hear you with any microphone. Check the connection and the input volume.",
                  "No conseguí oírte con ningún micrófono. Revisa la conexión y el volumen de entrada."))

    # ---- screens ----
    scr = info["screens"]
    preset = info["suggested_preset"]
    say(describe_screens(scr, preset, info.get("page_screen")))
    result["screens"] = scr
    result["microphones"] = mics
    result["suggested_preset"] = preset
    result["page_screen"] = info.get("page_screen")

    # ---- write ----
    LOCAL_DIR.mkdir(parents=True, exist_ok=True)
    cfg_path = LOCAL_DIR / "config.yaml"
    local = {}
    if cfg_path.exists():
        local = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    if result["buttons"].get("talk"):
        local["button_key"] = result["buttons"]["talk"]
        local["button2_key"] = result["buttons"].get("no")
    if "input_device" in result:
        local["input_device"] = result["input_device"]
    # screen_preset stays "auto": the loop looks at the screens every start, so
    # plugging glasses in later just works.
    cfg_path.write_text(yaml.safe_dump(local, allow_unicode=True, sort_keys=False), encoding="utf-8")
    hardware.save(result)
    say(hardware.spoken_summary(result) + L(" Done. I am restarting to use the new settings.",
                                             " Listo. Reinicio para usar la nueva configuración."))
    return result
