"""Speech to text with faster-whisper, fully local. No audio leaves the machine."""

from __future__ import annotations

import numpy as np


class Transcriber:
    def __init__(self, cfg: dict):
        from faster_whisper import WhisperModel

        device = cfg.get("whisper_device", "auto")
        compute = "float16" if device == "cuda" else "int8"
        self.model = WhisperModel(cfg["whisper_model"], device=device, compute_type=compute)
        self.language = cfg.get("language", "es")

    def transcribe(self, audio: np.ndarray) -> str:
        if audio.size == 0:
            return ""
        segments, _ = self.model.transcribe(audio, language=self.language, vad_filter=True)
        return " ".join(seg.text.strip() for seg in segments).strip()
