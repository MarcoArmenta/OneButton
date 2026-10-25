"""Client for the blackboard server (modules/maths-screen/start.py)."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request


class Board:
    def __init__(self, port: int = 8765):
        self.base = f"http://127.0.0.1:{port}"

    def _call(self, method: str, path: str, data: dict | None = None, timeout: float = 2.0):
        body = json.dumps(data).encode("utf-8") if data is not None else None
        req = urllib.request.Request(self.base + path, data=body, method=method,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8") or "null")

    def available(self) -> bool:
        try:
            return "mtime" in self._call("GET", "/status")
        except (urllib.error.URLError, OSError, ValueError):
            return False

    def post(self, event: dict) -> int:
        try:
            return int(self._call("POST", "/event", event)["seq"])
        except (urllib.error.URLError, OSError, ValueError, KeyError):
            return 0

    def state(self) -> dict:
        try:
            st = self._call("GET", "/state")
            return st if isinstance(st, dict) else {}
        except (urllib.error.URLError, OSError, ValueError):
            return {}

    def wait_handled(self, seq: int, timeout: float = 2.5) -> dict:
        """Poll until the viewer reports it processed event `seq`; return its state."""
        end = time.monotonic() + timeout
        st = {}
        while time.monotonic() < end:
            st = self.state()
            if int(st.get("seq_handled") or 0) >= seq:
                return st
            time.sleep(0.1)
        return st
