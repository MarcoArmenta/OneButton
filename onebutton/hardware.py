"""What is plugged in: screens and microphones. Buttons are learned by asking (setup.py)."""

from __future__ import annotations

import json
import os
from pathlib import Path

from .config import LOCAL_DIR

HARDWARE_FILE = LOCAL_DIR / "hardware.json"


def screens() -> list[dict]:
    """[{name, x, y, width, height, primary}] via screeninfo; empty when it cannot tell."""
    try:
        from screeninfo import get_monitors
        return [{"name": m.name or "", "x": int(m.x or 0), "y": int(m.y or 0), "width": m.width, "height": m.height,
                 "primary": bool(m.is_primary)}
                for m in get_monitors()]
    except Exception:
        return []


def microphones() -> list[dict]:
    """[{index, name, default}] input devices via sounddevice."""
    try:
        import sounddevice as sd
        default = sd.default.device[0] if isinstance(sd.default.device, (list, tuple)) else sd.default.device
        out = []
        for i, d in enumerate(sd.query_devices()):
            if d.get("max_input_channels", 0) > 0:
                out.append({"index": i, "name": d.get("name", ""), "default": i == default})
        return out
    except Exception:
        return []


def is_wide(s: dict) -> bool:
    """A display wider than 2.3:1 is a virtual wide screen from display glasses."""
    return bool(s.get("height")) and s["width"] / s["height"] > 2.3


def suggest_preset(found: list[dict]) -> str:
    """Wide virtual display (glasses) -> glasses; otherwise monitor."""
    for s in found:
        if is_wide(s):
            return "glasses"
    return "monitor"


def page_screen(found: list[dict], choice: str | int = "auto") -> dict | None:
    """Which screen the page goes on.

    auto: the glasses if there are any; with two or more monitors, the one that is
    not primary (the terminal stays on the primary, for the helper); else the only one.
    primary / secondary / a number pick explicitly. None when nothing is known.
    """
    if not found:
        return None
    if isinstance(choice, int) and not isinstance(choice, bool):
        return found[choice] if 0 <= choice < len(found) else found[0]
    if isinstance(choice, str) and choice.isdigit():
        return page_screen(found, int(choice))
    primary = next((s for s in found if s.get("primary")), found[0])
    others = [s for s in found if s is not primary]
    if choice == "primary":
        return primary
    if choice == "secondary":
        return others[0] if others else primary
    for s in found:
        if is_wide(s):
            return s
    return others[0] if others else primary


def detect(choice: str | int = "auto") -> dict:
    scr = screens()
    return {"screens": scr, "microphones": microphones(), "suggested_preset": suggest_preset(scr),
            "page_screen": page_screen(scr, choice), "os": os.name}


def load() -> dict | None:
    if HARDWARE_FILE.exists():
        try:
            return json.loads(HARDWARE_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
    return None


def save(info: dict) -> None:
    LOCAL_DIR.mkdir(parents=True, exist_ok=True)
    HARDWARE_FILE.write_text(json.dumps(info, indent=2, ensure_ascii=False), encoding="utf-8")


def spoken_summary(info: dict) -> str:
    b = info.get("buttons") or {}
    n = sum(1 for k in ("talk", "no") if b.get(k))
    parts = []
    parts.append({0: "ningún botón", 1: "un botón", 2: "dos botones"}[min(n, 2)])
    mics = info.get("microphones") or []
    parts.append("micrófono" if mics else "ningún micrófono")
    scr = info.get("screens") or []
    parts.append({0: "ninguna pantalla detectada", 1: "una pantalla"}.get(len(scr), f"{len(scr)} pantallas"))
    return "Tengo " + ", ".join(parts) + "."
