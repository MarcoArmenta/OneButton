"""Keep Claude Code signed in without anyone at the keyboard.

Two mechanisms, both set up once by a helper and stored in local/credentials.env:

    CLAUDE_CODE_OAUTH_TOKEN=...   a long-lived token from `claude setup-token`
                                  (uses the Claude subscription; recommended)
    ANTHROPIC_API_KEY=...         a Console API key (pay per use, never expires
                                  unless revoked)

Either is passed only to the claude subprocess's environment. The agent is
denied read access to local/, and this file never enters the repo.

`status()` asks Claude Code itself whether it is signed in, so the loop can
say so plainly at startup instead of failing on the first task.

When the sign-in lapses anyway, the user says "inicia sesión" (or the loop starts
it by itself): login.py runs `claude auth login` in a pseudo-terminal, the user
clicks "Autorizar" through the numbered overlay of the computadora module, the
code on the resulting page is read off the screen and fed back, and the loop
polls `status()` without the stored token (a stale token would hide a fresh
login) and then retires that token with `retire_token()`.
"""

from __future__ import annotations

import re

import json
import os
import shutil
import subprocess

from .config import LOCAL_DIR

CREDENTIALS_FILE = LOCAL_DIR / "credentials.env"
ACCEPTED = ("CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_API_KEY")


def parse_env(text: str) -> dict[str, str]:
    """KEY=VALUE per line; comments and blanks ignored; quotes stripped; only accepted keys kept."""
    out: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key.startswith("export "):
            key = key[7:].strip()
        value = value.strip().strip('"').strip("'")
        if key in ACCEPTED and value:
            out[key] = value
    return out


def credentials_env() -> dict[str, str]:
    if not CREDENTIALS_FILE.exists():
        return {}
    try:
        return parse_env(CREDENTIALS_FILE.read_text(encoding="utf-8"))
    except OSError:
        return {}


def subprocess_env(base: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(os.environ if base is None else base)
    env.update(credentials_env())
    return env


def status(claude_bin: str = "claude", use_credentials: bool = True) -> dict:
    """Return Claude Code's own view: {"loggedIn": bool, "authMethod": str, ...}. Never raises.

    use_credentials=False asks about the browser login alone, ignoring local/credentials.env.
    """
    exe = shutil.which(claude_bin) or claude_bin
    try:
        proc = subprocess.run([exe, "auth", "status", "--json"], capture_output=True, text=True,
                              timeout=30, env=subprocess_env() if use_credentials else dict(os.environ))
        data = json.loads(proc.stdout or "{}")
        if isinstance(data, dict):
            return data
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        pass
    return {"loggedIn": False, "error": "no pude consultar el estado"}


def version(claude_bin: str = "claude") -> str:
    """Claude Code's version string such as '2.1.316', or '' when it cannot be read."""
    try:
        proc = subprocess.run([shutil.which(claude_bin) or claude_bin, "--version"], capture_output=True,
                              text=True, timeout=30, env=subprocess_env())
    except (OSError, subprocess.TimeoutExpired):
        return ""
    m = re.search(r"\d+\.\d+\.\d+", (proc.stdout or "") + (proc.stderr or ""))
    return m.group(0) if m else ""


def login_message(helper: str) -> str:
    return (f"Claude Code no tiene la sesión iniciada, así que no puedo hacer tareas. "
            f"Di 'inicia sesión' y te ayudo a entrar desde el navegador. "
            f"Si no funciona, hay que avisar a {helper}. Mientras tanto sigo escuchando.")


URL_RE = re.compile(r"https?://[^\s\"'<>]+")


def login_url(text: str) -> str | None:
    """The sign-in URL in a line of `claude auth login` output, if any."""
    m = URL_RE.search(text or "")
    return m.group(0).rstrip(".,)") if m else None


def retire_token(path=None) -> bool:
    """Comment out CLAUDE_CODE_OAUTH_TOKEN in credentials.env after a fresh browser login, so the
    stale token stops overriding it. Returns True when a line was changed."""
    path = CREDENTIALS_FILE if path is None else path
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return False
    out, changed = [], False
    for line in text.splitlines():
        stripped = line.strip()
        key = stripped.removeprefix("export ").partition("=")[0].strip()
        if key == "CLAUDE_CODE_OAUTH_TOKEN" and not stripped.startswith("#") and stripped.partition("=")[2].strip():
            out.append("# retirado tras iniciar sesión en el navegador: " + line)
            changed = True
        else:
            out.append(line)
    if changed:
        path.write_text("\n".join(out) + "\n", encoding="utf-8")
    return changed
