"""Speech to text with faster-whisper, fully local. No audio leaves the machine.

`whisper_device: auto` picks an NVIDIA GPU whenever one is present, even when the
CUDA libraries (cuBLAS, cuDNN) are not installed. The model then loads fine and
fails only at the first real decode. When that happens the model is reloaded on
the CPU once and the same audio is transcribed again, so a laptop with a GPU but
no CUDA still works.

He may speak English or Spanish, one utterance in one of them. Whisper is asked
which of the languages in `listen_languages` the audio is in, and nothing else
is considered: left to choose among all its languages it hears a short Spanish
command as Portuguese or Italian now and then. The recogniser is then primed
with that language's own prompt.
"""

from __future__ import annotations

import sys

import numpy as np


class Transcriber:
    def __init__(self, cfg: dict):
        self.model_name = cfg["whisper_model"]
        self.device = cfg.get("whisper_device", "auto")
        self.model = self._load(self.device)
        self.languages = [str(c) for c in (cfg.get("listen_languages") or ["en", "es"])]
        self.vad_threshold = float(cfg.get("vad_threshold", 0.35))
        self.prompts = {k: (v or "").strip() for k, v in (cfg.get("whisper_prompts") or {}).items()}
        self.last_language = self.languages[0]   # what the last utterance was in

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
        vad = {"threshold": self.vad_threshold, "min_silence_duration_ms": 700}
        language = self._which_language(audio, vad)
        segments, _ = self.model.transcribe(
            audio, language=language, vad_filter=True, vad_parameters=vad,
            initial_prompt=self.prompts.get(language) or None, beam_size=5,
        )
        text = " ".join(seg.text.strip() for seg in segments).strip()
        self.last_language = language
        return text

    def _which_language(self, audio: np.ndarray, vad: dict) -> str:
        """The likeliest of the languages we listen for. With one language there is nothing to ask."""
        if len(self.languages) == 1:
            return self.languages[0]
        # Asking for a transcription with no language makes Whisper detect it up front; the
        # segments are lazy and never read, so this costs one pass of the encoder, not a decode.
        _, info = self.model.transcribe(audio, language=None, vad_filter=True, vad_parameters=vad)
        return pick_language(getattr(info, "all_language_probs", None), getattr(info, "language", None),
                             self.languages, self.last_language)


def pick_language(probs, detected: str | None, allowed: list[str], fallback: str) -> str:
    """Of the `allowed` languages, the one Whisper finds likeliest. Pure, so it is tested.

    `probs` is Whisper's [(code, probability), ...] over every language it knows, `detected` its
    single best guess. When neither says anything about an allowed language, keep the last one.
    """
    scores = {code: p for code, p in (probs or []) if code in allowed}
    if scores:
        return max(scores, key=scores.get)
    return detected if detected in allowed else fallback
