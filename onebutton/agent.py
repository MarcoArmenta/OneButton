"""Talk to Claude Code: one long-lived process per conversation, messages in, replies out.

Each conversation is a `claude -p --input-format stream-json --output-format stream-json`
process kept alive in the workspace directory, which holds CLAUDE.md (the rules) and
the user's files. The first start of a conversation passes `--session-id`; any later
start (after a cancel, a crash or an idle close) passes `--resume`, so nothing is lost.

User messages are JSON lines on stdin. A message written while a turn is running is
queued by Claude Code itself (`priority: next`: read in the same turn once the running
tool calls finish, or at the start of the next turn), exactly what the interactive
keyboard does. Every finished turn comes back as a `result` line, handed to the
conversation's callback from a reader thread.

Tools outside the allow list in claude/settings.json are denied rather than prompted,
so a turn can never hang waiting for a click.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import threading
import time
import uuid

from .auth import login_message, subprocess_env
from .config import LOCAL_DIR, REPO_DIR, WORKSPACE_DIR

MSG_TIMEOUT = "La tarea tardó demasiado y la detuve. Dime si quieres que lo intente de otra forma."
MSG_MISSING = "No encuentro Claude Code en esta computadora. Hay que pedir ayuda para instalarlo."
MSG_CANCELLED = "Cancelado."
MSG_CRASHED = "Claude Code se cerró de golpe. Repite lo último y lo intento de nuevo."
MSG_MAX_TURNS = "Me quedé sin pasos para esta tarea. Dime si sigo."
AUTH_HINTS = ("login", "log in", "auth", "token", "credential", "unauthorized", "401", "not logged")


def user_message(text: str, priority: str = "next") -> dict:
    """One stdin line for Claude Code's stream-json input."""
    return {"type": "user", "uuid": str(uuid.uuid4()),
            "message": {"role": "user", "content": text},
            "parent_tool_use_id": None, "priority": priority}


def reply_from_result(d: dict, helper: str) -> str:
    """The spoken reply for a `result` line; pure, so it is tested."""
    subtype = d.get("subtype") or ""
    text = (d.get("result") or "").strip()
    if subtype == "success" and text:
        return text
    if subtype == "error_max_turns":
        return MSG_MAX_TURNS
    errors = " ".join(str(e) for e in (d.get("errors") or [])) if isinstance(d.get("errors"), list) else str(d.get("errors") or "")
    low = (errors + " " + text).lower()
    if any(k in low for k in AUTH_HINTS):
        return login_message(helper)
    if text:
        return text
    return f"Claude Code devolvió un error: {errors.strip() or subtype or 'sin detalle'}."


class Session:
    """A conversation's process. Thread-safe: the loop sends, a reader thread receives."""

    def __init__(self, agent: Agent, session_id: str, on_reply):
        self.agent = agent
        self.id = session_id
        self.on_reply = on_reply
        self.created = False          # a process has run for this id: later starts use --resume
        self.proc: subprocess.Popen | None = None
        self.pending = 0              # messages sent since the last result
        self.last_send = 0.0
        self.last_activity = time.monotonic()
        self.cancelled = False
        self.lock = threading.RLock()
        self._stderr: list[str] = []

    # ---- process -------------------------------------------------------
    def command(self) -> list[str]:
        a = self.agent
        cmd = [a.bin, "-p", "--verbose", "--input-format", "stream-json", "--output-format", "stream-json",
               "--permission-mode", a.mode, "--max-turns", str(a.max_turns), "--settings", a.settings_file()]
        cmd += ["--resume", self.id] if self.created else ["--session-id", self.id]
        return cmd

    def alive(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def start(self) -> bool:
        with self.lock:
            if self.alive():
                return True
            try:
                self.proc = subprocess.Popen(self.command(), cwd=self.agent.workspace, stdin=subprocess.PIPE,
                                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                             encoding="utf-8", errors="replace", bufsize=1, env=subprocess_env())
            except FileNotFoundError:
                self.proc = None
                return False
            self.cancelled = False
            self._stderr = []
            self.last_activity = time.monotonic()
            threading.Thread(target=self._read, args=(self.proc,), daemon=True).start()
            threading.Thread(target=self._drain_stderr, args=(self.proc,), daemon=True).start()
            return True

    def send(self, text: str, priority: str = "next") -> bool:
        with self.lock:
            if not self.start():
                return False
            try:
                self.proc.stdin.write(json.dumps(user_message(text, priority), ensure_ascii=False) + "\n")
                self.proc.stdin.flush()
            except (OSError, ValueError):
                return False
            self.pending += 1
            self.last_send = self.last_activity = time.monotonic()
            return True

    def cancel(self) -> None:
        """Kill the turn. The conversation survives: the next message resumes the session."""
        with self.lock:
            self.cancelled = True
            self.pending = 0
            if self.alive():
                self.proc.kill()

    def close(self) -> None:
        with self.lock:
            if not self.alive():
                return
            try:
                self.proc.stdin.close()
            except OSError:
                pass
        try:
            self.proc.wait(5)
        except subprocess.TimeoutExpired:
            self.proc.kill()

    # ---- reading -------------------------------------------------------
    def _drain_stderr(self, proc: subprocess.Popen) -> None:
        try:
            for line in proc.stderr:
                self._stderr.append(line.rstrip())
                del self._stderr[:-20]
        except (OSError, ValueError):
            pass

    def _read(self, proc: subprocess.Popen) -> None:
        try:
            for line in proc.stdout:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(d, dict):
                    continue
                if d.get("type") == "system" and d.get("subtype") == "init":
                    self.created = True
                if d.get("type") == "result":
                    with self.lock:
                        self.pending = 0
                        self.last_activity = time.monotonic()
                    self.on_reply(reply_from_result(d, self.agent.helper))
        except (OSError, ValueError):
            pass
        proc.wait()
        for pipe in (proc.stdin, proc.stdout, proc.stderr):
            try:
                pipe.close()
            except (OSError, ValueError, AttributeError):
                pass
        with self.lock:
            if proc is not self.proc:
                return
            unanswered, cancelled = self.pending, self.cancelled
            self.pending = 0
            err = " ".join(self._stderr).lower()
        if unanswered and not cancelled:
            if any(k in err for k in AUTH_HINTS):
                self.on_reply(login_message(self.agent.helper))
            else:
                self.on_reply(MSG_CRASHED)

    # ---- housekeeping (called by the agent's watchdog) -----------------
    def tick(self, now: float) -> None:
        with self.lock:
            if not self.alive():
                return
            if self.pending and now - self.last_send > self.agent.timeout:
                self.cancel()
                self.on_reply(MSG_TIMEOUT)
            elif not self.pending and now - self.last_activity > self.agent.idle_close:
                self.close()   # memory back; the next message resumes the session


class Agent:
    def __init__(self, cfg: dict):
        # On Windows the entry point is claude.cmd; Popen only finds it through which().
        self.bin = shutil.which(cfg["claude_bin"]) or cfg["claude_bin"]
        self.mode = cfg["permission_mode"]
        self.timeout = int(cfg["claude_timeout"])
        self.idle_close = int(cfg.get("claude_idle_close", 900))
        self.max_turns = int(cfg["max_turns"])
        self.settings = REPO_DIR / "claude" / "settings.json"
        self.workspace = WORKSPACE_DIR
        self.helper = cfg.get("helper_name") or "la persona que te ayuda"
        self.sessions: dict[str, Session] = {}
        self._lock = threading.Lock()
        self._watchdog: threading.Thread | None = None

    def settings_file(self) -> str:
        """Write the effective settings to local/ and return the path. A file survives any shell's quoting."""
        LOCAL_DIR.mkdir(parents=True, exist_ok=True)
        target = LOCAL_DIR / "claude-settings.json"
        target.write_text(self._settings_json(), encoding="utf-8")
        return str(target)

    _settings_file = settings_file  # older name, kept for callers and tests

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

    # ---- conversations ---------------------------------------------------
    def session(self, session_id: str, on_reply) -> Session:
        with self._lock:
            s = self.sessions.get(session_id)
            if s is None:
                s = self.sessions[session_id] = Session(self, session_id, on_reply)
            else:
                s.on_reply = on_reply
            if self._watchdog is None:
                self._watchdog = threading.Thread(target=self._watch, daemon=True)
                self._watchdog.start()
            return s

    def send(self, session_id: str, text: str, on_reply, priority: str = "next") -> None:
        """Queue a message for a conversation. The reply reaches on_reply(text) from another thread.

        Sending while that conversation is still working is fine: Claude Code reads the
        message in the same turn once the running tool calls finish, or starts the next turn.
        """
        s = self.session(session_id, on_reply)
        if not s.send(text, priority):
            on_reply(MSG_MISSING if not shutil.which(self.bin) and not shutil.which(self.bin.split("/")[-1]) else MSG_CRASHED)

    def working(self, session_id: str) -> bool:
        s = self.sessions.get(session_id)
        return bool(s and s.pending)

    def cancel(self, session_id: str | None = None) -> None:
        """Kill the turn of one conversation, or every running turn."""
        for sid, s in list(self.sessions.items()):
            if session_id in (None, sid):
                s.cancel()

    def close(self, session_id: str) -> None:
        s = self.sessions.pop(session_id, None)
        if s:
            s.cancel()

    def shutdown(self) -> None:
        for s in list(self.sessions.values()):
            s.close()

    def _watch(self) -> None:
        while True:
            time.sleep(1.0)
            for s in list(self.sessions.values()):
                try:
                    s.tick(time.monotonic())
                except Exception:
                    pass

    # ---- one-shot helpers --------------------------------------------------
    CONVERT_PROMPT = (
        "Convierte esta expresión matemática dictada en español a LaTeX. "
        "Responde únicamente con el LaTeX, sin delimitadores de dólar, sin comillas y sin explicación. "
        "Si hay varias interpretaciones razonables, elige la más común en matemáticas.\n\n{text}"
    )

    def convert_latex(self, text: str) -> str:
        """One-shot conversion in its own directory so it never touches a conversation."""
        convert_dir = LOCAL_DIR / "convert"
        convert_dir.mkdir(parents=True, exist_ok=True)
        cmd = [self.bin, "-p", self.CONVERT_PROMPT.format(text=text), "--output-format", "text",
               "--permission-mode", self.mode, "--max-turns", "1", "--settings", self.settings_file()]
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
