# maths-screen: the blackboard

A browser page that shows `workspace/pizarra/pizarra.md` in large type with
LaTeX rendered, and refreshes itself whenever the file changes. The agent
writes maths there and speaks about it in words, so formulas never get read
aloud as symbols.

## Turn it on

In `local/config.yaml`:

```yaml
modules: [maths-screen]
```

Restart OneButton. The board is the **Pizarra** panel of the screen the loop
opens at start. Put that browser window on the screen the user reads.

## Needs

- Any modern browser. KaTeX and marked are vendored in `vendor/`, so the
  board works with no internet at all.
- Optional: `pandoc` and a LaTeX install for PDF export.

## Editing what is on the board

Voice composes, buttons point. With two buttons, **hold button 2** and choose
"Editar fórmula" in the ring (or say "editar fórmula"). The last formula gets a numbered chip for every part that can be
edited: each symbol, each subscripted or superscripted term, each fraction,
root, decorated symbol and bracketed group. Then:

- **Say a number** to pick a part, or step through them with button 2 and
  pick with a held button 1. The chosen part is coloured in the formula.
- **Say what to do**, in one breath if you like: "barra en el siete",
  "subíndice en el dos", "fracción en el cuatro", "borra el tres". The menu
  (Decorar, Índices, Estructura, Editar) is also on screen as a ring: button
  2 steps, a held button 1 chooses, "atrás" goes up a level.
- **When content is needed** (a subscript, an exponent, a denominator, a
  replacement) the board says "dicta el subíndice" and the next thing you say
  is converted to LaTeX by Claude and inserted. Anything said with a part
  selected that is not a number or a menu word is treated the same way, as a
  free-form replacement: "cámbialo por una suma desde uno hasta n".
- "anterior" and "siguiente" move between formulas. "deshacer" undoes the
  last edit on the board. "salir", or a held button 2, leaves board mode.

Edits are instant and local: the page parses the formula with KaTeX, splices
the LaTeX source, and writes the file back. Claude is only called to turn
dictated content into LaTeX. The board speaks for itself through the
browser's speech engine, so turn the browser's sound on.

## Voice phrases that the rules understand

- "escribe en la pizarra ..." / anything mathematical
- "borra la pizarra" / "pizarra nueva" (archives first)
- "guarda la pizarra como <nombre>" / "exporta a PDF"

## Files

- `CLAUDE.md`: the rules. The page code lives in `onebutton/screen/`
  (`board.js` for hints, menu and splicing; its core is pure and tested in
  node, the whole flow in headless Chromium).
- `CLAUDE.md`: rules appended to the agent's instructions when enabled.
