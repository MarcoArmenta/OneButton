#!/usr/bin/env python3
"""Numbered labels over the screen, or a 3x3 grid, for choosing by number or by scanning.

Reads JSON lines on stdin:
    {"labels": [{"n": 1, "x": 100, "y": 200}, ...], "selected": 3}
    {"grid": [left, top, width, height], "selected": 5}
    {"clear": true}
and draws a click-through, always-on-top transparent window. Exit on EOF.
"""

from __future__ import annotations

import json
import sys
import threading
import tkinter as tk


def main() -> int:
    root = tk.Tk()
    root.overrideredirect(True)
    root.attributes("-topmost", True)
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    root.geometry(f"{sw}x{sh}+0+0")
    key_color = "#010101"
    try:
        root.attributes("-transparentcolor", key_color)   # Windows: that colour becomes see-through
    except tk.TclError:
        root.attributes("-alpha", 0.35)
    canvas = tk.Canvas(root, bg=key_color, highlightthickness=0)
    canvas.pack(fill="both", expand=True)
    if sys.platform == "win32":
        _click_through(root)

    def draw(msg: dict) -> None:
        canvas.delete("all")
        if msg.get("clear"):
            return
        sel = msg.get("selected")
        if "labels" in msg:
            for lab in msg["labels"]:
                x, y, n = lab["x"], lab["y"], lab["n"]
                current = (n == sel)
                fill = "#ffcc00" if current else "#2a5db0"
                size = 22 if current else 16
                w = size * (1 + len(str(n)) * 0.45)
                canvas.create_rectangle(x - w / 2, y - size, x + w / 2, y + size, fill=fill, outline="white", width=2)
                canvas.create_text(x, y, text=str(n), fill="black" if current else "white", font=("Segoe UI", size, "bold"))
        if "grid" in msg:
            left, top, width, height = msg["grid"]
            cw, ch = width / 3, height / 3
            for i in range(9):
                r, c = divmod(i, 3)
                x0, y0 = left + c * cw, top + r * ch
                current = (i + 1 == sel)
                canvas.create_rectangle(x0, y0, x0 + cw, y0 + ch, outline="#ffcc00" if current else "#2a5db0", width=4 if current else 2)
                canvas.create_text(x0 + cw / 2, y0 + ch / 2, text=str(i + 1), fill="#ffcc00" if current else "#2a5db0",
                                   font=("Segoe UI", int(min(cw, ch) / 4), "bold"))

    def reader():
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            root.after(0, draw, msg)
        root.after(0, root.destroy)

    threading.Thread(target=reader, daemon=True).start()
    root.mainloop()
    return 0


def _click_through(root: tk.Tk) -> None:
    import ctypes
    hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
    GWL_EXSTYLE, WS_EX_LAYERED, WS_EX_TRANSPARENT, WS_EX_TOOLWINDOW = -20, 0x80000, 0x20, 0x80
    style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW)


if __name__ == "__main__":
    sys.exit(main())
