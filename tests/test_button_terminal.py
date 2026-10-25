"""Burst detection in terminal mode, driven with fake input instead of a tty."""

import threading
import time
import unittest

from onebutton import button as b


class FakeInput:
    def __init__(self):
        self.buf = ""
        self.lock = threading.Lock()

    def feed(self, s):
        with self.lock:
            self.buf += s

    def available(self):
        with self.lock:
            return bool(self.buf)

    def read(self):
        with self.lock:
            s, self.buf = self.buf, ""
            return s

    def swallow(self, seconds):
        time.sleep(seconds)
        self.read()


class TerminalBurstTests(unittest.TestCase):
    def setUp(self):
        self.btn = b.Button.__new__(b.Button)
        import queue
        self.btn.events = queue.Queue()
        self.btn.keys = {"talk": "space", "no": "enter"}
        self.inp = FakeInput()
        threading.Thread(target=self.btn._burst_reader,
                         args=(self.btn._char_map(), self.inp.available, self.inp.read, self.inp.swallow),
                         daemon=True).start()

    def test_single_space_is_short_talk(self):
        self.inp.feed(" ")
        self.assertEqual(self.btn.wait(2), ("talk", "short"))

    def test_enter_is_short_no(self):
        self.inp.feed("\r")
        self.assertEqual(self.btn.wait(2), ("no", "short"))

    def test_burst_is_long(self):
        self.inp.feed(" " * 8)
        self.assertEqual(self.btn.wait(2), ("talk", "long"))
        self.assertIsNone(self.btn.wait(1.2))  # swallowed, no trailing short

    def test_other_keys_ignored(self):
        self.inp.feed("abc\n")
        self.assertEqual(self.btn.wait(2), ("no", "short"))
        self.assertIsNone(self.btn.wait(0.5))


if __name__ == "__main__":
    unittest.main()
