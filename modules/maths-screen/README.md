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

Restart OneButton. The loop starts a small local server on
`http://127.0.0.1:8765` and opens it in the default browser once. Put that
window on the screen the user reads, next to or behind the terminal.

## Needs

- Any modern browser. KaTeX and marked are vendored in `vendor/`, so the
  board works with no internet at all.
- Optional: `pandoc` and a LaTeX install for PDF export.

## Voice phrases that the rules understand

- "escribe en la pizarra ..." / anything mathematical
- "borra la pizarra" / "pizarra nueva" (archives first)
- "guarda la pizarra como <nombre>" / "exporta a PDF"

## Files

- `start.py`: the server. Started by the loop with the workspace path as its
  only argument. Serves the viewer at `/`, the file at `/pizarra.md`, and
  `/status` (mtime) for cheap polling.
- `viewer.html`: the page.
- `CLAUDE.md`: rules appended to the agent's instructions when enabled.
