#!/usr/bin/env python3
"""The OneButton screen: one local page with panels. Usage: start.py <workspace> [port]

Binds to 127.0.0.1 only. Routes:

    GET  /                     the page
    GET  /board.js             blackboard editing logic
    GET  /vendor/...           KaTeX and marked
    GET  /doc/<path>           a text file under the workspace    PUT /doc/<path>  replace it
    GET  /status               {"seq": n, "docs": {path: mtime_ns}} for the docs the page watches
    POST /event                the loop pushes {"type": ...}; GET /events?after=n returns newer ones
    GET  /state                what the page last reported; POST /state sets it (never goes backwards)

Opens the browser once on first start unless ONEBUTTON_NO_BROWSER=1.
"""

from __future__ import annotations

import json
import os
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote

HERE = Path(__file__).resolve().parent
CTYPES = {"js": "application/javascript", "css": "text/css", "woff2": "font/woff2", "html": "text/html; charset=utf-8",
          "md": "text/markdown; charset=utf-8", "txt": "text/plain; charset=utf-8"}
WATCHED = ["conversacion.md", "pizarra/pizarra.md", "escritos/actual"]
EMPTY_BOARD = "# Pizarra\n\n"


def main() -> int:
    workspace = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()
    port = int(sys.argv[2]) if len(sys.argv) > 2 else int(os.environ.get("ONEBUTTON_SCREEN_PORT", 8765))
    (workspace / "pizarra" / "archivo").mkdir(parents=True, exist_ok=True)
    (workspace / "escritos").mkdir(parents=True, exist_ok=True)
    board = workspace / "pizarra" / "pizarra.md"
    if not board.exists():
        board.write_text(EMPTY_BOARD, encoding="utf-8")

    lock = threading.Lock()
    events: list[dict] = []
    state: dict = {"mode": "idle"}

    def safe(rel: str) -> Path | None:
        rel = unquote(rel).lstrip("/")
        if not rel or ".." in rel.split("/"):
            return None
        p = (workspace / rel).resolve()
        return p if workspace in p.parents or p == workspace else None

    def manuscript_path() -> str | None:
        actual = workspace / "escritos" / "actual"
        if actual.exists():
            name = actual.read_text(encoding="utf-8").strip()
            if name:
                return f"escritos/{name}/manuscrito.md"
        return None

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # quiet
            pass

        def _send(self, code: int, body: bytes, ctype: str = "application/json") -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, code: int, obj) -> None:
            self._send(code, json.dumps(obj).encode("utf-8"))

        def _body(self) -> bytes:
            n = int(self.headers.get("Content-Length") or 0)
            return self.rfile.read(n) if n else b""

        def do_GET(self):
            path, _, query = self.path.partition("?")
            if path == "/":
                self._send(200, (HERE / "index.html").read_bytes(), CTYPES["html"])
            elif path in ("/board.js", "/screen.js"):
                self._send(200, (HERE / path[1:]).read_bytes(), CTYPES["js"])
            elif path.startswith("/doc/"):
                f = safe(path[5:])
                if f and f.is_file():
                    self._send(200, f.read_bytes(), CTYPES.get(f.suffix[1:], "text/plain; charset=utf-8"))
                else:
                    self._send(404, b"", "text/plain")
            elif path == "/status":
                docs = {}
                watched = list(WATCHED)
                m = manuscript_path()
                if m:
                    watched.append(m)
                for rel in watched:
                    f = workspace / rel
                    docs[rel] = f.stat().st_mtime_ns if f.exists() else 0
                with lock:
                    seq = events[-1]["seq"] if events else 0
                self._json(200, {"seq": seq, "docs": docs, "manuscript": m})
            elif path == "/events":
                after = 0
                for part in query.split("&"):
                    if part.startswith("after="):
                        try:
                            after = int(part[6:])
                        except ValueError:
                            pass
                with lock:
                    self._json(200, [e for e in events if e["seq"] > after][-50:])
            elif path == "/state":
                with lock:
                    self._json(200, state)
            elif path.startswith("/vendor/") and ".." not in path:
                f = (HERE / path.lstrip("/")).resolve()
                if f.is_file() and HERE in f.parents:
                    self._send(200, f.read_bytes(), CTYPES.get(f.suffix[1:], "application/octet-stream"))
                else:
                    self._send(404, b"not found", "text/plain")
            else:
                self._send(404, b"not found", "text/plain")

        def do_POST(self):
            path = self.path.split("?", 1)[0]
            try:
                data = json.loads(self._body() or b"{}")
            except json.JSONDecodeError:
                self._json(400, {"error": "bad json"})
                return
            if path == "/event":
                with lock:
                    seq = (events[-1]["seq"] + 1) if events else 1
                    data = dict(data, seq=seq)
                    events.append(data)
                    del events[:-200]
                self._json(200, {"seq": seq})
            elif path == "/state":
                with lock:
                    new_seq = int(data.get("seq_handled") or 0) if isinstance(data, dict) else 0
                    if new_seq >= int(state.get("seq_handled") or 0):
                        state.clear()
                        state.update(data if isinstance(data, dict) else {})
                self._json(200, {"ok": True})
            else:
                self._send(404, b"not found", "text/plain")

        def do_PUT(self):
            path = self.path.split("?", 1)[0]
            f = safe(path[5:]) if path.startswith("/doc/") else None
            if not f:
                self._send(404, b"not found", "text/plain")
                return
            text = self._body().decode("utf-8", errors="replace")
            f.parent.mkdir(parents=True, exist_ok=True)
            tmp = f.with_suffix(f.suffix + ".tmp")
            tmp.write_text(text, encoding="utf-8")
            os.replace(tmp, f)
            self._json(200, {"ok": True, "bytes": len(text)})

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}/"
    print(f"pantalla en {url} ({workspace})", flush=True)
    if os.environ.get("ONEBUTTON_NO_BROWSER") != "1":
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
