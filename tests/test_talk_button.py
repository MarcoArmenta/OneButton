"""The talk button, as he lives it: a press means "I am talking" or "I am done", and he can hear which.

A press while the computer is speaking used to do a third thing: stop the voice and nothing else.
He then spoke without being recorded, and his next press started a recording he thought he was ending.
"""

import queue
import tempfile
import types
import unittest
from pathlib import Path

import numpy as np

from onebutton import __main__ as loop_mod
from onebutton import lang

from test_english import make_loop

TALK, NO = ("talk", "short"), ("no", "short")


class Presses:
    """The button's queue, with the calls the loop makes on it."""

    def __init__(self):
        self.events = queue.Queue()

    def wait(self, timeout=None):
        try:
            return self.events.get(timeout=min(timeout or 0.01, 0.05))
        except queue.Empty:
            return None

    def poll(self):
        try:
            return self.events.get_nowait()
        except queue.Empty:
            return None

    def clear(self):
        while self.poll() is not None:
            pass


class Voice:
    """Speaks; `pressed` is what he presses in the middle of the next thing it says."""

    def __init__(self, button):
        self.button, self.said, self.pressed = button, [], None

    def say(self, text, until=None, clean=False, show=True):
        self.said.append(text)
        if self.pressed:
            self.button.events.put(self.pressed)
            self.pressed = None
            return not (until and until())
        return True


def loop_with_a_button(ws: Path):
    lp = make_loop(ws)
    lp.button = Presses()
    lp.speaker = Voice(lp.button)
    lp.heard = "hello"
    lp.order = []
    lp.cues = types.SimpleNamespace(start=lambda: lp.order.append("listening sound"),
                                    stop=lambda: lp.order.append("stopped sound"))
    lp.recorder = types.SimpleNamespace(
        rate=16000, record_until=lambda stop: lp.order.append("recording") or np.full(16000, 0.2, dtype=np.float32))
    lp.transcriber = types.SimpleNamespace(transcribe=lambda audio: lp.heard)
    return lp


class TalkButtonTests(unittest.TestCase):
    def setUp(self):
        lang.set_language("en")
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.lp = loop_with_a_button(Path(self.tmp.name))

    def test_a_sound_when_it_starts_listening_and_another_when_it_stops(self):
        lp = self.lp
        self.assertEqual(lp.record_and_transcribe(), "hello")
        self.assertEqual(lp.order, ["listening sound", "recording", "stopped sound"])

    def test_a_press_while_it_speaks_stops_the_voice_and_starts_listening(self):
        lp = self.lp
        lp.speaker.pressed = TALK
        lp.say("A long reply that he does not want to hear to the end.")
        self.assertEqual(lp.action(loop_mod.IDLE, 0.01), loop_mod.A_TALK, "the same press starts the recording")
        self.assertEqual(lp.record_and_transcribe(), "hello")
        self.assertEqual(lp.order[0], "listening sound")
        lp.say("And the next thing is said aloud as usual.")
        self.assertEqual(len(lp.speaker.said), 2)

    def test_nothing_more_is_said_between_that_press_and_his_words(self):
        lp = self.lp
        lp.speaker.pressed = TALK
        lp.say("First reply.")
        lp.say("Second reply, which was waiting.")
        self.assertEqual(lp.speaker.said, ["First reply."], "he asked for the floor: the rest waits on the screen")
        self.assertEqual(lp.action(loop_mod.IDLE, 0.01), loop_mod.A_TALK)

    def test_the_press_survives_the_start_of_a_task(self):
        lp = self.lp
        lp.speaker.pressed = TALK
        lp.say("Noted.")
        lp.forget_presses()                      # what wait_for() does when a task starts
        self.assertEqual(lp.action(loop_mod.THINKING, 0.01), loop_mod.A_REASSURE, "he is still about to speak")

    def test_button_two_only_silences(self):
        lp = self.lp
        lp.speaker.pressed = NO
        lp.say("A long reply.")
        self.assertIsNone(lp.action(loop_mod.IDLE, 0.01), "no recording starts")
        lp.say("The next thing.")
        self.assertEqual(lp.speaker.said, ["A long reply.", "The next thing."])

    def test_pressing_twice_just_to_silence_it_is_not_answered_with_i_heard_nothing(self):
        lp = self.lp
        lp.heard = ""
        lp.speaker.pressed = TALK
        lp.say("A long reply.")
        lp.action(loop_mod.IDLE, 0.01)
        self.assertEqual(lp.record_and_transcribe(), "")
        lp.heard_nothing()
        self.assertEqual(lp.speaker.said, ["A long reply."], "he only wanted quiet")
        self.assertEqual(lp.record_and_transcribe(), "")       # an ordinary empty recording, later
        lp.heard_nothing()
        self.assertIn("I heard nothing", lp.speaker.said[-1])

    def test_if_no_recording_follows_it_speaks_again_after_a_while(self):
        lp = self.lp
        lp.speaker.pressed = TALK
        lp.say("First.")
        lp.button.clear()                         # the press was lost on the way, whatever the reason
        lp.barged_at -= loop_mod.BARGE_SECONDS + 1
        lp.say("Much later.")
        self.assertEqual(lp.speaker.said, ["First.", "Much later."], "it must never stay mute")


if __name__ == "__main__":
    unittest.main()
