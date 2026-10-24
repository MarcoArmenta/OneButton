"""Assemble workspace/CLAUDE.md from the base rules plus enabled modules.

Done at every start so the workspace always reflects the installed version.
Module rules extend the base; the base is written first and says so.
"""

from __future__ import annotations

from pathlib import Path

from .config import REPO_DIR, WORKSPACE_DIR

MODULES_DIR = REPO_DIR / "modules"


def available_modules() -> list[str]:
    return sorted(p.parent.name for p in MODULES_DIR.glob("*/CLAUDE.md"))


def assemble(enabled: list[str]) -> str:
    parts = [(REPO_DIR / "claude" / "CLAUDE.md").read_text(encoding="utf-8").rstrip()]
    for name in enabled:
        path = MODULES_DIR / name / "CLAUDE.md"
        if not path.exists():
            print(f"[rules] módulo desconocido: {name}")
            continue
        parts.append(f"\n\n<!-- módulo: {name} -->\n\n" + path.read_text(encoding="utf-8").rstrip())
    return "\n".join(parts) + "\n"


def install(enabled: list[str], workspace: Path = WORKSPACE_DIR) -> Path:
    workspace.mkdir(parents=True, exist_ok=True)
    target = workspace / "CLAUDE.md"
    target.write_text(assemble(enabled), encoding="utf-8")
    return target
