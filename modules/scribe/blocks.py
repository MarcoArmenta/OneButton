#!/usr/bin/env python3
"""Numbered blocks of a manuscript, so the screen and the agent count the same way.

    blocks.py list <file>            print "N: first line..." for every block
    blocks.py get <file> N           print block N
    blocks.py set <file> N           replace block N with stdin (empty stdin deletes it)
    blocks.py insert <file> N        insert stdin as a new block after N (0 = at the start)

A block is a run of non-blank lines. Fenced code (```) and display maths ($$ on
its own line) stay whole even when they contain blank lines. Headings count
as blocks too, so every number on screen is editable.
"""

from __future__ import annotations

import sys
from pathlib import Path


def split_blocks(text: str) -> list[str]:
    out: list[str] = []
    cur: list[str] = []
    in_code = in_math = False

    def flush() -> None:
        nonlocal cur
        if any(x.strip() for x in cur):
            out.append("\n".join(cur))
        cur = []

    for line in text.split("\n"):
        t = line.strip()
        if t.startswith("```"):
            in_code = not in_code
            cur.append(line)
            if not in_code:
                flush()
            continue
        if in_code:
            cur.append(line)
            continue
        if t == "$$":
            in_math = not in_math
            cur.append(line)
            if not in_math:
                flush()
            continue
        if in_math:
            cur.append(line)
            continue
        if not t:
            flush()
            continue
        cur.append(line)
    flush()
    return out


def join_blocks(blocks: list[str]) -> str:
    return "\n\n".join(b.rstrip("\n") for b in blocks if b.strip()) + "\n"


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    cmd, path = argv[0], Path(argv[1])
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    blocks = split_blocks(text)
    if cmd == "list":
        for i, b in enumerate(blocks, 1):
            first = b.strip().split("\n")[0]
            print(f"{i}: {first[:90]}{'…' if len(first) > 90 else ''}")
        return 0
    n = int(argv[2]) if len(argv) > 2 else 0
    if cmd == "get":
        if not 1 <= n <= len(blocks):
            print(f"no hay bloque {n}; hay {len(blocks)}", file=sys.stderr)
            return 1
        print(blocks[n - 1])
        return 0
    new = sys.stdin.read().strip("\n")
    if cmd == "set":
        if not 1 <= n <= len(blocks):
            print(f"no hay bloque {n}; hay {len(blocks)}", file=sys.stderr)
            return 1
        if new.strip():
            blocks[n - 1] = new
        else:
            del blocks[n - 1]
    elif cmd == "insert":
        if not 0 <= n <= len(blocks):
            print(f"posición {n} fuera de rango; hay {len(blocks)}", file=sys.stderr)
            return 1
        blocks.insert(n, new)
    else:
        print(__doc__)
        return 2
    path.write_text(join_blocks(blocks), encoding="utf-8")
    print(f"{len(blocks)} bloques")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
