"""Load configuration: defaults, then config.example.yaml, then local/config.yaml."""

from __future__ import annotations

import os
from pathlib import Path

import yaml

REPO_DIR = Path(os.environ.get("ONEBUTTON_HOME", Path(__file__).resolve().parent.parent))
LOCAL_DIR = REPO_DIR / "local"
WORKSPACE_DIR = REPO_DIR / "workspace"

# Words that always work, in both languages. What the config lists is added to these, so an
# older local/config.yaml with only the Spanish words keeps understanding English too.
WORDS = {
    "confirm_words": ["go ahead", "yes go ahead", "confirm", "adelante", "sí adelante", "confirmo"],
    "cancel_words": ["cancel", "stop", "no", "cancela", "cancelar", "para"],
    "update_words": ["update", "check for updates", "actualiza", "actualizar"],
    "undo_words": ["undo", "roll back", "deshacer", "deshaz"],
    "repeat_words": ["repeat", "repeat that", "say that again", "say it again", "repite", "repítelo"],
}

WHISPER_PROMPTS = {
    "en": "Mathematics, algebra, quiver, representations, module, theorem, lemma, proof, go ahead, update, undo, "
          "board, desk, new conversation, review, scroll down.",
    "es": "Matemáticas, álgebra, carcaj, representaciones, módulo, teorema, lema, demostración, adelante, actualiza, "
          "deshacer, pizarrón, escritorio, nueva conversación, revisión, baja un poco.",
}

DEFAULTS = {
    "speak_language": "en",          # what the computer speaks: en or es
    "listen_languages": ["en", "es"],  # what it understands; one utterance is in one of them
    "button_key": "space",
    "button2_key": "enter",
    "button_exclusive": True,
    "cue_sounds": True,              # a sound when it starts listening and another when it stops
    "press_min_hold": 0.0,           # no press is too short to count; set it (0.06 to 0.12) to ignore stray touches
    "press_bounce": 0.15,
    "press_refractory": 0.35,
    "long_hold": 1.5,
    "note_hold": 5.0,                # still held this long: a note for the maintainer. 0 turns it off
    "maintainer_name": "Marco",      # who the notes are for, as it is said aloud
    "button_source": "auto",
    "silence_timeout": 90,
    "max_recording": 600,
    "sample_rate": 16000,
    "input_device": None,
    "silence_rms": "auto",
    "whisper_model": "small",
    "whisper_device": "auto",
    "vad_threshold": 0.35,
    "whisper_prompt": "",            # legacy: one prompt, used for Spanish
    "whisper_prompts": dict(WHISPER_PROMPTS),
    **{k: list(v) for k, v in WORDS.items()},
    "tts": "auto",
    "tts_voice": "",                 # legacy: one voice, used for Spanish
    "tts_voices": {"en": "", "es": ""},
    "tts_rate": 170,
    "piper_model": "",
    "piper_voice": "",
    "progress_interval": 45,
    "log_transcripts": True,
    "modules": [],
    "screen_port": 8765,
    "open_browser": True,
    "screen_preset": "auto",
    "screen_display": "auto",
    "screen_theme": "auto",
    "screen_layout": "auto",
    "screen_font_size": "auto",
    "font_size": 28,
    "helper_name": "",
    "claude_bin": "claude",
    "permission_mode": "acceptEdits",
    "claude_timeout": 600,
    "claude_idle_close": 900,
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


def normalise(cfg: dict) -> dict:
    """Fill in what an older config does not say, so every reader sees the same shape.

    `language` used to mean both the language heard and the language spoken, and was always
    Spanish. It is not read any more: `speak_language` and `listen_languages` replace it, and
    a config that predates them gets the defaults, English spoken and both understood.
    """
    for key, builtin in WORDS.items():
        words = list(cfg.get(key) or [])
        cfg[key] = words + [w for w in builtin if w not in words]
    speak = str(cfg.get("speak_language") or "en").lower()[:2]
    cfg["speak_language"] = speak if speak in ("en", "es") else "en"
    listen = cfg.get("listen_languages") or ["en", "es"]
    if isinstance(listen, str):
        listen = [listen]
    cfg["listen_languages"] = [str(code).lower()[:2] for code in listen] or ["en", "es"]
    # The single voice and the single prompt of an older config were chosen for Spanish.
    voices = {**DEFAULTS["tts_voices"], **(cfg.get("tts_voices") or {})}
    if cfg.get("tts_voice") and not voices.get("es"):
        voices["es"] = cfg["tts_voice"]
    cfg["tts_voices"] = voices
    prompts = {**WHISPER_PROMPTS, **(cfg.get("whisper_prompts") or {})}
    if cfg.get("whisper_prompt"):
        prompts["es"] = cfg["whisper_prompt"]
    cfg["whisper_prompts"] = prompts
    return cfg


def load() -> dict:
    cfg = dict(DEFAULTS)
    cfg.update(_read(REPO_DIR / "config.example.yaml"))
    cfg.update(_read(LOCAL_DIR / "config.yaml"))
    return normalise(cfg)


def save_local(**values) -> None:
    """Merge a few keys into local/config.yaml, keeping everything else the helper wrote."""
    LOCAL_DIR.mkdir(parents=True, exist_ok=True)
    path = LOCAL_DIR / "config.yaml"
    local = _read(path)
    local.update(values)
    path.write_text(yaml.safe_dump(local, allow_unicode=True, sort_keys=False), encoding="utf-8")
