# Modules

A module is a folder `modules/<name>/` containing:

- `CLAUDE.md`: rules appended to the base rules when the module is on. They
  may add behaviour; they may never relax a rule in `claude/CLAUDE.md`.
- `README.md`: what it does, what it needs installed, how to turn it on.
- Optional `start.py`: a long-running helper the loop starts at boot with the
  workspace path as its only argument, and terminates at exit.
- Optional code the agent invokes through the tool allow list.

Modules are turned on by listing them under `modules:` in `local/config.yaml`.
At every start the loop writes `workspace/CLAUDE.md` as the base rules followed
by each enabled module's `CLAUDE.md`, so the workspace always matches the
installed version.

A module can also own a panel on the screen (`onebutton/screen/screen.js`
knows the panels; the loop tells the page which ones are on).

Shipped: `maths-screen` (panel Pizarra), `scribe` (panel Escritorio).
Planned: a reader for PDFs, computation, a window switcher for foreign apps,
email-to-video.
