"""Speech to text with faster-whisper, fully local. No audio leaves the machine.

`whisper_device: auto` picks an NVIDIA GPU whenever one is present, even when the
CUDA libraries (cuBLAS, cuDNN) are not installed. The model then loads fine and
fails only at the first real decode. When that happens the model is reloaded on
the CPU once and the same audio is transcribed again, so a laptop with a GPU but
no CUDA still works.
"""

from __future__ import annotations

import sys

import numpy as np


class Transcriber:
    def __init__(self, cfg: dict):
        self.model_name = cfg["whisper_model"]
        self.device = cfg.get("whisper_device", "auto")
        self.model = self._load(self.device)
        self.language = cfg.get("language", "es")
        self.vad_threshold = float(cfg.get("vad_threshold", 0.35))
        self.prompt = (cfg.get("whisper_prompt") or "").strip() or None

    def _load(self, device: str):
        from faster_whisper import WhisperModel

        compute = "float16" if device == "cuda" else "int8"
        return WhisperModel(self.model_name, device=device, compute_type=compute)

    def transcribe(self, audio: np.ndarray) -> str:
        if audio.size == 0:
            return ""
        peak = float(np.max(np.abs(audio))) if audio.size else 0.0
        if 0 < peak < 0.3:
            audio = audio * (0.5 / peak)   # soft voice: normalise before VAD and recognition
        try:
            return self._decode(audio)
        except RuntimeError as exc:
            if self.device == "cpu":
                raise
            print(f"[stt] la GPU no sirve para transcribir ({exc}); uso la CPU.", file=sys.stderr, flush=True)
            self.device = "cpu"
            self.model = self._load("cpu")
            return self._decode(audio)

    def _decode(self, audio: np.ndarray) -> str:
        segments, _ = self.model.transcribe(
            audio, language=self.language, vad_filter=True,
            vad_parameters={"threshold": self.vad_threshold, "min_silence_duration_ms": 700},
            initial_prompt=self.prompt, beam_size=5,
        )
        return " ".join(seg.text.strip() for seg in segments).strip()
