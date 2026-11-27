# OneButton

Voice-first computing for people who cannot use a keyboard or mouse. One or
two big buttons, a microphone, a screen, and Claude Code doing the work.

## Install

This part is for the helper: whoever sets the computer up, once. After it the
user needs nobody for daily use, and updates arrive by voice. The hardware is
listed under [What you need](#what-you-need). The same steps in Spanish,
written for non-technical helpers, are in
[docs/guia-ayudante.md](docs/guia-ayudante.md).

Do every step in the account of the computer (Windows, macOS or Linux) that
the user will use every day. Claude Code's sign-in and OneButton's settings
belong to that account.

### 1. Install what OneButton needs

**Windows 10 or 11**

- [Git for Windows](https://git-scm.com/download/win).
- Python 3.10 or newer from [python.org](https://www.python.org/downloads/),
  ticking **"Add python.exe to PATH"** in its installer. On a fresh Windows 11
  typing `python` opens the Microsoft Store instead of failing; that is not
  Python, and the OneButton installer will say so.
- Edge (already there) or Chrome, so the screen can open full screen.
- The "OpenSSH Client" optional feature, which signed updates are checked
  with. Recent Windows has it; if the installer warns that `ssh-keygen` is
  missing, turn it on in Settings, Apps, Optional features.

**macOS**

- Git: `xcode-select --install`.
- Python 3.10 or newer: check with `python3 --version`. If it is older,
  install a newer one from [python.org](https://www.python.org/downloads/).
- Chrome or Edge, so the screen can open full screen.

**Linux (Debian, Ubuntu)**

```bash
sudo apt install git python3 python3-venv libportaudio2 espeak-ng
```

Under Wayland the buttons are read from the terminal: set
`button_source: terminal` in the configuration after installing.

### 2. Install Claude Code and sign in

OneButton does its work through [Claude Code](https://code.claude.com/docs/en/setup),
so Claude Code has to be installed **and signed in** before OneButton is
installed. It needs a paid Claude plan (Pro, Max, Team or Enterprise) or an
Anthropic Console account; the free plan does not include Claude Code.

Windows, in PowerShell:

```powershell
irm https://claude.ai/install.ps1 | iex
```

macOS or Linux:

```bash
curl -fsSL https://claude.ai/install.sh | bash
```

Close the terminal, open a new one, and sign in:

1. Type `claude` and press Enter. The first time, it asks you to sign in: a
   browser page opens, you sign in with the account that has the plan, and
   you click **Authorize**. Back in the terminal, Claude Code is ready.
2. If Claude Code opens but is not signed in, or is signed in to the wrong
   account, type **`/login`** at its prompt and press Enter. It runs the same
   browser sign-in again.
3. Type `/exit` to leave Claude Code.
4. Check it from the terminal:

   ```
   claude auth status
   ```

   It must show `"loggedIn": true`. If it shows `false`, open `claude` again
   and run `/login`.

### 3. Run the OneButton installer

One command, run once. It is safe to run again, and running it again brings
an existing install up to date.

Windows, in PowerShell:

```powershell
irm https://raw.githubusercontent.com/MarcoArmenta/OneButton/main/bootstrap/install.ps1 | iex
```

macOS or Linux:

```bash
curl -fsSL https://raw.githubusercontent.com/MarcoArmenta/OneButton/main/bootstrap/install.sh | bash
```

It takes a few minutes, most of it downloads. What it does:

- puts OneButton in a folder called `OneButton` in the home folder
  (`%USERPROFILE%\OneButton` on Windows, `~/OneButton` elsewhere; set
  `ONEBUTTON_HOME` first to use another place);
- creates OneButton's own Python environment there and installs its libraries;
- downloads the model that understands speech and, if the computer has no
  voice for English or for Spanish, a voice to speak with;
- creates `local/`, where the settings, the credentials and the update keys
  live and which never leaves the computer, and `workspace/`, where the
  user's documents go;
- checks that Claude Code is signed in;
- installs the newest signed release, or stays on `main` while there is none;
- on Windows, puts an **OneButton** shortcut on the Desktop and in the Startup
  folder, so it starts with the computer.

It ends by saying aloud "OneButton installed correctly."

The installer writes in Spanish. What matters:

| It prints | Meaning |
| --- | --- |
| `Sesión iniciada.` | Claude Code is signed in. Nothing to do. |
| `AVISO: Claude Code no tiene sesión iniciada.` | Claude Code is not signed in. Open `claude`, run `/login`, and check with `claude auth status`. There is no need to run the installer again. |
| A line starting with `ERROR:` | Something from steps 1 and 2 is missing, and the line names it: Git, Python, Claude Code or, on Linux, `libportaudio2`. Install it, open a **new** terminal, and run the installer again. |
| `AVISO: falta ssh-keygen` | Windows only: turn on the "OpenSSH Client" optional feature. Until then updates by voice do not work. |
| `AVISO: local/allowed_signers no tiene una llave real.` | Expected for now: no signed release has been published yet, so OneButton runs the code on `main` and "update" finds nothing to install. |

### 4. Keep Claude Code signed in

The browser sign-in lapses now and then. So that the user never depends on
someone clicking "Authorize", leave a long-lived token once: with Claude Code
signed in, run

```
claude setup-token
```

copy the long token it prints, open `OneButton/local/credentials.env` in a
text editor, and put it on the `CLAUDE_CODE_OAUTH_TOKEN=` line, removing the
`#` in front. Details and the alternatives are in
[docs/login.md](docs/login.md).

If OneButton ever says "Claude Code is not signed in", the user can say
**"sign in"** / **"inicia sesión"** and do it by voice, or a helper can open
`claude` and run `/login`.

### 5. Allow the microphone and the buttons

- **Windows:** Settings, Privacy & security, Microphone: turn on "Let desktop
  apps access your microphone".
- **macOS:** the first start asks for the Microphone and for Input Monitoring
  for the Terminal. Allow both in System Settings, Privacy & Security.

### 6. Start it

- **Windows:** double-click **OneButton** on the Desktop. From then on it
  starts with the computer.
- **macOS or Linux:** `~/OneButton/bin/onebutton`. To start it with the
  computer, add that command to the login items; see the helper guide.

The first time, it asks aloud for the buttons and checks the microphone and
the screens (see [First run](#first-run)). Then it says "OneButton is ready.
Press the button and speak." Try it: press the button, say "what time is it",
press again.

The settings are in `OneButton/local/config.yaml`; see
[Configuration](#configuration).

## Quick start on one page

Print it and leave it next to the user: the buttons, and what to say.

**[Quick start, in English (PDF)](docs/quick-start.pdf)** ·
**[Inicio rápido, en español (PDF)](docs/inicio-rapido.pdf)**

## What it does

Press the button, speak, press again. The words go to Claude Code, which
writes, computes, reads email, searches, and answers aloud. Everything he
needs to see is on one local page with panels: the conversation, a maths
board, the manuscript he is writing. Updates arrive by saying "update";
mistakes are undone by saying "undo".

It speaks English and understands English and Spanish at once: every command
below works in both ("scroll down" or "baja", "new conversation" or "nueva
conversación"). Say "habla en español" and it speaks Spanish from then on.

Built by Marco Armenta for a friend in Mexico City who lives with very limited
mobility. Everything here is designed so that the person helping at home never
has to log into anything or manage accounts after a single install.

**Status: early.** The core loop exists and is testable; it has not yet been
run on the first user's machine. See [CHANGELOG.md](CHANGELOG.md).

## What you need

| Item | Notes |
| --- | --- |
| Computer | Windows 11 (first target), Windows 10, macOS, or Linux. It speaks with a voice of the language it is speaking: one installed on the system, or else an offline Piper voice downloaded once. On Linux under Wayland use `button_source: terminal`. |
| Microphone | A wireless lapel microphone, or a desk microphone near the user. Display glasses do not provide one. |
| One or two accessible buttons | USB switches that send a key each, typically the space bar and Enter. Most "big button" switch interfaces do this out of the box. The first run learns them by side ("pulsa el de la izquierda", then the right one), so whoever places them never has to know which is which. One button is enough; the second adds yes and no without speech. |
| Screen | One or two monitors, or USB-C display glasses (Xreal, Viture and similar). Looked at on every start: with two monitors the page opens full screen on the second and the terminal stays on the first; a wide virtual display switches to the `glasses` preset (true black, large type, all panels side by side). Full screen without a keyboard needs Edge or Chrome. |
| Windows Hello infrared camera | Unlocking stays as secure as a password: only his face, or the password typed by someone he trusts. The computer keeps locking when idle. OneButton cannot type into the lock screen, by design. See the helper guide. |
| Claude Code subscription | Signed in once by the helper, then kept signed in with a long-lived token so nobody has to click "Authorize" again. See [docs/login.md](docs/login.md). |

## First run

The first time it starts, the loop asks aloud for the left button, then the
right one (with a single button it waits and moves on), proposes talking with
the right one and swaps if he presses the left, checks the microphone by
asking him to say his name, and looks at the screens. It writes what it found
to the local config and restarts. Screens are looked at again on every start.
"Configura los botones" repeats it.

## Daily use

Each button has one meaning everywhere. Two gestures: a short press and a
hold of about 1.5 seconds.

| | Button 1 (right, unless he swapped) | Button 2 (left) |
| --- | --- | --- |
| Press | Talk. Press to start (a short rising two-note sound: it is listening), press again to stop (one lower note). While it is speaking, a press stops the voice and starts listening at once. | No. Cancel a recording, a task, or a question. Also stops speech, without listening. |
| Hold | Yes, when a question is pending. Otherwise repeat the last reply. | Open the screen's ring menu: panels, formula editing, read aloud, help. |

With a single button, a hold cancels (or explains the controls when idle),
and yes is the spoken word "adelante". To just silence it with a single
button: press (it stops and listens), press again (it stops listening;
nothing is said about hearing nothing).

- **The buttons belong to OneButton.** Their keys are swallowed before any
  application sees them, so a press never pages a PDF or submits a form.
  Moving a page is done by voice: **"scroll down"** / **"baja"** (half a
  screen), **"scroll down a little"** / **"baja un poco"**, **"scroll down a
  lot"** / **"baja mucho"**, **"again"** / **"otra vez"** (repeats the last
  move), **"go up"** / **"ve hacia arriba"**, **"go to the top"** / **"al
  principio"**, **"go to the end"** / **"al final"**. The wheel turns over the
  window in front.
- **"Speak Spanish"** / **"habla en inglés"** changes the language it speaks,
  now and at every start. It keeps understanding both.
- Pauses while speaking are fine, up to 90 seconds by default.
- Tremor is filtered: a double tap and a hold that loses contact for a moment
  are read as what was meant. No press is too short to count, unless a minimum
  length is set (`press_min_hold`). The thresholds are in the config.
- A soft voice is normalised before recognition, and the recogniser can be
  primed with the words he uses most.
- During a long task it says "still on it" now and then. A press of button 1
  lets him speak: "nueva conversación" leaves the task running and opens
  another conversation, "cancela" stops it, and anything else is handed to the
  running conversation ("Noted"), which Claude Code reads as soon as its
  current tool calls finish, like typing while Claude works in the terminal.
- **"Repite"** reads the last reply again.
- **"Nueva conversación"** opens another Claude Code conversation in the same
  workspace while the current one keeps working; **"conversación dos"**
  switches, **"qué conversaciones hay"** lists them, **"cierra esta
  conversación"** closes one. Each is its own long-lived Claude Code process
  (stream-json in, stream-json out, resumed by session id after a cancel or an
  idle close), so a long task never blocks a quick question. A conversation that finishes in the
  background is announced once; switching to it reads the reply.
- **"Ve a Chrome"**, **"números"**, **"pulsa el siete"**, **"escribe ..."**,
  **"cierra esta ventana"** control any application directly when the
  `computadora` module is on. "Qué hay en pantalla" or any multi-step task
  goes to Claude, which looks at the screen and acts.
- **"Dictation"** / **"nuevo escrito"** opens the writing desk, where his
  words are written down exactly as he says them; **"review"** / **"revisión"**
  asks for suggestions, which he accepts or refuses one by one. See Modules.
- **"Board"**, **"desk"**, **"conversation"** (**"pizarrón"**,
  **"escritorio"**, **"conversación"**) switch panels on the
  screen. **"Lee"** or **"lee el cinco"** reads the current panel aloud from
  the page, block by block; button 2 skips, a number jumps.
- With the OneButton page in front, the same scrolling words move the panel
  on screen, most of a screen at a time, and each panel comes back where it
  was left. **"Scroll down the board"** / **"baja el pizarrón"** scrolls that
  panel whatever is in front. What Claude writes on the board is shown at
  once, from where the new part starts.
- **"Actualiza"** checks for a new version, reads the changes aloud, and waits
  for a yes before installing. Anything else cancels.
- **"Deshacer"** goes back to the previous version, after the same confirmation.
- **"Inicia sesión"** signs Claude Code in again with no keyboard: the loop runs
  the login in a pseudo-terminal, he clicks "Autorizar" by number, and the code
  the page shows is read off the browser window and fed back to Claude Code.
  It starts by itself whenever Claude Code reports it is signed out. See
  [docs/login.md](docs/login.md).
- **"Actualiza Claude"** upgrades Claude Code itself with its own `claude update`,
  after a yes, and says which version it went from and to.
- Before anything irreversible (sending, deleting, paying) the assistant says
  what it is about to do and asks "Go ahead?". Only a clear yes proceeds.

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
The usual things to change: `speak_language` (`en` or `es`),
`listen_languages`, `silence_timeout`, `button_key`, `button2_key` (null for
one button), `button_exclusive`, `cue_sounds` (`true` by default; `false`
turns off the two sounds that tell him when it starts and stops listening),
`tts_voices`, `whisper_model`.

## The screen

A local page (`onebutton/screen/`, served on 127.0.0.1) that the loop opens in
the browser at start. It has one panel per enabled feature and switches to
whatever just changed: a reply shows the conversation, a formula written
during a turn shows the board, a drafted paragraph shows the manuscript. It
works with no internet, speaks for itself through the browser, and is driven
by the same two buttons through the loop. The terminal is for the helper.
Presets: `monitor` (tabs), `glasses` (black background, every panel side by
side across a wide virtual display), `tablet`; `screen_preset: auto` picks one
from the screens that are plugged in at start. With two monitors the page
fills the second one and the terminal stays on the first (`screen_display`).
The page opens as a full-screen app window in Edge or Chrome; without either,
the default browser opens a tab.

## Modules

Optional features, each in `modules/<name>/` with its own `CLAUDE.md` that
extends the base rules. All three shipped modules are on by default; remove one
from `modules:` in `local/config.yaml` to turn it off.

- `maths-screen/` **(shipped)**: a blackboard in the browser. The assistant
  writes Markdown with LaTeX to a file; the page re-renders it live in large
  type, fully offline. Formulas are spoken in words and shown as symbols.
  Holding button 2 opens editing: every part of the last formula gets a
  number, and "barra en el siete" or "subíndice en el dos" edits it on the
  spot. See [modules/maths-screen/README.md](modules/maths-screen/README.md).
- `scribe/` **(shipped)**: the writing desk. What he dictates is written down
  word for word, one numbered paragraph per utterance; nothing is added,
  rephrased or tidied. "Revisión" / "review" asks the assistant for
  corrections and additions, given one at a time and applied only on a yes.
  Suggestions follow the author's own style, a profile drawn from his papers
  and grown from every spoken correction; no fine-tuning. See
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
onebutton/      the loop: button gestures, recording, transcription, Claude turn, speech cleanup, TTS, launcher, the two languages (lang.py)
onebutton/screen/  the page: panels, ring menu, reading aloud, board editing, vendored KaTeX and marked
claude/         CLAUDE.md rules installed into the workspace, and the tool allow list
bin/            onebutton (macOS/Linux), onebutton.cmd (Windows), onebutton-release (maintainer)
bootstrap/      install.ps1, install.sh and allowed_signers
docs/           one-page quick start (PDF, English and Spanish), helper guide (Spanish), security model, release process
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
