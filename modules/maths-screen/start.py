#!/usr/bin/env python3
"""Serve the blackboard. Usage: start.py <workspace> [port]

Binds to 127.0.0.1 only. Routes:

    GET  /              the viewer page
    GET  /board.js      the board logic (hints, menu, editing)
    GET  /vendor/...    KaTeX and marked
    GET  /pizarra.md    the board text        PUT /pizarra.md   replace it (viewer edits)
    GET  /status        {"mtime": ns, "seq": n}  cheap polling target
    POST /event         the loop pushes {"type": ...}; GET /events?after=n returns newer ones
    GET  /state         what the viewer last reported; POST /state sets it

Opens the browser once on first start unless PIZARRA_NO_BROWSER=1.
"""

from __future__ import annotations

import json
import os
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
EMPTY = "# Pizarra\n\n"
CTYPES = {"js": "application/javascript", "css": "text/css", "woff2": "font/woff2", "html": "text/html; charset=utf-8"}


def main() -> int:
    workspace = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()
    port = int(sys.argv[2]) if len(sys.argv) > 2 else int(os.environ.get("PIZARRA_PORT", 8765))
    board_dir = workspace / "pizarra"
    board_dir.mkdir(parents=True, exist_ok=True)
    (board_dir / "archivo").mkdir(exist_ok=True)
    board = board_dir / "pizarra.md"
    if not board.exists():
        board.write_text(EMPTY, encoding="utf-8")

    lock = threading.Lock()
    events: list[dict] = []          # [{"seq": n, ...}]
    state: dict = {"mode": "idle"}

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
                self._send(200, (HERE / "viewer.html").read_bytes(), CTYPES["html"])
            elif path == "/board.js":
                self._send(200, (HERE / "board.js").read_bytes(), CTYPES["js"])
            elif path == "/pizarra.md":
                data = board.read_bytes() if board.exists() else EMPTY.encode()
                self._send(200, data, "text/markdown; charset=utf-8")
            elif path == "/status":
                mtime = board.stat().st_mtime_ns if board.exists() else 0
                with lock:
                    seq = events[-1]["seq"] if events else 0
                self._json(200, {"mtime": mtime, "seq": seq})
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
                    # Reports are posted asynchronously; never let an older one overwrite a newer one.
                    new_seq = int(data.get("seq_handled") or 0) if isinstance(data, dict) else 0
                    if new_seq >= int(state.get("seq_handled") or 0):
                        state.clear()
                        state.update(data if isinstance(data, dict) else {})
                self._json(200, {"ok": True})
            else:
                self._send(404, b"not found", "text/plain")

        def do_PUT(self):
            path = self.path.split("?", 1)[0]
            if path != "/pizarra.md":
                self._send(404, b"not found", "text/plain")
                return
            text = self._body().decode("utf-8", errors="replace")
            tmp = board.with_suffix(".md.tmp")
            tmp.write_text(text, encoding="utf-8")
            os.replace(tmp, board)
            self._json(200, {"ok": True, "bytes": len(text)})

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}/"
    print(f"pizarra en {url} ({board})", flush=True)
    if os.environ.get("PIZARRA_NO_BROWSER") != "1":
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
