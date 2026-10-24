# OneButton

Voice-first computing for people who cannot use a keyboard or mouse. One big
button, a microphone, a screen, and Claude Code doing the work.

Press the button, speak, press again. The words go to Claude Code, which
writes, computes, reads email, searches, and answers aloud. Updates arrive by
saying "actualiza"; mistakes are undone by saying "deshacer".

Built by Marco Armenta for a friend in Mexico City who lives with very limited
mobility. Everything here is designed so that the person helping at home never
has to log into anything or manage accounts after a single install.

**Status: early.** The core loop exists and is testable; it has not yet been
run on the first user's machine. See [CHANGELOG.md](CHANGELOG.md).

## What you need

| Item | Notes |
| --- | --- |
| Computer | Windows 10/11, macOS, or Linux. On Linux under Wayland use `button_source: terminal`. |
| Microphone | Any USB microphone placed near the user. |
| One accessible button | A USB switch that sends the space bar. Most "big button" switches do this out of the box or with an adapter. |
| Screen | Placed where the user can read it. Large font. |
| Claude Code subscription | Logged in once by the helper. The login does expire occasionally and must be renewed by a helper. |

## Install (for the helper)

One command, run once. It needs git, Python 3.10+, and Claude Code already
installed and logged in.

Windows, in PowerShell:

```powershell
irm https://raw.githubusercontent.com/MarcoArmenta/OneButton/main/bootstrap/install.ps1 | iex
```

macOS or Linux:

```bash
curl -fsSL https://raw.githubusercontent.com/MarcoArmenta/OneButton/main/bootstrap/install.sh | bash
```

The Windows installer puts an "OneButton" shortcut on the Desktop and in the
Startup folder, so it starts with the computer. On macOS and Linux start it
with `~/OneButton/bin/onebutton`.

A full step-by-step guide in Spanish, written for non-technical helpers, is in
[docs/guia-ayudante.md](docs/guia-ayudante.md).

## Daily use

One button, two gestures: a short press and a long press (held about 1.5 s).

- **Press** the button. Speak. Pauses are fine, up to 90 seconds by default.
- **Press** again when done. The reply is spoken and shown on screen.
- **Press** while it is speaking to stop the speech.
- **Hold** the button to cancel anything: a recording, a task in progress, a
  pending confirmation. Held while idle, it explains the controls.
- During a long task it says "sigo en ello" now and then; a short press gets
  the same reassurance.
- **"Repite"** reads the last reply again.
- **"Actualiza"** checks for a new version, reads the changes aloud, and waits
  for "adelante" before installing. Anything else cancels.
- **"Deshacer"** goes back to the previous version, after the same confirmation.
- Before anything irreversible (sending, deleting, paying) the assistant says
  what it is about to do and asks "¿Adelante?". Only a clear yes proceeds.

## Safety and privacy, in plain words

- Audio is transcribed on the machine. It is not uploaded anywhere. Only the
  text of each turn goes to Claude.
- What was said and answered is appended to `local/session.log` so a helper
  can see what went wrong. It never leaves the machine; turn it off with
  `log_transcripts: false`.
- Replies are cleaned before being spoken: code, formulas, links and tables
  stay on screen and are announced, not read character by character.
- Personal things (email settings, contacts, notes, keys) live in `local/`,
  which is ignored by git and hidden from the assistant.
- The assistant treats emails and web pages as information, never as orders.
- Updates come only from signed release tags of this repository. The signing
  key is checked against a list copied to the machine at install time, which
  updates cannot change. Anything unsigned is refused.
- Every update is logged and can be undone by voice.
- The assistant cannot run `sudo`, delete recursively, or change permissions.

Full details in [docs/security.md](docs/security.md).

## Configuration

`local/config.yaml`, created from [config.example.yaml](config.example.yaml).
The usual things to change: `language`, `silence_timeout`, `button_key`,
`tts_voice`, `whisper_model`.

## Modules

Optional features, each in `modules/<name>/` with its own `CLAUDE.md` that
extends the base rules. Turn one on by listing it under `modules:` in
`local/config.yaml`.

- `maths-screen/` **(shipped)**: a blackboard in the browser. The assistant
  writes Markdown with LaTeX to a file; the page re-renders it live in large
  type, fully offline. Formulas are spoken in words and shown as symbols.
- `scribe/`: idea in, full text out, for papers and books
- `switch-scanning/`: on-screen menu driven by the button alone
- `computation/`: GAP/QPA, SageMath, QuiverLab
- `email-to-video/`: email conversation to AI video

See [modules/README.md](modules/README.md).

## Repository layout

```
onebutton/      the loop: button gestures, recording, transcription, Claude turn, speech cleanup, TTS, launcher
claude/         CLAUDE.md rules installed into the workspace, and the tool allow list
bin/            onebutton (macOS/Linux), onebutton.cmd (Windows), onebutton-release (maintainer)
bootstrap/      install.ps1, install.sh and allowed_signers
docs/           helper guide (Spanish), security model, release process
tests/          unit tests for the parts that run without audio hardware
local/          git-ignored: config.yaml, allowed_signers, state.json, logs
workspace/      git-ignored: the user's own documents, and the installed CLAUDE.md
```

## Contributing

Fork, branch, pull request. Only the maintainer merges to `main`, and only
signed tags are installable, so review is the real gate. Read
[docs/security.md](docs/security.md) before proposing anything that touches
the updater, the rules, or the allow list.

Run the tests with:

```bash
python3 -m unittest discover -s tests
```

Try the loop without hardware:

```bash
python3 -m onebutton --dry-run
```

## Credits

Built by Marco Armenta for a friend, with his permission. Licence: CC0, see
[LICENSE](LICENSE).
