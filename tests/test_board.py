"""Blackboard: server endpoints (Python), core logic (node), end to end (node + Playwright)."""

import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
START = REPO / "onebutton" / "screen" / "start.py"


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def node_has(module: str) -> bool:
    if not shutil.which("node"):
        return False
    return subprocess.run(["node", "-e", f"require('{module}')"], capture_output=True).returncode == 0


class ServerMixin:
    def start_server(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.port = free_port()
        self.proc = subprocess.Popen([sys.executable, str(START), str(self.tmp), str(self.port)],
                                     env=dict(os.environ, ONEBUTTON_NO_BROWSER="1"),
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(50):
            try:
                self.get("/status")
                return
            except OSError:
                time.sleep(0.1)
        raise RuntimeError("server did not start")

    def stop_server(self):
        self.proc.terminate()
        self.proc.wait(5)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def req(self, method, path, data=None, ctype="application/json"):
        body = data if isinstance(data, bytes) else (json.dumps(data).encode() if data is not None else None)
        r = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", data=body, method=method,
                                   headers={"Content-Type": ctype})
        with urllib.request.urlopen(r, timeout=5) as resp:
            raw = resp.read()
        return json.loads(raw) if resp.headers.get("Content-Type", "").startswith("application/json") else raw

    def get(self, path):
        return self.req("GET", path)


class ServerTests(ServerMixin, unittest.TestCase):
    def setUp(self):
        self.start_server()

    def tearDown(self):
        self.stop_server()

    def test_events_state_and_put(self):
        self.assertEqual(self.get("/status")["seq"], 0)
        s1 = self.req("POST", "/event", {"type": "enter"})["seq"]
        s2 = self.req("POST", "/event", {"type": "voice", "text": "siete"})["seq"]
        self.assertEqual((s1, s2), (1, 2))
        self.assertEqual([e["type"] for e in self.get("/events?after=1")], ["voice"])
        self.req("POST", "/state", {"mode": "hints", "seq_handled": 2})
        self.assertEqual(self.get("/state")["mode"], "hints")
        self.req("PUT", "/doc/pizarron/pizarron.md", "# Pizarrón\n\n$x$\n".encode(), "text/markdown")
        self.assertEqual((self.tmp / "pizarron" / "pizarron.md").read_text(encoding="utf-8"), "# Pizarrón\n\n$x$\n")
        self.assertEqual(self.req("GET", "/doc/pizarron/pizarron.md"), "# Pizarrón\n\n$x$\n".encode())
        self.assertIn("pizarron/pizarron.md", self.get("/status")["docs"])
        with self.assertRaises(urllib.error.HTTPError):
            self.get("/doc/../config.example.yaml")
        self.req("PUT", "/doc/escritos/actual", b"tesis", "text/plain")
        self.assertEqual(self.get("/status")["manuscript"], "escritos/tesis/manuscrito.md")

    def test_vendor_is_served_and_traversal_is_not(self):
        self.assertTrue(len(self.req("GET", "/vendor/katex/katex.min.css")) > 1000)
        with self.assertRaises(urllib.error.HTTPError):
            self.get("/vendor/../start.py")

    def test_board_client(self):
        from onebutton.board import Board
        b = Board(self.port)
        self.assertTrue(b.available())
        seq = b.post({"type": "enter"})
        self.req("POST", "/state", {"mode": "hints", "seq_handled": seq})
        self.assertEqual(b.wait_handled(seq)["mode"], "hints")
        self.assertFalse(Board(free_port()).available())


class BrowserLaunchTests(unittest.TestCase):
    def setUp(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("onebutton_screen_start", START)
        self.start = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.start)

    def test_rect_parsing(self):
        self.assertEqual(self.start.parse_rect("1920,0,2560,1440"), (1920, 0, 2560, 1440))
        self.assertIsNone(self.start.parse_rect(None)); self.assertIsNone(self.start.parse_rect(""))
        self.assertIsNone(self.start.parse_rect("1,2,3")); self.assertIsNone(self.start.parse_rect("0,0,0,0"))

    def test_command_is_a_fresh_fullscreen_app_window(self):
        cmd = self.start.browser_command("/x/msedge.exe", "http://127.0.0.1:8765/", (1920, 0, 2560, 1440), Path("/p"))
        self.assertEqual(cmd[0], "/x/msedge.exe")
        self.assertIn("--app=http://127.0.0.1:8765/", cmd)
        self.assertIn("--user-data-dir=" + str(Path("/p")), cmd, "own profile so a running browser cannot swallow the flags")
        self.assertIn("--start-fullscreen", cmd)
        self.assertIn("--window-position=1920,0", cmd); self.assertIn("--window-size=2560,1440", cmd)
        cmd = self.start.browser_command("/x/chrome", "http://127.0.0.1:8765/", None, Path("/p"))
        self.assertFalse(any(a.startswith("--window-") for a in cmd))

    def test_find_browser_never_raises(self):
        found = self.start.find_browser()
        self.assertTrue(found is None or isinstance(found, str))


@unittest.skipUnless(shutil.which("node"), "needs node")
class CoreTests(unittest.TestCase):
    def test_core(self):
        r = subprocess.run(["node", str(REPO / "tests" / "board_core.test.js")], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


@unittest.skipUnless(node_has("playwright"), "needs node and playwright")
class EndToEndTests(ServerMixin, unittest.TestCase):
    def setUp(self):
        self.start_server()

    def tearDown(self):
        self.stop_server()

    def test_full_flow(self):
        r = subprocess.run(["node", str(REPO / "tests" / "board_e2e.js"), str(self.tmp), str(self.port)],
                           capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
