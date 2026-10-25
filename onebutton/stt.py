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
        self.vad_threshold = float(cfg.get("vad_threshold", 0.35))
        self.prompt = (cfg.get("whisper_prompt") or "").strip() or None

    def transcribe(self, audio: np.ndarray) -> str:
        if audio.size == 0:
            return ""
        peak = float(np.max(np.abs(audio))) if audio.size else 0.0
        if 0 < peak < 0.3:
            audio = audio * (0.5 / peak)   # soft voice: normalise before VAD and recognition
        segments, _ = self.model.transcribe(
            audio, language=self.language, vad_filter=True,
            vad_parameters={"threshold": self.vad_threshold, "min_silence_duration_ms": 700},
            initial_prompt=self.prompt, beam_size=5,
        )
        return " ".join(seg.text.strip() for seg in segments).strip()
