"""Load configuration: defaults, then config.example.yaml, then local/config.yaml."""

from __future__ import annotations

import os
from pathlib import Path

import yaml

REPO_DIR = Path(os.environ.get("ONEBUTTON_HOME", Path(__file__).resolve().parent.parent))
LOCAL_DIR = REPO_DIR / "local"
WORKSPACE_DIR = REPO_DIR / "workspace"

DEFAULTS = {
    "language": "es",
    "button_key": "space",
    "button2_key": "enter",
    "button_source": "auto",
    "silence_timeout": 90,
    "max_recording": 600,
    "sample_rate": 16000,
    "input_device": None,
    "silence_rms": "auto",
    "whisper_model": "small",
    "whisper_device": "auto",
    "confirm_words": ["adelante", "sí adelante", "confirmo"],
    "cancel_words": ["cancela", "cancelar", "no", "para"],
    "update_words": ["actualiza", "actualizar"],
    "undo_words": ["deshacer", "deshaz"],
    "repeat_words": ["repite", "repítelo"],
    "tts": "auto",
    "tts_voice": "",
    "tts_rate": 170,
    "piper_model": "",
    "progress_interval": 45,
    "log_transcripts": True,
    "modules": [],
    "screen_port": 8765,
    "open_browser": True,
    "font_size": 28,
    "helper_name": "",
    "claude_bin": "claude",
    "permission_mode": "acceptEdits",
    "claude_timeout": 600,
    "max_turns": 30,
    "repo_url": "https://github.com/MarcoArmenta/OneButton.git",
}


def _read(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a mapping")
    return data


def load() -> dict:
    cfg = dict(DEFAULTS)
    cfg.update(_read(REPO_DIR / "config.example.yaml"))
    cfg.update(_read(LOCAL_DIR / "config.yaml"))
    return cfg
