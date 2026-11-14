"""Cross-platform supervisor: run the loop, restart it after an update or a crash.

    python -m onebutton.launcher [loop args]

Exit code 0 from the loop means quit. 3 means "I installed a new version,
start me again", so dependencies are refreshed and the loop restarts on the
new code. Anything else is a crash: say so and restart after a pause.

The libraries are also brought up to date at start whenever requirements.txt
is not the one last installed from, so an install updated with `git pull`
gets what the new code needs without anyone running pip.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import time
from pathlib import Path

from .config import LOCAL_DIR, REPO_DIR, load

REQUIREMENTS = REPO_DIR / "requirements.txt"
STAMP = LOCAL_DIR / "requirements.sha256"


def requirements_changed(req: Path = REQUIREMENTS, stamp: Path = STAMP) -> str | None:
    """The fingerprint of requirements.txt when it is not the one recorded after the last install; else None."""
    try:
        now = hashlib.sha256(req.read_bytes()).hexdigest()
    except OSError:
        return None
    try:
        before = stamp.read_text(encoding="utf-8").strip()
    except OSError:
        before = ""
    return now if now != before else None


def record_requirements(fingerprint: str, stamp: Path = STAMP) -> None:
    try:
        stamp.parent.mkdir(parents=True, exist_ok=True)
        stamp.write_text(fingerprint + "\n", encoding="utf-8")
    except OSError:
        pass


def refresh_dependencies() -> bool:
    """pip install -r requirements.txt. True when it finished cleanly. With no network it gives up quickly."""
    if not REQUIREMENTS.exists():
        return True
    try:
        proc = subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "--retries", "1", "--timeout", "20",
                               "-r", str(REQUIREMENTS)], cwd=REPO_DIR, timeout=900, check=False)
        return proc.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False


def refresh_if_changed() -> None:
    fingerprint = requirements_changed()
    if not fingerprint:
        return
    print("Poniendo al día las bibliotecas de OneButton (sólo hace falta tras una actualización)...", flush=True)
    if refresh_dependencies():
        record_requirements(fingerprint)
    else:
        print("[launcher] no pude instalar las bibliotecas nuevas; lo intentaré en el próximo arranque.", file=sys.stderr)


def announce(text: str) -> None:
    # A Speaker of its own each time: the voice is chosen when it first speaks, and what is
    # installed may have changed since the last announcement (a voice downloaded, a library added).
    from .tts import Speaker
    Speaker(load()).say(text)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    env = dict(os.environ, ONEBUTTON_HOME=str(REPO_DIR))
    refresh_if_changed()
    while True:
        rc = subprocess.call([sys.executable, "-m", "onebutton", *args], cwd=REPO_DIR, env=env)
        if rc == 0:
            return 0
        if rc == 3:
            announce("Reiniciando con la nueva versión.")
            refresh_if_changed()
        else:
            announce("OneButton se reinició. Espera un momento.")
            time.sleep(3)


if __name__ == "__main__":
    sys.exit(main())
