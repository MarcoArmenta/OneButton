"""Send one spoken turn to Claude Code and get the reply back as plain text.

Each turn is `claude -p` run inside the workspace directory, which holds
CLAUDE.md (the rules) and the user's files. A conversation is a Claude Code
session: `--session-id` on its first turn, `--resume` on the rest, so several
conversations can live side by side in the same directory (conversations.py).
Without a session id the turn falls back to `--continue`. Tools outside the allow
list in claude/settings.json are denied rather than prompted, so a turn can
never hang waiting for a click. A turn can be cancelled from another thread.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import threading
import time

from .auth import login_message, subprocess_env
from .config import LOCAL_DIR, REPO_DIR, WORKSPACE_DIR

MSG_TIMEOUT = "La tarea tardó demasiado y la detuve. Dime si quieres que lo intente de otra forma."
MSG_MISSING = "No encuentro Claude Code en esta computadora. Hay que pedir ayuda para instalarlo."
MSG_CANCELLED = "Cancelado."


class Agent:
    def __init__(self, cfg: dict):
        # On Windows the entry point is claude.cmd; Popen only finds it through which().
        self.bin = shutil.which(cfg["claude_bin"]) or cfg["claude_bin"]
        self.mode = cfg["permission_mode"]
        self.timeout = int(cfg["claude_timeout"])
        self.max_turns = int(cfg["max_turns"])
        self.settings = REPO_DIR / "claude" / "settings.json"
        self.workspace = WORKSPACE_DIR
        self.helper = cfg.get("helper_name") or "la persona que te ayuda"
        self.first_turn = True
        self._procs: dict[str, subprocess.Popen] = {}
        self._cancelled: set[str] = set()
        self._lock = threading.Lock()

    def _settings_file(self) -> str:
        """Write the effective settings to local/ and return the path. A file survives any shell's quoting."""
        LOCAL_DIR.mkdir(parents=True, exist_ok=True)
        target = LOCAL_DIR / "claude-settings.json"
        target.write_text(self._settings_json(), encoding="utf-8")
        return str(target)

    def _settings_json(self) -> str:
        """Allow list from claude/settings.json plus absolute deny rules for local/ and the repo code."""
        data = {"permissions": {"allow": [], "deny": []}}
        if self.settings.exists():
            data = json.loads(self.settings.read_text(encoding="utf-8"))
        deny = data.setdefault("permissions", {}).setdefault("deny", [])
        local, repo = LOCAL_DIR.as_posix(), REPO_DIR.as_posix()
        for pattern in (f"Read(//{local}/**)", f"Edit(//{local}/**)",
                        f"Edit(//{repo}/onebutton/**)", f"Edit(//{repo}/claude/**)",
                        f"Edit(//{repo}/modules/**)"):
            if pattern not in deny:
                deny.append(pattern)
        return json.dumps(data)

    def cancel(self, session_id: str | None = None) -> None:
        """Kill the turn of one conversation, or every running turn."""
        with self._lock:
            for sid, proc in list(self._procs.items()):
                if session_id in (None, sid):
                    self._cancelled.add(sid)
                    if proc.poll() is None:
                        proc.kill()

    def command(self, text: str, session_id: str | None = None, resume: bool = False) -> list[str]:
        """The claude invocation for one turn. Pure, so it is tested."""
        cmd = [
            self.bin, "-p", text,
            "--output-format", "text",
            "--permission-mode", self.mode,
            "--max-turns", str(self.max_turns),
            "--settings", self._settings_file(),
        ]
        if session_id:
            cmd += ["--resume", session_id] if resume else ["--session-id", session_id]
        elif not self.first_turn:
            cmd.append("--continue")
        return cmd

    CONVERT_PROMPT = (
        "Convierte esta expresión matemática dictada en español a LaTeX. "
        "Responde únicamente con el LaTeX, sin delimitadores de dólar, sin comillas y sin explicación. "
        "Si hay varias interpretaciones razonables, elige la más común en matemáticas.\n\n{text}"
    )

    def convert_latex(self, text: str) -> str:
        """One-shot conversion in its own directory so it never becomes the --continue conversation."""
        convert_dir = LOCAL_DIR / "convert"
        convert_dir.mkdir(parents=True, exist_ok=True)
        cmd = [self.bin, "-p", self.CONVERT_PROMPT.format(text=text), "--output-format", "text",
               "--permission-mode", self.mode, "--max-turns", "1", "--settings", self._settings_file()]
        try:
            proc = subprocess.run(cmd, cwd=convert_dir, capture_output=True, text=True, timeout=90,
                                  env=subprocess_env())
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return ""
        out = (proc.stdout or "").strip().strip("`").strip()
        if out.startswith("$$") and out.endswith("$$"):
            out = out[2:-2].strip()
        elif out.startswith("$") and out.endswith("$"):
            out = out[1:-1].strip()
        return out

    def ask(self, text: str, session_id: str | None = None, resume: bool = False) -> str:
        """One turn. Safe to call from several threads at once, one per conversation."""
        cmd = self.command(text, session_id, resume)
        key = session_id or "_default"
        try:
            with self._lock:
                self._cancelled.discard(key)
                proc = subprocess.Popen(cmd, cwd=self.workspace, stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE, text=True, env=subprocess_env())
                self._procs[key] = proc
        except FileNotFoundError:
            return MSG_MISSING
        try:
            out, err = proc.communicate(timeout=self.timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            return MSG_TIMEOUT
        finally:
            with self._lock:
                self._procs.pop(key, None)
                cancelled = key in self._cancelled
                self._cancelled.discard(key)
        if cancelled:
            return MSG_CANCELLED
        self.first_turn = False
        out = (out or "").strip()
        err = (err or "").strip()
        if proc.returncode != 0 and not out:
            low = err.lower()
            if any(k in low for k in ("login", "log in", "auth", "token", "credential", "unauthorized", "401")):
                return login_message(self.helper)
            tail = err.splitlines()[-1] if err else "sin detalle"
            return f"Claude Code devolvió un error: {tail}"
        return out or "Listo."
