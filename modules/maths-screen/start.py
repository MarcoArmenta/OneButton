#!/usr/bin/env python3
"""Serve the blackboard. Usage: start.py <workspace> [port]

Serves viewer.html at /, the Markdown at /pizarra.md, and its mtime at
/status. Binds to 127.0.0.1 only. Opens the browser once on first start.
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


def main() -> int:
    workspace = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()
    port = int(sys.argv[2]) if len(sys.argv) > 2 else int(os.environ.get("PIZARRA_PORT", 8765))
    board_dir = workspace / "pizarra"
    board_dir.mkdir(parents=True, exist_ok=True)
    (board_dir / "archivo").mkdir(exist_ok=True)
    board = board_dir / "pizarra.md"
    if not board.exists():
        board.write_text(EMPTY, encoding="utf-8")
    viewer = (HERE / "viewer.html").read_bytes()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # quiet
            pass

        def _send(self, code: int, body: bytes, ctype: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path = self.path.split("?", 1)[0]
            if path == "/":
                self._send(200, viewer, "text/html; charset=utf-8")
            elif path == "/pizarra.md":
                data = board.read_bytes() if board.exists() else EMPTY.encode()
                self._send(200, data, "text/markdown; charset=utf-8")
            elif path == "/status":
                mtime = board.stat().st_mtime_ns if board.exists() else 0
                self._send(200, json.dumps({"mtime": mtime}).encode(), "application/json")
            elif path.startswith("/vendor/") and ".." not in path:
                f = (HERE / path.lstrip("/")).resolve()
                if f.is_file() and HERE in f.parents:
                    ctype = {"js": "application/javascript", "css": "text/css",
                             "woff2": "font/woff2"}.get(f.suffix[1:], "application/octet-stream")
                    self._send(200, f.read_bytes(), ctype)
                else:
                    self._send(404, b"not found", "text/plain")
            else:
                self._send(404, b"not found", "text/plain")

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
