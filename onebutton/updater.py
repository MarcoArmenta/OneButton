"""Update and undo, with one rule: only signed tags from the official repo.

State lives in local/state.json: the tag currently installed and the one
before it. Signatures are SSH signatures verified against
local/allowed_signers, which is copied from bootstrap/allowed_signers once
at install time and never overwritten by an update. A compromised repo can
therefore not grant itself new signing keys.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .config import LOCAL_DIR, REPO_DIR

STATE_FILE = LOCAL_DIR / "state.json"
ALLOWED_SIGNERS = LOCAL_DIR / "allowed_signers"
TAG_RE = re.compile(r"^v\d+\.\d+\.\d+$")


@dataclass
class Release:
    tag: str
    notes: str


class UpdateError(Exception):
    pass


def _git(*args: str, cwd: Path = REPO_DIR, check: bool = True) -> str:
    proc = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise UpdateError(proc.stderr.strip() or f"git {' '.join(args)} failed")
    return proc.stdout.strip()


def read_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {"current": None, "previous": None}


def write_state(state: dict) -> None:
    LOCAL_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def version_key(tag: str) -> tuple[int, ...]:
    return tuple(int(p) for p in tag[1:].split("."))


def verify_tag(tag: str, repo: Path = REPO_DIR) -> None:
    """Raise UpdateError unless `tag` carries a valid SSH signature from an allowed key."""
    if not ALLOWED_SIGNERS.exists():
        raise UpdateError("Falta local/allowed_signers; no puedo verificar la firma.")
    # Pin the verifier so a machine-wide gpg.ssh.program (a signing-only wrapper, say)
    # cannot silently break or bypass verification.
    proc = subprocess.run(
        ["git", "-c", "gpg.format=ssh", "-c", "gpg.ssh.program=ssh-keygen",
         "-c", f"gpg.ssh.allowedSignersFile={ALLOWED_SIGNERS}", "tag", "-v", tag],
        cwd=repo, capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise UpdateError(f"La firma de {tag} no es válida o no es de una llave autorizada.")


def changelog_for(tag: str, repo: Path = REPO_DIR) -> str:
    """Return the CHANGELOG.md section for `tag` as it exists at that tag."""
    try:
        text = _git("show", f"{tag}:CHANGELOG.md", cwd=repo)
    except UpdateError:
        return ""
    pattern = re.compile(rf"^## \[?{re.escape(tag)}\]?.*?$", re.MULTILINE)
    m = pattern.search(text)
    if not m:
        return ""
    rest = text[m.end():]
    nxt = re.search(r"^## ", rest, re.MULTILINE)
    return (rest[: nxt.start()] if nxt else rest).strip()


def check(repo: Path = REPO_DIR) -> Release | None:
    """Fetch tags and return the newest verified release newer than current, or None."""
    _git("fetch", "--tags", "--quiet", "origin", cwd=repo)
    tags = [t for t in _git("tag", "--list", cwd=repo).splitlines() if TAG_RE.match(t)]
    if not tags:
        return None
    current = read_state().get("current")
    newest = max(tags, key=version_key)
    if current and version_key(newest) <= version_key(current):
        return None
    verify_tag(newest, repo)
    return Release(newest, changelog_for(newest, repo))


def install(tag: str, repo: Path = REPO_DIR) -> None:
    verify_tag(tag, repo)
    state = read_state()
    _git("checkout", "--quiet", tag, cwd=repo)
    state = {"current": tag, "previous": state.get("current")}
    write_state(state)
    _log(f"install {tag}")


def undo(repo: Path = REPO_DIR) -> str | None:
    state = read_state()
    prev = state.get("previous")
    if not prev:
        return None
    verify_tag(prev, repo)
    _git("checkout", "--quiet", prev, cwd=repo)
    write_state({"current": prev, "previous": state.get("current")})
    _log(f"undo -> {prev}")
    return prev


def _log(line: str) -> None:
    import datetime as dt

    LOCAL_DIR.mkdir(parents=True, exist_ok=True)
    with (LOCAL_DIR / "updates.log").open("a", encoding="utf-8") as fh:
        fh.write(f"{dt.datetime.now().isoformat(timespec='seconds')} {line}\n")
