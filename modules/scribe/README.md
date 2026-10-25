# scribe: the writing desk

Dictate ideas, get prose in your own style, correct it by paragraph number.
Adds the **Escritorio** panel to the screen and rules for the assistant.

## Turn it on

```yaml
modules: [maths-screen, scribe]
```

## How it works

- Each piece of writing is a folder `workspace/escritos/<name>/` with
  `manuscrito.md` (Markdown with LaTeX), `notas.md`, `bibliografia.bib` and an
  optional per-project `perfil.md`. `workspace/escritos/actual` names the
  open one; the screen shows that manuscript with every block numbered.
- Blocks are counted by `blocks.py`, and the page counts the same way, so
  "reescribe el tres" means the same thing to both.
- "Lee" reads the manuscript aloud block by block from the page: button 2
  skips to the next block, a number jumps, holding button 2 stops.
- Export with pandoc to PDF or LaTeX.

## Learning the author's style

Put the author's own papers (PDF, TeX, Markdown or text) in
`workspace/estilo/corpus/`. That folder is outside the repository and never
shared. Say "aprende mi estilo". The assistant extracts:

- `estilo/perfil.md`: how the author writes, as a style guide.
- `estilo/ejemplos.md`: short verbatim excerpts with their sources.

Every spoken correction ("yo no diría eso así") is appended to
`estilo/preferencias.md` and applied from then on. All three files are plain
text the author can hear read back and change. No model is fine-tuned; the
profile is loaded into every writing turn.

## Files

- `CLAUDE.md`: the rules.
- `blocks.py`: list, get, set, insert numbered blocks. Tested in
  `tests/test_blocks.py` against the page's own block rule.
