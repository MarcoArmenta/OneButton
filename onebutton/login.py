"""Sign Claude Code in again without a keyboard.

`claude auth login` only talks to a real terminal, so it runs here in a pseudo-terminal
(the `pty` module on macOS and Linux, pywinpty on Windows). It opens the browser on the
claude.ai authorisation page; after "Autorizar" the browser lands on a claude.com page that
shows a code, and the CLI waits for that code to be pasted ("Paste code here if prompted").

The loop closes that gap three ways, whichever comes first: it scans the browser window's
accessibility tree for the code (computadora module, `desktop.py find_text`), it watches
the clipboard in case the user clicked the page's copy button by number, and it accepts a
code the user had Claude copy. The code is then written to the pseudo-terminal, and the
loop confirms with Claude Code's own `auth status`.

Pure helpers (ANSI stripping, URL and code extraction, prompt detection) are tested;
TerminalProcess is tested on POSIX against a small script.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import threading

ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b[()][A-Za-z0-9]|\r")
URL_RE = re.compile(r"https?://[^\s\"'<>]+")
# Claude Code's manual code is "<authorization code>#<state>", both url-safe base64-ish.
CODE_RE = re.compile(r"[A-Za-z0-9_-]{16,}#[A-Za-z0-9_-]{8,}")
PROMPT_WORDS = ("paste code", "pega el c", "paste the code")
SUCCESS_WORDS = ("logged in", "login successful", "sesión iniciada", "successfully", "you're all set")


def strip_ansi(text: str) -> str:
    return ANSI_RE.sub("", text or "")


URL_FRAGMENT_RE = re.compile(r"[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]+")


def unwrap_urls(text: str) -> str:
    """Rejoin a URL the TUI wrapped over several lines: a continuation line is a single
    space-free token of URL characters right after a line that holds a URL."""
    out: list[str] = []
    for line in strip_ansi(text).splitlines():
        stripped = line.strip()
        if out and "http" in out[-1] and stripped and URL_FRAGMENT_RE.fullmatch(stripped) and " " not in out[-1].split("http", 1)[1]:
            out[-1] += stripped
        else:
            out.append(line)
    return "\n".join(out)


def extract_url(text: str) -> str | None:
    """The sign-in URL in the terminal output."""
    m = URL_RE.search(unwrap_urls(text))
    return m.group(0).rstrip(".,)") if m else None


def extract_code(text: str) -> str | None:
    m = CODE_RE.search(text or "")
    return m.group(0) if m else None


def waiting_for_code(text: str) -> bool:
    low = strip_ansi(text).lower()
    return any(w in low for w in PROMPT_WORDS)


def looks_successful(text: str) -> bool:
    low = strip_ansi(text).lower()
    return any(w in low for w in SUCCESS_WORDS)


def clean_env() -> dict[str, str]:
    """The environment without stored credentials: a stale token must not hide the fresh login."""
    env = {k: v for k, v in os.environ.items() if k not in ("CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_API_KEY")}
    env.setdefault("TERM", "xterm-256color")
    env["COLUMNS"], env["LINES"] = "160", "40"
    return env


def read_clipboard() -> str:
    """Text on the clipboard, or ''. Never raises."""
    if sys.platform == "win32":
        cmd = ["powershell", "-NoProfile", "-Command", "Get-Clipboard -Raw"]
    elif sys.platform == "darwin":
        cmd = ["pbpaste"]
    elif shutil.which("wl-paste"):
        cmd = ["wl-paste", "--no-newline"]
    elif shutil.which("xclip"):
        cmd = ["xclip", "-selection", "clipboard", "-o"]
    else:
        return ""
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=5).stdout or ""
    except (OSError, subprocess.TimeoutExpired):
        return ""


class TerminalProcess:
    """A child process behind a pseudo-terminal, with its cleaned output accumulated in `text`."""

    def __init__(self, cmd: list[str], env: dict[str, str] | None = None):
        self.cmd = cmd
        self.env = env or clean_env()
        self.text = ""
        self._lock = threading.Lock()
        self._proc = None       # POSIX: subprocess.Popen; Windows: winpty.PtyProcess
        self._master = None     # POSIX master fd
        self.error: str | None = None

    # ---- lifecycle -------------------------------------------------------
    def start(self) -> bool:
        try:
            if sys.platform == "win32":
                from winpty import PtyProcess  # pywinpty
                self._proc = PtyProcess.spawn(self.cmd, env=self.env, dimensions=(40, 160))
            else:
                import pty
                master, slave = pty.openpty()
                self._proc = subprocess.Popen(self.cmd, stdin=slave, stdout=slave, stderr=slave, env=self.env,
                                              close_fds=True, start_new_session=True)
                os.close(slave)
                self._master = master
        except (OSError, ImportError) as exc:
            self.error = str(exc)
            return False
        threading.Thread(target=self._read, daemon=True).start()
        return True

    def alive(self) -> bool:
        if self._proc is None:
            return False
        if sys.platform == "win32":
            return bool(self._proc.isalive())
        return self._proc.poll() is None

    def write(self, text: str) -> None:
        try:
            if sys.platform == "win32":
                self._proc.write(text)
            else:
                os.write(self._master, text.encode("utf-8"))
        except (OSError, ValueError, AttributeError):
            pass

    def send_line(self, text: str) -> None:
        self.write(text + "\r")

    def kill(self) -> None:
        try:
            if self._proc is None:
                return
            if sys.platform == "win32":
                self._proc.terminate(force=True)
            else:
                self._proc.kill()
                self._proc.wait(5)
        except Exception:
            pass
        finally:
            if self._master is not None:
                try:
                    os.close(self._master)
                except OSError:
                    pass
                self._master = None

    # ---- reading ---------------------------------------------------------
    def _read(self) -> None:
        try:
            while True:
                if sys.platform == "win32":
                    chunk = self._proc.read(65536)
                    if not chunk:
                        break
                else:
                    try:
                        data = os.read(self._master, 65536)
                    except OSError:
                        break
                    if not data:
                        break
                    chunk = data.decode("utf-8", "replace")
                with self._lock:
                    self.text += strip_ansi(chunk)
                    if len(self.text) > 200_000:
                        self.text = self.text[-100_000:]
        except Exception:
            pass

    def snapshot(self) -> str:
        with self._lock:
            return self.text
