"""Turn a spoken note about something that went wrong into an issue on the project's repository.

He holds his button five seconds and says what happened. Nobody is beside him to write it
down or to read the log, so the note goes by itself to where the people who can fix it will
see it: the issues of the GitHub repository. When it cannot be sent (no connection, no key
yet) it stays in local/reports/ and goes out with the next one, so a note is never lost.

What leaves the computer is the note he dictated for that purpose, a few facts the loop
passes (version, system, buttons) and the last presses and recordings from local/session.log.
That log also holds everything he said and everything that was answered: none of it is sent.
Lines are chosen by an allow-list, so a kind of line added to the log later stays private
until someone decides otherwise.

The key that lets it write issues is one line in local/credentials.env, set up once by a helper:

    ONEBUTTON_GITHUB_TOKEN=...   a fine-grained token with "Issues: read and write" on this
                                 repository and nothing else

On a helper's own computer a signed-in GitHub CLI (`gh auth login`) works too. The key is sent
to api.github.com and nowhere else, and never appears in a message, a saved note or the log.
"""

from __future__ import annotations

import http.client
import json
import re
import subprocess
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

from .config import LOCAL_DIR

CREDENTIALS_FILE = LOCAL_DIR / "credentials.env"
REPORTS_DIR = LOCAL_DIR / "reports"
TOKEN_KEY = "ONEBUTTON_GITHUB_TOKEN"
API = "https://api.github.com"

TITLE_PREFIX = "Voice note: "
TITLE_MAX = 70
LINE_MAX = 300      # one log line; a press or a recording is far shorter
BODY_MAX = 60000    # GitHub refuses a body over 65536 characters
FOOTER = ("_Sent by voice from OneButton. Apart from the note above, it contains nothing that was said "
          "to the computer or that the computer answered._")

# "2026-11-27T17:03:12 BOTÓN: talk short (idle) -> talk", as the loop's log() writes it.
_LOG_LINE = re.compile(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?) ([^\s:]+): ?(.*)$")
# Presses and recordings are names of states and numbers. Every other kind of line can hold his words.
_TECHNICAL = ("BOTÓN", "GRABACIÓN")
_FAILED_ORDER = re.compile(r"^error en ([\w?-]{1,30}):\s*(.*)$")
_FAILURE_KIND = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,40}(?:Error|Exception)\b")

_REPO_URL = re.compile(
    r"^(?:https?://(?:[^/@\s]+@)?(?:www\.)?github\.com/|(?:ssh://)?git@github\.com[:/])"
    r"([A-Za-z0-9][A-Za-z0-9-]*)/([A-Za-z0-9._-]+?)(?:\.git)?/?$", re.IGNORECASE)
_SLUG = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9._-]+")
_SAVED = re.compile(r"^(\d{8}-\d{6})(?:-(\d+))?\.md$")
_SENT_LINE = re.compile(r"\n\nSent: \S+\n\Z")

_REFUSALS = {
    401: "GitHub did not accept the key",
    403: "GitHub refused the key for this repository",
    404: "GitHub did not find the repository, or the key cannot see it",
    410: "the repository has issues turned off",
    422: "GitHub did not accept the note",
}


class ReportError(Exception):
    """The note could not be sent. The message is short and never holds the key."""


def _one_line(text: object) -> str:
    return " ".join(str(text).split())


def _cut(text: str, width: int) -> str:
    return text if len(text) <= width else text[: width - 1].rstrip() + "…"


def _scrub(text: str, key: str | None) -> str:
    return text.replace(key, "…") if key else text


# ---- what the log may say ---------------------------------------------------
def _failure_only(text: str) -> str:
    """'error en type: Command [... what he typed ...] timed out' -> 'error en type: timed out'.

    The detail of a failed order can quote the text he typed (a timeout prints the whole
    command) or the title of a window he had open, so only the order's name and the kind of
    failure are kept.
    """
    m = _FAILED_ORDER.match(text)
    if not m:
        return "error"
    order, detail = m.groups()
    kind = _FAILURE_KIND.match(detail)
    hint = kind.group(0) if kind else "timed out" if "timed out" in detail else ""
    return f"error en {order}: {hint}" if hint else f"error en {order}"


def technical_lines(log_text: str, limit: int = 40) -> list[str]:
    """The last `limit` presses, recordings and failed orders of the log, oldest first.

    A line that does not start with a timestamp and a known name is dropped: it is the second
    line of a long answer, or something the loop did not write.
    """
    kept: list[str] = []
    for line in reversed(log_text.splitlines()):
        if len(kept) >= limit:
            break
        m = _LOG_LINE.match(line)
        if not m:
            continue
        stamp, who, text = m.groups()
        if who in _TECHNICAL:
            kept.append(_cut(f"{stamp} {who}: {text}", LINE_MAX))
        elif who == "EQUIPO" and text.startswith("error"):
            kept.append(f"{stamp} {who}: {_failure_only(text)}")
    return kept[::-1]


# ---- the issue ----------------------------------------------------------------
def _quote(note: str) -> str:
    lines = note.strip().splitlines() or ["(empty)"]
    return "\n".join(f"> {line}".rstrip() for line in lines)


def _detail(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return ", ".join(_one_line(v) for v in value)
    return _one_line(value)


def _fence(lines: list[str]) -> str:
    """Longer than any run of backticks inside, so no line can close the block early."""
    longest = max((len(run) for line in lines for run in re.findall(r"`+", line)), default=0)
    return "`" * max(3, longest + 1)


def compose(note: str, info: dict, log_text: str = "") -> tuple[str, str]:
    """(title, body) of the issue. The note is kept as he said it, in his language."""
    title = _cut(TITLE_PREFIX + (_one_line(note) or "(empty)"), TITLE_MAX)
    parts = [_quote(note)]
    details = [f"- {key}: {_detail(value)}" for key, value in (info or {}).items() if _detail(value)]
    if details:
        parts.append("## Details\n\n" + "\n".join(details))
    lines = technical_lines(log_text)
    if lines:
        fence = _fence(lines)
        parts.append("## Last presses and recordings\n\n" + "\n".join([fence + "text", *lines, fence]))
    parts.append(FOOTER)
    return title, "\n\n".join(parts)


def repo_slug(repo_url: str) -> str | None:
    """'https://github.com/Owner/Repo.git' or 'git@github.com:Owner/Repo.git' -> 'Owner/Repo'."""
    m = _REPO_URL.match(str(repo_url or "").strip())
    if not m or m.group(2) in (".", ".."):
        return None
    return f"{m.group(1)}/{m.group(2)}"


# ---- the key --------------------------------------------------------------------
def _token_in(text: str) -> str | None:
    found = None
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, sep, value = line.partition("=")
        if sep and key.strip() == TOKEN_KEY:   # a commented line has '#' in its key and never matches
            found = value.strip().strip('"').strip("'").strip() or found
    return found


def token(credentials_file: Path | None = None, run=subprocess.run) -> str | None:
    """The key that may write issues: from local/credentials.env, else from a signed-in `gh`."""
    path = Path(credentials_file) if credentials_file else CREDENTIALS_FILE
    try:
        # utf-8-sig: Notepad may put a byte-order mark before the first line.
        found = _token_in(path.read_text(encoding="utf-8-sig", errors="replace"))
    except OSError:
        found = None
    if found:
        return found
    try:
        proc = run(["gh", "auth", "token"], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    out = (proc.stdout or "").strip()
    return out if proc.returncode == 0 and out else None


# ---- sending ----------------------------------------------------------------------
def _refusal(exc: urllib.error.HTTPError) -> str:
    said = ""
    try:
        said = _one_line(json.loads(exc.read()).get("message") or "")
        exc.close()
    except Exception:   # GitHub's own words are a courtesy; the code is the answer
        pass
    reason = _REFUSALS.get(exc.code, "GitHub refused the note")
    return f"{reason} ({exc.code})" + (f": {_cut(said, 120)}" if said else "")


def send(title: str, body: str, slug: str, token: str, opener=urllib.request.urlopen, timeout: float = 20) -> str:
    """Open the issue and return its address. Any failure is a ReportError without the key in it."""
    key = (token or "").strip()
    # A key with a space or a line break would be quoted back by the error it causes.
    if not re.fullmatch(r"[\x21-\x7e]+", key):
        raise ReportError("the key is not valid")
    if not _SLUG.fullmatch(slug or ""):
        raise ReportError("not a GitHub repository")
    request = urllib.request.Request(
        f"{API}/repos/{slug}/issues",
        data=json.dumps({"title": title, "body": _cut(body, BODY_MAX)}).encode("utf-8"),
        headers={"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28",
                 "User-Agent": "OneButton", "Content-Type": "application/json"},
        method="POST")
    # Unredirected: if GitHub ever answers with a redirect, the key is not carried to the new address.
    request.add_unredirected_header("Authorization", f"Bearer {key}")
    try:
        response = opener(request, timeout=timeout)
        try:
            issue = json.loads(response.read())
        finally:
            close = getattr(response, "close", None)
            if close:
                close()
    except urllib.error.HTTPError as exc:
        raise ReportError(_scrub(_refusal(exc), key)) from None
    except OSError as exc:   # no network, no DNS, TLS, a timeout: all of them "later"
        late = isinstance(exc, TimeoutError) or isinstance(getattr(exc, "reason", None), TimeoutError)
        raise ReportError("GitHub did not answer in time" if late else "no connection to GitHub") from None
    except (ValueError, http.client.HTTPException):
        raise ReportError("unexpected answer from GitHub") from None
    except Exception as exc:   # only its name: the text of an unknown error could quote the request
        raise ReportError(f"could not send ({type(exc).__name__})") from None
    url = issue.get("html_url") if isinstance(issue, dict) else None
    if not isinstance(url, str) or not url.startswith("https://"):
        raise ReportError("unexpected answer from GitHub")
    return url


# ---- kept on disk -------------------------------------------------------------------
def _folder(folder: Path | None) -> Path:
    return Path(folder) if folder else REPORTS_DIR


def save(title: str, body: str, folder: Path | None = None, now: datetime | None = None) -> Path:
    """Write the note to local/reports/YYYYMMDD-HHMMSS.md and return where it is."""
    folder = _folder(folder)
    folder.mkdir(parents=True, exist_ok=True)
    stamp = (now or datetime.now()).strftime("%Y%m%d-%H%M%S")
    n = 1
    while True:
        stem = stamp if n == 1 else f"{stamp}-{n}"
        path = folder / f"{stem}.md"
        n += 1
        # A sent note keeps its name: taking it again would overwrite that note when this one is sent.
        if path.exists() or (folder / f"{stem}.sent.md").exists():
            continue
        try:
            with path.open("x", encoding="utf-8", newline="\n") as fh:
                fh.write(f"# {_one_line(title)}\n\n{body}\n")
        except FileExistsError:
            continue
        return path


def _age(path: Path) -> tuple[str, int, str]:
    # By hand because "x-2.md" sorts before "x.md" as text, and it was written after it.
    m = _SAVED.match(path.name)
    return (m.group(1), int(m.group(2) or 1), path.name) if m else (path.name, 0, path.name)


def pending(folder: Path | None = None) -> list[Path]:
    """Notes saved and not yet sent, oldest first."""
    try:
        files = [p for p in _folder(folder).iterdir()
                 if p.is_file() and p.name.endswith(".md") and not p.name.endswith(".sent.md")]
    except OSError:
        return []
    return sorted(files, key=_age)


def mark_sent(path: Path, url: str) -> Path:
    """x.md -> x.sent.md, with the issue's address at the end."""
    path = Path(path)
    if path.name.endswith(".sent.md"):
        return path
    done = path.with_name(path.name[: -len(".md")] + ".sent.md")
    # Renamed before the address is written: whatever fails after this, the note is not sent twice.
    path.replace(done)
    try:
        with done.open("a", encoding="utf-8", newline="\n") as fh:
            fh.write(f"\n\nSent: {url}\n")
    except OSError:
        pass
    return done


def read_saved(path: Path) -> tuple[str, str]:
    """(title, body) of a saved note, as they were given to save()."""
    path = Path(path)
    text = path.read_text(encoding="utf-8", errors="replace")
    if path.name.endswith(".sent.md"):
        text = _SENT_LINE.sub("", text)
    if not text.startswith("# "):
        return "Voice note", text.strip()   # not written by save(): sent whole rather than left behind
    head, _, body = text.partition("\n")
    body = body[1:] if body.startswith("\n") else body
    return head[2:].strip(), body[:-1] if body.endswith("\n") else body


# ---- the whole thing ------------------------------------------------------------------
def deliver(note: str, info: dict, log_text: str, repo_url: str, folder: Path | None = None,
            get_token=token, sender=send) -> dict:
    """Save the note, then send every note that is waiting, oldest first. Never raises.

    Returns {"saved": where this note is, "url": its issue or None, "error": None or a short
    reason, "sent": how many notes went out in this call}.
    """
    out: dict = {"saved": None, "url": None, "error": None, "sent": 0}
    key = None
    try:
        title, body = compose(note, info, log_text)
        mine = out["saved"] = save(title, body, folder)   # on disk before anything can fail
        slug = repo_slug(repo_url)
        key = get_token() if slug else None
        if not slug or not key:
            out["error"] = "no key" if slug else "not a GitHub repository"
            return out
        for path in pending(folder):
            try:
                saved = read_saved(path)
            except OSError:
                out["error"] = f"could not read {path.name}"
                continue   # one unreadable file must not hold back the others
            try:
                url = sender(*saved, slug, key)
            except ReportError as exc:
                out["error"] = str(exc)
                break   # most likely no connection: the rest wait with this one
            out["sent"] += 1
            if path.name == mine.name:
                out["url"] = url
            done = mark_sent(path, url)
            if path.name == mine.name:
                out["saved"] = done
    except Exception as exc:   # he is in the middle of using the computer: say it, never stop the loop
        out["error"] = out["error"] or _scrub(_cut(f"{type(exc).__name__}: {_one_line(exc)}", 200), key)
    return out
