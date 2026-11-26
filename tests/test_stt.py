import sys
import types
import unittest
from unittest import mock

import numpy as np

from onebutton.stt import Transcriber

CUDA_ERROR = "Library cublas64_12.dll is not found or cannot be loaded"


class FakeSegment:
    def __init__(self, text):
        self.text = text


class FakeModel:
    """Loads anywhere, like the real one; on "cuda" it fails at decode time, as without the CUDA libraries."""
    loads: list = []

    def __init__(self, name, device, compute_type):
        self.device = device
        FakeModel.loads.append((device, compute_type))

    def transcribe(self, audio, **kw):
        def gen():  # faster-whisper decodes lazily: the error comes while iterating
            if self.device != "cpu":
                raise RuntimeError(CUDA_ERROR)
            yield FakeSegment(" hola me llamo Marco ")
        return gen(), None


class TranscriberDeviceTests(unittest.TestCase):
    def setUp(self):
        FakeModel.loads = []
        fake = types.ModuleType("faster_whisper")
        fake.WhisperModel = FakeModel
        patcher = mock.patch.dict(sys.modules, {"faster_whisper": fake})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.audio = np.full(16000, 0.4, dtype=np.float32)

    def cfg(self, device):
        return {"whisper_model": "small", "whisper_device": device, "language": "es"}

    def test_gpu_without_cuda_libraries_falls_back_to_cpu(self):
        t = Transcriber(self.cfg("auto"))
        self.assertEqual(t.transcribe(self.audio), "hola me llamo Marco")
        self.assertEqual(FakeModel.loads[-1], ("cpu", "int8"))

    def test_fallback_is_remembered(self):
        t = Transcriber(self.cfg("auto"))
        t.transcribe(self.audio)
        t.transcribe(self.audio)
        self.assertEqual(len(FakeModel.loads), 2)   # the original load, then the CPU one, once

    def test_cpu_errors_are_not_swallowed(self):
        t = Transcriber(self.cfg("cpu"))
        t.model.transcribe = mock.Mock(side_effect=RuntimeError("boom"))
        with self.assertRaises(RuntimeError):
            t.transcribe(self.audio)


if __name__ == "__main__":
    unittest.main()
