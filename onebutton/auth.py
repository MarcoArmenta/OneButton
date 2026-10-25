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
"""

from __future__ import annotations

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


def status(claude_bin: str = "claude") -> dict:
    """Return Claude Code's own view: {"loggedIn": bool, "authMethod": str, ...}. Never raises."""
    exe = shutil.which(claude_bin) or claude_bin
    try:
        proc = subprocess.run([exe, "auth", "status", "--json"], capture_output=True, text=True,
                              timeout=30, env=subprocess_env())
        data = json.loads(proc.stdout or "{}")
        if isinstance(data, dict):
            return data
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        pass
    return {"loggedIn": False, "error": "no pude consultar el estado"}


def login_message(helper: str) -> str:
    return (f"Claude Code no tiene la sesión iniciada, así que no puedo hacer tareas. "
            f"Hay que avisar a {helper} para que la arregle. Mientras tanto sigo escuchando.")
