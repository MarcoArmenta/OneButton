"""Cross-platform supervisor: run the loop, restart it after an update or a crash.

    python -m onebutton.launcher [loop args]

Exit code 0 from the loop means quit. 3 means "I installed a new version,
start me again", so dependencies are refreshed and the loop restarts on the
new code. Anything else is a crash: say so and restart after a pause.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time

from .config import REPO_DIR, load


def refresh_dependencies() -> None:
    req = REPO_DIR / "requirements.txt"
    if not req.exists():
        return
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "-r", str(req)],
                       cwd=REPO_DIR, timeout=600, check=False)
    except (subprocess.TimeoutExpired, OSError):
        pass


def main(argv: list[str] | None = None) -> int:
    from .tts import Speaker

    args = list(sys.argv[1:] if argv is None else argv)
    speaker = Speaker(load())
    env = dict(os.environ, ONEBUTTON_HOME=str(REPO_DIR))
    while True:
        rc = subprocess.call([sys.executable, "-m", "onebutton", *args], cwd=REPO_DIR, env=env)
        if rc == 0:
            return 0
        if rc == 3:
            speaker.say("Reiniciando con la nueva versión.")
            refresh_dependencies()
        else:
            speaker.say("OneButton se reinició. Espera un momento.")
            time.sleep(3)


if __name__ == "__main__":
    sys.exit(main())
