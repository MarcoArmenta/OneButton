"""modules/computadora/desktop.py: the parts that can be checked without a desktop."""

import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("onebutton_desktop_tool", REPO / "modules" / "computadora" / "desktop.py")
desktop = importlib.util.module_from_spec(spec)
spec.loader.exec_module(desktop)


class ScrollPointTests(unittest.TestCase):
    """The wheel goes to the window under the pointer, so the pointer is put on the window in front."""

    def test_middle_of_the_window(self):
        self.assertEqual(desktop.scroll_point((100, 50, 900, 650)), (500, 350))

    def test_a_window_on_a_monitor_to_the_left(self):
        self.assertEqual(desktop.scroll_point((-1920, 0, 0, 1080)), (-960, 540))

    def test_no_window_or_a_sliver_leaves_the_pointer_alone(self):
        self.assertIsNone(desktop.scroll_point(None))
        self.assertIsNone(desktop.scroll_point((0, 0, 10, 10)))


class OwnPythonTests(unittest.TestCase):
    """Claude runs this file with whichever `python` comes first, which usually lacks pyautogui."""

    def test_finds_the_environment_of_the_install(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertIsNone(desktop.own_python(root))
            exe = root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
            exe.parent.mkdir(parents=True)
            exe.write_text("")
            self.assertEqual(desktop.own_python(root), str(exe))

    def test_hands_over_when_a_library_is_missing(self):
        with mock.patch.object(desktop, "NEEDS", ["a_library_nobody_has_installed"]), \
                mock.patch.object(desktop, "own_python", lambda root=None: "/ob/.venv/bin/python"):
            cmd = desktop.hand_over(["scroll", "down", "5"], env={})
            self.assertEqual(cmd[0], "/ob/.venv/bin/python")
            self.assertEqual(cmd[2:], ["scroll", "down", "5"])
            self.assertTrue(cmd[1].endswith("desktop.py"))
            self.assertIsNone(desktop.hand_over(["scroll"], env={"ONEBUTTON_DESKTOP_CHILD": "1"}), "never twice")

    def test_carries_on_when_nothing_is_missing_or_there_is_no_environment(self):
        with mock.patch.object(desktop, "NEEDS", ["json"]):
            self.assertIsNone(desktop.hand_over(["windows"], env={}))
        with mock.patch.object(desktop, "NEEDS", ["a_library_nobody_has_installed"]), \
                mock.patch.object(desktop, "own_python", lambda root=None: None):
            self.assertIsNone(desktop.hand_over(["windows"], env={}))


if __name__ == "__main__":
    unittest.main()
