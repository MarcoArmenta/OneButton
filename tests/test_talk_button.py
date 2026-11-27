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


HOLD5 = ("talk", "very_long")


class NoteForTheMaintainerTests(unittest.TestCase):
    """Holding the button five seconds: a different sound, and what he says next is a note for Marco."""

    def setUp(self):
        lang.set_language("en")
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.lp = lp = loop_with_a_button(Path(self.tmp.name))
        lp.cues.note = lambda: lp.order.append("note sound")
        lp.heard = "the page did not scroll when I said baja"
        self.delivered = []
        self.outcome = {"saved": Path("x.md"), "url": "https://github.com/o/r/issues/7", "error": None, "sent": 1}
        lp.deliver_note = lambda **kw: self.delivered.append(kw) or self.outcome

    def hold_then_talk(self):
        lp = self.lp
        lp.button.events.put(HOLD5)
        lp.action(loop_mod.IDLE, 0.01)                    # the loop reads the five-second hold
        self.assertTrue(lp.note_requested)
        lp.speaker.pressed = TALK                         # he presses to say it as soon as he has heard enough
        lp.take_note()

    def test_the_whole_gesture(self):
        lp = self.lp
        self.hold_then_talk()
        self.assertEqual(lp.order[:3], ["note sound", "listening sound", "recording"])
        self.assertIn("A note for Marco", lp.speaker.said[0])
        self.assertEqual(self.delivered[0]["note"], "the page did not scroll when I said baja")
        self.assertEqual(self.delivered[0]["repo_url"], lp.cfg["repo_url"])
        self.assertEqual(set(self.delivered[0]["info"]) >= {"when", "version", "system", "speaks", "buttons"}, True)
        self.assertEqual(lp.speaker.said[-1], "Sent to Marco.")
        self.assertFalse(lp.note_requested)

    def test_when_it_cannot_be_sent_it_is_kept_and_he_is_told(self):
        self.outcome = {"saved": Path("x.md"), "url": None, "error": "no key", "sent": 0}
        self.hold_then_talk()
        self.assertEqual(self.lp.speaker.said[-1], "I saved the note. Marco will get it as soon as it can be sent.")

    def test_saying_cancel_drops_it(self):
        self.lp.heard = "Cancel."
        self.hold_then_talk()
        self.assertEqual(self.delivered, [])
        self.assertEqual(self.lp.speaker.said[-1], "All right, no note.")

    def test_saying_nothing_drops_it(self):
        self.lp.heard = ""
        self.hold_then_talk()
        self.assertEqual(self.delivered, [])

    def test_it_uses_the_name_in_the_config(self):
        self.lp.cfg["maintainer_name"] = "Ana"
        self.hold_then_talk()
        self.assertIn("A note for Ana", self.lp.speaker.said[0])
        self.assertEqual(self.lp.speaker.said[-1], "Sent to Ana.")

    def test_five_seconds_during_a_recording_ends_it_and_the_note_comes_next(self):
        lp = self.lp
        lp.button.events.put(HOLD5)
        self.assertEqual(lp.action(loop_mod.RECORDING, 0.01), loop_mod.A_CANCEL)
        self.assertTrue(lp.note_requested)

    def test_the_hold_is_not_lost_when_it_arrives_while_the_computer_is_speaking(self):
        lp = self.lp
        lp.speaker.pressed = HOLD5                      # held through the spoken help, which starts at two seconds
        lp.say("Press once to talk and once more to finish.")
        self.assertTrue(lp.note_requested)
        self.assertFalse(lp.barged, "it is not a press to talk")

    def test_nor_when_it_was_waiting_before_the_computer_spoke(self):
        lp = self.lp
        lp.button.events.put(HOLD5)
        lp.say("Something.")                            # say() drops presses made before it starts
        self.assertTrue(lp.note_requested)


if __name__ == "__main__":
    unittest.main()
