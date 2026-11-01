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
    say("Vamos a conocer tu equipo. Primero los botones.")
    say("Pulsa el botón de la izquierda. Si sólo tienes un botón, pulsa ese.")
    left = None
    for _ in range(3):
        left = wait_key(20)
        if left:
            break
        say("No detecté nada. Pulsa el botón de la izquierda, o el único que tengas.")
    if not left:
        say("No detecté ningún botón. Seguiré con la configuración anterior.")
        return out
    say(f"Botón izquierdo registrado: {left}.")
    pause(1.0)

    say("Ahora el de la derecha. Si sólo tienes uno, no hagas nada y espera.")
    right = wait_key(12)
    while right == left:
        say("Ese es el mismo botón. Si tienes otro a la derecha, púlsalo; si no, espera.")
        right = wait_key(10)
    if not right:
        say("De acuerdo, un solo botón. Pulsar es hablar; mantenerlo pulsado es cancelar.")
        out.update({"talk": left, "no": None, "sides": {"left": left}, "talk_side": "left"})
        return out
    say(f"Botón derecho registrado: {right}.")
    pause(1.0)

    talk_side = TALK_SIDE_DEFAULT
    say("El derecho será para hablar y para decir sí. El izquierdo, para decir no y abrir el menú. "
        "Si prefieres hablar con el izquierdo, púlsalo ahora. Si así está bien, no hagas nada y espera.")
    k = wait_key(8)
    while k and k not in (left, right):
        k = wait_key(4)
    if k == left:
        talk_side = "left"
        say("De acuerdo: hablas con el izquierdo, y el derecho es no.")
    else:
        say("De acuerdo: hablas con el derecho, y el izquierdo es no.")
    talk, no = (right, left) if talk_side == "right" else (left, right)
    out.update({"talk": talk, "no": no, "sides": {"left": left, "right": right}, "talk_side": talk_side})
    return out


def describe_screens(scr: list[dict], preset: str, page: dict | None) -> str:
    if not scr:
        return "No veo ninguna pantalla; la página se abrirá donde el navegador quiera."
    if preset == "glasses":
        return "Veo una pantalla muy ancha; usaré el modo gafas."
    if len(scr) == 1:
        return "Veo una pantalla; usaré el modo monitor."
    where = "la segunda" if page and not page.get("primary") else "la principal"
    return f"Veo {len(scr)} pantallas. La página irá a pantalla completa en {where}, y la terminal se queda en la otra."


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
        say("No encuentro ningún micrófono. Hay que conectar uno.")
    elif transcriber_factory and recorder_factory:
        say("Ahora el micrófono. Cuando oigas la señal, di: hola, me llamo, y tu nombre.")
        ok = False
        for mic in sorted(mics, key=lambda m: not m["default"]):
            cfg_try = dict(cfg, input_device=mic["index"], silence_timeout=4, max_recording=6)
            try:
                rec = recorder_factory(cfg_try)
                rec.calibrate(0.5)
                say("Ahora.")
                import threading
                audio = rec.record_until(threading.Event())
                text = transcriber_factory(cfg).transcribe(audio)
            except Exception as exc:
                print(f"[setup] micrófono {mic['name']}: {exc}")
                continue
            if text.strip():
                say(f"Te oí decir: {text}.")
                result["input_device"] = mic["index"] if not mic["default"] else None
                ok = True
                break
            say(f"No oí nada con el micrófono {mic['name']}. Probaré otro.")
        if not ok:
            say("No conseguí oírte con ningún micrófono. Revisa la conexión y el volumen de entrada.")

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
    say(hardware.spoken_summary(result) + " Listo. Reinicio para usar la nueva configuración.")
    return result
