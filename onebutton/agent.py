"""Send one spoken turn to Claude Code and get the reply back as plain text.

Each turn is `claude -p --continue` run inside the workspace directory, which
holds CLAUDE.md (the rules) and the user's files. Tools outside the allow
list in claude/settings.json are denied rather than prompted, so a turn can
never hang waiting for a click.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from .config import LOCAL_DIR, REPO_DIR, WORKSPACE_DIR


class Agent:
    def __init__(self, cfg: dict):
        self.bin = cfg["claude_bin"]
        self.mode = cfg["permission_mode"]
        self.timeout = int(cfg["claude_timeout"])
        self.max_turns = int(cfg["max_turns"])
        self.settings = REPO_DIR / "claude" / "settings.json"
        self.workspace = WORKSPACE_DIR
        self.first_turn = True

    def _settings_json(self) -> str:
        """Allow list from claude/settings.json plus absolute deny rules for local/ and the repo code."""
        data = {"permissions": {"allow": [], "deny": []}}
        if self.settings.exists():
            data = json.loads(self.settings.read_text(encoding="utf-8"))
        deny = data.setdefault("permissions", {}).setdefault("deny", [])
        for pattern in (f"Read(//{LOCAL_DIR}/**)", f"Edit(//{LOCAL_DIR}/**)",
                        f"Edit(//{REPO_DIR}/onebutton/**)", f"Edit(//{REPO_DIR}/claude/**)"):
            if pattern not in deny:
                deny.append(pattern)
        return json.dumps(data)

    def ask(self, text: str) -> str:
        cmd = [
            self.bin, "-p", text,
            "--output-format", "text",
            "--permission-mode", self.mode,
            "--max-turns", str(self.max_turns),
        ]
        cmd += ["--settings", self._settings_json()]
        if not self.first_turn:
            cmd.append("--continue")
        try:
            proc = subprocess.run(
                cmd, cwd=self.workspace, capture_output=True, text=True, timeout=self.timeout,
            )
        except subprocess.TimeoutExpired:
            return "La tarea tardó demasiado y la detuve. Dime si quieres que lo intente de otra forma."
        except FileNotFoundError:
            return "No encuentro Claude Code en esta computadora. Hay que pedir ayuda para instalarlo."
        self.first_turn = False
        out = proc.stdout.strip()
        if proc.returncode != 0 and not out:
            err = (proc.stderr or "").strip().splitlines()
            tail = err[-1] if err else "sin detalle"
            return f"Claude Code devolvió un error: {tail}"
        return out or "Listo."
