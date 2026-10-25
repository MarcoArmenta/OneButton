# OneButton

Voice-first computing for people who cannot use a keyboard or mouse. One or
two big buttons, a microphone, a screen, and Claude Code doing the work.

Press the button, speak, press again. The words go to Claude Code, which
writes, computes, reads email, searches, and answers aloud. Everything he
needs to see is on one local page with panels: the conversation, a maths
board, the manuscript he is writing. Updates arrive by saying "actualiza";
mistakes are undone by saying "deshacer".

Built by Marco Armenta for a friend in Mexico City who lives with very limited
mobility. Everything here is designed so that the person helping at home never
has to log into anything or manage accounts after a single install.

**Status: early.** The core loop exists and is testable; it has not yet been
run on the first user's machine. See [CHANGELOG.md](CHANGELOG.md).

## What you need

| Item | Notes |
| --- | --- |
| Computer | Windows 11 (first target; natural voices recommended), Windows 10, macOS, or Linux. On Linux under Wayland use `button_source: terminal`. |
| Microphone | A wireless lapel microphone, or a desk microphone near the user. Display glasses do not provide one. |
| One or two accessible buttons | USB switches that send the space bar (button 1, the stronger hand) and Enter (button 2). Most "big button" switch interfaces do this out of the box. One button is enough; the second adds yes and no without speech. |
| Screen | A monitor, or USB-C display glasses (Xreal, Viture and similar), which the `glasses` preset is tuned for: true black, large type, all panels side by side. |
| Windows Hello infrared camera | Unlocking stays as secure as a password: only his face, or the password typed by someone he trusts. The computer keeps locking when idle. OneButton cannot type into the lock screen, by design. See the helper guide. |
| Claude Code subscription | Signed in once by the helper, then kept signed in with a long-lived token so nobody has to click "Authorize" again. See [docs/login.md](docs/login.md). |

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

## First run

The first time it starts, the loop asks aloud for the button he will talk
with, then for a second button if there is one, checks the microphone by
asking him to say his name, and looks at the screens. It writes what it
found to the local config and restarts. "Configura los botones" repeats it.

## Daily use

Each button has one meaning everywhere. Two gestures: a short press and a
hold of about 1.5 seconds.

| | Button 1 (stronger hand) | Button 2 |
| --- | --- | --- |
| Press | Talk. Press to start, press again to stop. Also stops speech. | No. Cancel a recording, a task, or a question. Also stops speech. |
| Hold | Yes, when a question is pending. Otherwise repeat the last reply. | Open the screen's ring menu: panels, formula editing, read aloud, help. |

With a single button, a hold cancels (or explains the controls when idle),
and yes is the spoken word "adelante".

- Pauses while speaking are fine, up to 90 seconds by default.
- Tremor is filtered: taps too short to be deliberate, double taps, and a
  hold that loses contact for a moment are all read as what was meant. The
  thresholds are in the config.
- A soft voice is normalised before recognition, and the recogniser can be
  primed with the words he uses most.
- During a long task it says "sigo en ello" now and then; a press of button
  1 gets the same reassurance.
- **"Repite"** reads the last reply again.
- **"Ve a Chrome"**, **"números"**, **"pulsa el siete"**, **"escribe ..."**,
  **"cierra esta ventana"** control any application directly when the
  `computadora` module is on. "Qué hay en pantalla" or any multi-step task
  goes to Claude, which looks at the screen and acts.
- **"Pizarra"**, **"escritorio"**, **"conversación"** switch panels on the
  screen. **"Lee"** or **"lee el cinco"** reads the current panel aloud from
  the page, block by block; button 2 skips, a number jumps.
- **"Actualiza"** checks for a new version, reads the changes aloud, and waits
  for a yes before installing. Anything else cancels.
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
- Credentials live in `local/credentials.env`, outside the repo and out of
  the assistant's reach. At startup the loop checks the sign-in and says
  plainly, naming the helper, if a human is needed.

Full details in [docs/security.md](docs/security.md).

## Configuration

`local/config.yaml`, created from [config.example.yaml](config.example.yaml).
The usual things to change: `language`, `silence_timeout`, `button_key`,
`button2_key` (null for one button), `tts_voice`, `whisper_model`.

## The screen

A local page (`onebutton/screen/`, served on 127.0.0.1) that the loop opens in
the browser at start. It has one panel per enabled feature and switches to
whatever just changed: a reply shows the conversation, a formula written
during a turn shows the board, a drafted paragraph shows the manuscript. It
works with no internet, speaks for itself through the browser, and is driven
by the same two buttons through the loop. The terminal is for the helper.
Presets: `monitor` (tabs), `glasses` (black background, every panel side by
side across a wide virtual display), `tablet`.

## Modules

Optional features, each in `modules/<name>/` with its own `CLAUDE.md` that
extends the base rules. Turn one on by listing it under `modules:` in
`local/config.yaml`.

- `maths-screen/` **(shipped)**: a blackboard in the browser. The assistant
  writes Markdown with LaTeX to a file; the page re-renders it live in large
  type, fully offline. Formulas are spoken in words and shown as symbols.
  Holding button 2 opens editing: every part of the last formula gets a
  number, and "barra en el siete" or "subíndice en el dos" edits it on the
  spot. See [modules/maths-screen/README.md](modules/maths-screen/README.md).
- `scribe/` **(shipped)**: the writing desk. Dictate ideas, get prose in the
  author's own style, correct by paragraph number ("reescribe el tres"). The
  style is a profile extracted from the author's own papers and grown from
  every spoken correction; no fine-tuning. See
  [modules/scribe/README.md](modules/scribe/README.md).
- `computadora/` **(shipped)**: the whole computer. Window switching,
  numbered labels on any app's controls, a click grid, keys, typing, volume
  and power, by voice or by scanning with the two buttons; and for anything
  else Claude looks at the screen and acts, under strict rules. See
  [modules/computadora/README.md](modules/computadora/README.md).
- `computation/`: GAP/QPA, SageMath, QuiverLab
- `email-to-video/`: email conversation to AI video

See [modules/README.md](modules/README.md).

## Repository layout

```
onebutton/      the loop: button gestures, recording, transcription, Claude turn, speech cleanup, TTS, launcher
onebutton/screen/  the page: panels, ring menu, reading aloud, board editing, vendored KaTeX and marked
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
