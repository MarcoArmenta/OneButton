#!/usr/bin/env python3
"""Drive the computer: windows, keys, mouse, screenshots, volume, power.

Used two ways: the loop calls it for direct voice commands, and the agent
calls it to act on what it sees in a screenshot. Every command prints JSON.

    desktop.py windows                       [{"title", "app", "active"}]
    desktop.py focus <name>                  bring the window whose title or app contains <name> to the front
    desktop.py open <name>                   start an app by name (Start menu search on Windows)
    desktop.py minimize | maximize
    desktop.py key <combo>                   e.g. enter, esc, ctrl+s, alt+f4, win+d
    desktop.py type <text>                   type text into the focused app (Unicode safe)
    desktop.py click <x> <y> [left|right|double]   or: click here [right|double]
    desktop.py scroll <up|down> [n]
    desktop.py move <x> <y>
    desktop.py screenshot [path]             PNG of the whole screen; prints {"path", "width", "height"}
    desktop.py elements                      clickable controls of the active window: [{"n", "name", "type", "x", "y"}]
    desktop.py volume <up|down|mute>
    desktop.py power <sleep|shutdown|restart>   (the loop confirms first; the agent must too)

Windows is the first target (pywinauto for UI Automation, pyautogui for input).
On macOS and Linux the input and screenshot parts work through pyautogui;
window listing falls back to what pygetwindow or wmctrl can tell.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

WIN = os.name == "nt"
CLICKABLE = {"Button", "Hyperlink", "MenuItem", "TabItem", "ListItem", "TreeItem", "CheckBox", "RadioButton",
             "ComboBox", "Edit", "SplitButton", "Image", "Text", "DataItem", "Document"}


def out(obj) -> int:
    print(json.dumps(obj, ensure_ascii=False))
    return 0


def fail(msg: str) -> int:
    print(json.dumps({"error": msg}, ensure_ascii=False))
    return 1


# ---- windows ------------------------------------------------------------------
def list_windows() -> list[dict]:
    if WIN:
        from pywinauto import Desktop
        import ctypes
        active = ctypes.windll.user32.GetForegroundWindow()
        res = []
        for w in Desktop(backend="uia").windows():
            try:
                title = w.window_text().strip()
                if not title or not w.is_visible():
                    continue
                pid = w.process_id()
                app = _process_name(pid)
                res.append({"title": title, "app": app, "active": w.handle == active, "handle": w.handle})
            except Exception:
                continue
        return res
    try:
        import pygetwindow as gw
        return [{"title": w.title, "app": "", "active": w.isActive} for w in gw.getAllWindows() if w.title.strip()]
    except Exception:
        pass
    try:
        txt = subprocess.run(["wmctrl", "-l"], capture_output=True, text=True).stdout
        return [{"title": " ".join(l.split(None, 3)[3:]), "app": "", "active": False} for l in txt.splitlines()]
    except Exception:
        return []


def _process_name(pid: int) -> str:
    try:
        import psutil
        return psutil.Process(pid).name().lower().removesuffix(".exe")
    except Exception:
        return ""


ALIASES = {"navegador": ["chrome", "msedge", "firefox", "edge"], "chrome": ["chrome"], "edge": ["msedge", "edge"],
           "correo": ["outlook", "thunderbird", "mail", "correo"], "terminal": ["windowsterminal", "cmd", "powershell", "terminal"],
           "pdf": ["acrobat", "acrord32", "sumatrapdf", "pdf"], "lector": ["acrobat", "acrord32", "sumatrapdf", "pdf"],
           "word": ["winword", "word"], "explorador": ["explorer"], "archivos": ["explorer"], "onebutton": ["onebutton"],
           "pantalla": ["onebutton", "chrome", "msedge"], "claude": ["claude"], "notas": ["notepad", "bloc"], "bloc de notas": ["notepad"]}


def focus(name: str) -> int:
    name = name.lower().strip()
    needles = ALIASES.get(name, [name])
    wins = list_windows()
    for needle in needles:
        for w in wins:
            if needle in w["title"].lower() or needle in w.get("app", ""):
                if WIN:
                    from pywinauto import Application
                    try:
                        Application(backend="uia").connect(handle=w["handle"]).window(handle=w["handle"]).set_focus()
                    except Exception as exc:
                        return fail(f"no pude activar {w['title']}: {exc}")
                else:
                    try:
                        import pygetwindow as gw
                        gw.getWindowsWithTitle(w["title"])[0].activate()
                    except Exception:
                        subprocess.run(["wmctrl", "-a", w["title"]], check=False)
                return out({"focused": w["title"]})
    return fail(f"no hay ninguna ventana que se llame {name}")


def open_app(name: str) -> int:
    if WIN:
        import pyautogui
        pyautogui.press("win")
        time.sleep(0.6)
        pyautogui.write(name, interval=0.02)
        time.sleep(1.2)
        pyautogui.press("enter")
        return out({"opened": name, "via": "start menu"})
    try:
        subprocess.Popen([name])
        return out({"opened": name})
    except OSError as exc:
        return fail(str(exc))


def window_state(state: str) -> int:
    if WIN:
        import pyautogui
        pyautogui.hotkey("win", "down" if state == "minimize" else "up")
        return out({"window": state})
    try:
        import pygetwindow as gw
        w = gw.getActiveWindow()
        (w.minimize if state == "minimize" else w.maximize)()
        return out({"window": state})
    except Exception as exc:
        return fail(str(exc))


# ---- input ---------------------------------------------------------------------
def key(combo: str) -> int:
    import pyautogui
    parts = [p.strip() for p in combo.lower().split("+") if p.strip()]
    if len(parts) == 1:
        pyautogui.press(parts[0])
    else:
        pyautogui.hotkey(*parts)
    return out({"key": combo})


def type_text(text: str) -> int:
    if WIN:
        from pywinauto.keyboard import send_keys
        send_keys(text, with_spaces=True, with_tabs=True, with_newlines=True, pause=0.01)
    else:
        import pyautogui
        pyautogui.write(text, interval=0.01)
    return out({"typed": len(text)})


def click(x: int | None, y: int | None, how: str = "left") -> int:
    import pyautogui
    if x is None or y is None:
        x, y = pyautogui.position()
    if how == "double":
        pyautogui.doubleClick(x, y)
    else:
        pyautogui.click(x, y, button="right" if how == "right" else "left")
    return out({"clicked": [x, y], "how": how})


def scroll(direction: str, n: int = 5) -> int:
    import pyautogui
    pyautogui.scroll(n * (1 if direction == "up" else -1) * 100 if WIN else n * (1 if direction == "up" else -1))
    return out({"scrolled": direction, "n": n})


def move(x: int, y: int) -> int:
    import pyautogui
    pyautogui.moveTo(x, y, duration=0.1)
    return out({"moved": [x, y]})


def screenshot(path: str | None = None) -> int:
    import pyautogui
    p = Path(path) if path else Path(os.environ.get("TEMP") or "/tmp") / "onebutton-screen.png"
    img = pyautogui.screenshot()
    img.save(p)
    return out({"path": str(p), "width": img.width, "height": img.height})


# ---- elements (numbered overlay) ------------------------------------------------
def elements(limit: int = 80) -> list[dict]:
    if not WIN:
        return []
    from pywinauto import Desktop
    import ctypes
    hwnd = ctypes.windll.user32.GetForegroundWindow()
    try:
        win = Desktop(backend="uia").window(handle=hwnd)
    except Exception:
        return []
    found: list[dict] = []
    try:
        descendants = win.descendants()
    except Exception:
        return []
    for el in descendants:
        try:
            info = el.element_info
            ctype = info.control_type
            if ctype not in CLICKABLE:
                continue
            r = info.rectangle
            if r.width() < 8 or r.height() < 8 or not info.visible:
                continue
            name = (info.name or "").strip()
            if ctype in ("Text", "Image", "Document") and not name:
                continue
            found.append({"name": name[:60], "type": ctype, "x": int(r.mid_point().x), "y": int(r.mid_point().y),
                          "left": r.left, "top": r.top, "width": r.width(), "height": r.height()})
            if len(found) >= limit:
                break
        except Exception:
            continue
    seen = set()
    uniq = []
    for e in found:
        k = (e["x"] // 6, e["y"] // 6)
        if k in seen:
            continue
        seen.add(k)
        uniq.append(e)
    for i, e in enumerate(uniq, 1):
        e["n"] = i
    return uniq


# ---- volume and power ----------------------------------------------------------------
def volume(what: str) -> int:
    import pyautogui
    pyautogui.press({"up": "volumeup", "down": "volumedown", "mute": "volumemute"}[what], presses=3 if what != "mute" else 1)
    return out({"volume": what})


def power(what: str) -> int:
    if WIN:
        cmd = {"shutdown": ["shutdown", "/s", "/t", "5"], "restart": ["shutdown", "/r", "/t", "5"],
               "sleep": ["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"]}[what]
    elif sys.platform == "darwin":
        cmd = {"shutdown": ["osascript", "-e", 'tell app "System Events" to shut down'],
               "restart": ["osascript", "-e", 'tell app "System Events" to restart'], "sleep": ["pmset", "sleepnow"]}[what]
    else:
        cmd = {"shutdown": ["systemctl", "poweroff"], "restart": ["systemctl", "reboot"], "sleep": ["systemctl", "suspend"]}[what]
    subprocess.Popen(cmd)
    return out({"power": what})


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    cmd, args = argv[0], argv[1:]
    try:
        if cmd == "windows":
            return out([{k: v for k, v in w.items() if k != "handle"} for w in list_windows()])
        if cmd == "focus":
            return focus(" ".join(args))
        if cmd == "open":
            return open_app(" ".join(args))
        if cmd in ("minimize", "maximize"):
            return window_state(cmd)
        if cmd == "key":
            return key(" ".join(args))
        if cmd == "type":
            return type_text(" ".join(args))
        if cmd == "click":
            if args and args[0] == "here":
                return click(None, None, args[1] if len(args) > 1 else "left")
            return click(int(args[0]), int(args[1]), args[2] if len(args) > 2 else "left")
        if cmd == "scroll":
            return scroll(args[0], int(args[1]) if len(args) > 1 else 5)
        if cmd == "move":
            return move(int(args[0]), int(args[1]))
        if cmd == "screenshot":
            return screenshot(args[0] if args else None)
        if cmd == "elements":
            return out(elements())
        if cmd == "volume":
            return volume(args[0])
        if cmd == "power":
            return power(args[0])
    except Exception as exc:
        return fail(f"{type(exc).__name__}: {exc}")
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
