"""Send one spoken turn to Claude Code and get the reply back as plain text.

Each turn is `claude -p --continue` run inside the workspace directory, which
holds CLAUDE.md (the rules) and the user's files. Tools outside the allow
list in claude/settings.json are denied rather than prompted, so a turn can
never hang waiting for a click. A turn can be cancelled from another thread.
"""

from __future__ import annotations

import json
import subprocess
import threading
import time

from .config import LOCAL_DIR, REPO_DIR, WORKSPACE_DIR

MSG_TIMEOUT = "La tarea tardó demasiado y la detuve. Dime si quieres que lo intente de otra forma."
MSG_MISSING = "No encuentro Claude Code en esta computadora. Hay que pedir ayuda para instalarlo."
MSG_CANCELLED = "Cancelado."
MSG_LOGIN = "Parece que hay que iniciar sesión en Claude Code otra vez. Hace falta que alguien ayude con eso."


class Agent:
    def __init__(self, cfg: dict):
        self.bin = cfg["claude_bin"]
        self.mode = cfg["permission_mode"]
        self.timeout = int(cfg["claude_timeout"])
        self.max_turns = int(cfg["max_turns"])
        self.settings = REPO_DIR / "claude" / "settings.json"
        self.workspace = WORKSPACE_DIR
        self.first_turn = True
        self._proc: subprocess.Popen | None = None
        self._lock = threading.Lock()
        self.cancelled = False

    def _settings_json(self) -> str:
        """Allow list from claude/settings.json plus absolute deny rules for local/ and the repo code."""
        data = {"permissions": {"allow": [], "deny": []}}
        if self.settings.exists():
            data = json.loads(self.settings.read_text(encoding="utf-8"))
        deny = data.setdefault("permissions", {}).setdefault("deny", [])
        for pattern in (f"Read(//{LOCAL_DIR}/**)", f"Edit(//{LOCAL_DIR}/**)",
                        f"Edit(//{REPO_DIR}/onebutton/**)", f"Edit(//{REPO_DIR}/claude/**)",
                        f"Edit(//{REPO_DIR}/modules/**)"):
            if pattern not in deny:
                deny.append(pattern)
        return json.dumps(data)

    def cancel(self) -> None:
        with self._lock:
            self.cancelled = True
            if self._proc and self._proc.poll() is None:
                self._proc.kill()

    def ask(self, text: str) -> str:
        cmd = [
            self.bin, "-p", text,
            "--output-format", "text",
            "--permission-mode", self.mode,
            "--max-turns", str(self.max_turns),
            "--settings", self._settings_json(),
        ]
        if not self.first_turn:
            cmd.append("--continue")
        self.cancelled = False
        try:
            with self._lock:
                self._proc = subprocess.Popen(cmd, cwd=self.workspace, stdout=subprocess.PIPE,
                                              stderr=subprocess.PIPE, text=True)
                proc = self._proc
        except FileNotFoundError:
            return MSG_MISSING
        try:
            out, err = proc.communicate(timeout=self.timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            return MSG_TIMEOUT
        if self.cancelled:
            return MSG_CANCELLED
        self.first_turn = False
        out = (out or "").strip()
        err = (err or "").strip()
        if proc.returncode != 0 and not out:
            low = err.lower()
            if any(k in low for k in ("login", "log in", "auth", "token", "credential")):
                return MSG_LOGIN
            tail = err.splitlines()[-1] if err else "sin detalle"
            return f"Claude Code devolvió un error: {tail}"
        return out or "Listo."
