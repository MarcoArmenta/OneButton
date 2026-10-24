# Modules

A module is a folder `modules/<name>/` containing:

- `CLAUDE.md`: instructions appended to the base rules when the module is on.
  They may add behaviour; they may never relax a rule in `claude/CLAUDE.md`.
- `README.md`: what it does, what it needs installed, how to turn it on.
- Optional code, invoked by the agent through the tool allow list.

Modules are turned on by listing them under `modules:` in `local/config.yaml`.
The install step copies each enabled module's `CLAUDE.md` into
`workspace/modules/<name>/CLAUDE.md`, which Claude Code picks up automatically.

Nothing is shipped yet. Planned order: maths-screen, scribe, computation,
switch-scanning, email-to-video.
