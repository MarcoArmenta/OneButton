# computadora: control the whole computer

Everything a person does with a keyboard and mouse, by voice or by scanning
with the two buttons. Two layers:

**Direct commands** are parsed locally and run at once, no Claude turn:

| Say | Does |
| --- | --- |
| "qué ventanas hay" | reads the open windows |
| "ve a Chrome", "cambia al correo", "abre el bloc de notas" | switches to or starts an app |
| "cierra esta ventana", "minimiza", "maximiza" | window management |
| "números" | numbers every clickable control of the active window |
| "pulsa el siete" | clicks number 7 (with or without the overlay shown first) |
| "rejilla" | a 3×3 grid over the screen; say a cell to zoom, three times to click anywhere |
| "clic derecho", "doble clic" | at the pointer |
| "escribe hola Juan" | types into the focused app |
| "intro", "escape", "copiar", "pegar", "control s", "alt tab" | keys |
| "baja", "sube diez" | scrolls |
| "sube el volumen", "silencio" | volume |
| "apaga la computadora", "reinicia", "suspende", "bloquea" | power, after a yes |
| "qué hay en pantalla" | Claude describes the screen |

With the overlay or the grid showing, **button 2** steps to the next number
and **a held button 1** clicks it, so a bad voice day still reaches
everything. Holding button 2 cancels.

**Everything else** goes to Claude with `desktop.py`: it takes a screenshot,
reads it, finds controls with UI Automation, acts, and looks again, with the
rules in `CLAUDE.md` (confirm before anything irreversible, never type
secrets, stop at credential prompts).

## Turn it on

```yaml
modules: [maths-screen, scribe, computadora]
```

Windows is the target. Needs `pyautogui`, `pywinauto`, `psutil` and
`Pillow` (in requirements.txt). On macOS the terminal needs Accessibility
permission; on Linux X11 it works through pyautogui, Wayland does not allow it.

## Windows Voice Access

Windows 11 ships Voice Access, which does the same numbering trick system
wide and now speaks Spanish. It can run alongside OneButton, but both will
hear every word, so it is best kept asleep ("voice access sleep") and woken
only when OneButton's own commands fall short. Try it; if it suits him better
for raw computer control, OneButton can stay for the maths, the writing and
Claude.

## Files

- `desktop.py`: the driver. JSON out, one command per call.
- `overlay.py`: the click-through numbered labels and the grid, fed by JSON
  lines on stdin.
- `CLAUDE.md`: the rules and the see-act loop for the agent.
- `onebutton/desktop_commands.py`: the Spanish parser, tested.
