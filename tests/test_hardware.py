import unittest

from onebutton import commands, hardware
from onebutton.config import DEFAULTS


class HardwareTests(unittest.TestCase):
    def test_preset_from_aspect(self):
        self.assertEqual(hardware.suggest_preset([{"width": 1920, "height": 1080}]), "monitor")
        self.assertEqual(hardware.suggest_preset([{"width": 3840, "height": 1080}]), "glasses")
        self.assertEqual(hardware.suggest_preset([]), "monitor")

    def test_summary(self):
        s = hardware.spoken_summary({"buttons": {"talk": "space"}, "microphones": [{"index": 0}], "screens": [{}]})
        self.assertEqual(s, "Tengo un botón, micrófono, una pantalla.")
        s = hardware.spoken_summary({"buttons": {"talk": "space", "no": "enter"}, "microphones": [], "screens": []})
        self.assertIn("dos botones", s); self.assertIn("ningún micrófono", s)

    def test_detect_never_raises(self):
        info = hardware.detect()
        self.assertIn("suggested_preset", info)

    def test_setup_voice_command(self):
        self.assertEqual(commands.classify("configura los botones", DEFAULTS).kind, commands.SETUP)
        self.assertEqual(commands.classify("configura los botones de la camisa que te dije ayer", DEFAULTS).kind, commands.TEXT)


if __name__ == "__main__":
    unittest.main()
