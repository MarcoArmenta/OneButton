"""Voice-guided first run: learn the buttons, check the microphone, read the screens.

Runs when local/hardware.json is missing, or with `python -m onebutton --setup`,
or when the user says "configura los botones". Writes the result into
local/config.yaml (merging) and local/hardware.json. Everything is spoken, and
a helper can watch the terminal.
"""

from __future__ import annotations

import time

import yaml

from . import hardware
from .config import LOCAL_DIR

KEY_NAMES = {" ": "space", "\r": "enter", "\n": "enter", "\t": "tab"}


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


def run(cfg: dict, speaker, transcriber_factory=None, recorder_factory=None) -> dict:
    say = speaker.say
    result = {"buttons": {}}
    say("Vamos a conocer tu equipo. Primero los botones.")

    # ---- button 1 ----
    say("Pulsa el botón que vas a usar para hablar. Es el de la mano con más control.")
    k1 = None
    for _ in range(3):
        k1 = _wait_key(20)
        if k1:
            break
        say("No detecté nada. Pulsa el botón para hablar.")
    if not k1:
        say("No detecté ningún botón. Seguiré con la configuración anterior.")
    else:
        result["buttons"]["talk"] = k1
        say(f"Botón uno registrado: {k1}.")
        time.sleep(1.0)
        # ---- button 2 ----
        say("Si tienes un segundo botón, púlsalo ahora. Si sólo tienes uno, no hagas nada y espera.")
        k2 = _wait_key(12)
        while k2 == k1:
            say("Ese es el mismo botón. Si tienes otro, púlsalo; si no, espera.")
            k2 = _wait_key(10)
        if k2:
            result["buttons"]["no"] = k2
            say(f"Botón dos registrado: {k2}. Pulsar es no, mantener es ayuda.")
        else:
            say("De acuerdo, un solo botón. Mantenerlo pulsado será cancelar.")

    # ---- microphone ----
    info = hardware.detect()
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
    if scr:
        say({"glasses": "Veo una pantalla muy ancha; usaré el modo gafas.",
             "monitor": "Veo una pantalla; usaré el modo monitor."}[preset] if len(scr) == 1 or preset == "glasses"
            else f"Veo {len(scr)} pantallas; usaré el modo monitor en la principal.")
    result["screens"] = scr
    result["microphones"] = mics
    result["suggested_preset"] = preset

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
    if local.get("screen_preset") in (None, "auto"):
        local["screen_preset"] = preset
    cfg_path.write_text(yaml.safe_dump(local, allow_unicode=True, sort_keys=False), encoding="utf-8")
    hardware.save(result)
    say(hardware.spoken_summary(result) + " Listo. Reinicio para usar la nueva configuración.")
    return result
