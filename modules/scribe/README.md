# scribe: the writing desk

Dictate, and your words are written down exactly as you said them. Ask for a
review when you want suggestions, and decide on each one. Adds the **Desk**
(**Escritorio**) panel to the screen and rules for the assistant.

## Dictation and review

- "Nuevo escrito" / "new paper", "abre el escrito X" / "open the paper X" or
  "dictado" / "dictation" starts. From then on each thing you say becomes one
  numbered paragraph, character for character as it was heard: nothing added,
  rephrased, tidied or typeset. A new piece starts empty, with no title or
  outline.
- While you dictate, what you say is not taken for an order to the computer:
  a sentence that begins "Abre..." or "Go to..." is written down, not carried
  out. Scrolling ("baja un poco", "scroll down") and volume still work.
- Orders about the text are understood as orders: "borra lo último" / "delete
  the last one", "junta el dos y el tres", "in five, change X to Y", "punto y
  aparte" / "new paragraph", "título: ..." / "title: ...".
- "Revisión" / "review" asks for suggestions: corrections (a misheard word,
  grammar, a spoken formula to typeset) and additions (a missing step, a
  transition, headings). They come one at a time, each shown as it is and as
  it would be; "sí" / "yes" applies that one, "no" / "next" leaves the text
  alone. Nothing changes without a yes.
- "Fin del dictado" / "end dictation" ends it.

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
  "borra el tres" means the same thing to both. `blocks.py append` adds a
  dictated paragraph at the end, exactly as given.
- "Lee" reads the manuscript aloud block by block from the page: button 2
  skips to the next block, a number jumps, holding button 2 stops.
- Export with pandoc to PDF or LaTeX.

## Learning the author's style

Style shapes what the assistant *suggests* in a review and what it writes when
asked to write; it never touches dictated text.

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
- `blocks.py`: list, get, set, insert, append numbered blocks. Tested in
  `tests/test_blocks.py` against the page's own block rule.
