"""First-run setup: buttons learned by side, screens described, config written. No hardware."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

from onebutton import hardware, setup


class Speaker:
    def __init__(self):
        self.said = []

    def say(self, text, **kw):
        self.said.append(text)
        return True


def scripted(*keys):
    """wait_key stand-in: returns the next scripted key per call (None = timeout)."""
    it = iter(keys)
    return lambda seconds: next(it, None)


class LearnButtonsTests(unittest.TestCase):
    def test_two_buttons_right_talks_by_default(self):
        sp = Speaker()
        out = setup.learn_buttons(sp.say, scripted("enter", "space", None), pause=lambda s: None)
        self.assertEqual(out["sides"], {"left": "enter", "right": "space"})
        self.assertEqual(out["talk_side"], "right")
        self.assertEqual((out["talk"], out["no"]), ("space", "enter"))
        self.assertIn("Pulsa el botón de la izquierda", sp.said[1])
        self.assertIn("Ahora el de la derecha", sp.said[3])
        self.assertTrue(any("hablas con el derecho" in s for s in sp.said))

    def test_two_buttons_swap_by_pressing_left(self):
        out = setup.learn_buttons(Speaker().say, scripted("enter", "space", "enter"), pause=lambda s: None)
        self.assertEqual(out["talk_side"], "left")
        self.assertEqual((out["talk"], out["no"]), ("enter", "space"))

    def test_swap_prompt_ignores_other_keys(self):
        out = setup.learn_buttons(Speaker().say, scripted("enter", "space", "x", None), pause=lambda s: None)
        self.assertEqual(out["talk_side"], "right")

    def test_one_button(self):
        sp = Speaker()
        out = setup.learn_buttons(sp.say, scripted("space", None), pause=lambda s: None)
        self.assertEqual((out["talk"], out["no"]), ("space", None))
        self.assertEqual(out["sides"], {"left": "space"})
        self.assertTrue(any("un solo botón" in s for s in sp.said))

    def test_same_key_twice_is_asked_again(self):
        out = setup.learn_buttons(Speaker().say, scripted("space", "space", "enter", None), pause=lambda s: None)
        self.assertEqual(out["sides"], {"left": "space", "right": "enter"})

    def test_nothing_pressed(self):
        sp = Speaker()
        out = setup.learn_buttons(sp.say, scripted(None, None, None), pause=lambda s: None)
        self.assertEqual(out, {})
        self.assertTrue(any("ningún botón" in s for s in sp.said))


class DescribeScreensTests(unittest.TestCase):
    def test_two_monitors_page_on_second(self):
        scr = [{"width": 1920, "height": 1080, "primary": True}, {"width": 1920, "height": 1080, "primary": False}]
        text = setup.describe_screens(scr, "monitor", hardware.page_screen(scr))
        self.assertIn("2 pantallas", text); self.assertIn("la segunda", text)

    def test_one_and_none_and_glasses(self):
        self.assertIn("una pantalla", setup.describe_screens([{"width": 1920, "height": 1080}], "monitor", None))
        self.assertIn("ninguna", setup.describe_screens([], "monitor", None))
        self.assertIn("gafas", setup.describe_screens([{"width": 3840, "height": 1080}], "glasses", None))


class RunWritesConfigTests(unittest.TestCase):
    def test_run_writes_keys_and_keeps_preset_auto(self):
        with tempfile.TemporaryDirectory() as d:
            local = Path(d)
            (local / "config.yaml").write_text("screen_preset: auto\nhelper_name: Marco\n", encoding="utf-8")
            scr = [{"name": "A", "x": 0, "y": 0, "width": 1920, "height": 1080, "primary": True},
                   {"name": "B", "x": 1920, "y": 0, "width": 2560, "height": 1440, "primary": False}]
            with mock.patch.object(setup, "LOCAL_DIR", local), \
                 mock.patch.object(hardware, "HARDWARE_FILE", local / "hardware.json"), \
                 mock.patch.object(hardware, "LOCAL_DIR", local), \
                 mock.patch.object(hardware, "screens", lambda: scr), \
                 mock.patch.object(hardware, "microphones", lambda: [{"index": 0, "name": "mic", "default": True}]):
                sp = Speaker()
                res = setup.run({"screen_display": "auto"}, sp, wait_key=scripted("enter", "space", None))
            cfg = yaml.safe_load((local / "config.yaml").read_text(encoding="utf-8"))
            self.assertEqual(cfg["button_key"], "space")
            self.assertEqual(cfg["button2_key"], "enter")
            self.assertEqual(cfg["screen_preset"], "auto")
            self.assertEqual(cfg["helper_name"], "Marco")
            hw = json.loads((local / "hardware.json").read_text(encoding="utf-8"))
            self.assertEqual(hw["button_sides"], {"left": "enter", "right": "space"})
            self.assertEqual(hw["talk_side"], "right")
            self.assertEqual(hw["page_screen"]["name"], "B")
            self.assertEqual(res["suggested_preset"], "monitor")
            self.assertIn("Tengo dos botones, micrófono, 2 pantallas.", sp.said[-1])


if __name__ == "__main__":
    unittest.main()
