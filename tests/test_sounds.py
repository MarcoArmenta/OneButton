"""The two sounds that say whether the computer is listening."""

import unittest

import numpy as np

from onebutton import sounds


def pitch(samples) -> float:
    """The loudest frequency in a stretch of sound."""
    spectrum = np.abs(np.fft.rfft(samples))
    return float(np.fft.rfftfreq(len(samples), 1 / sounds.RATE)[spectrum.argmax()])


class ToneTests(unittest.TestCase):
    def test_both_are_short_soft_and_free_of_clicks(self):
        for notes in (sounds.START, sounds.STOP):
            s = sounds.tone(notes)
            self.assertEqual(s.dtype, np.float32)
            self.assertLess(len(s) / sounds.RATE, 0.35, "short enough not to get in the way of his first word")
            self.assertLessEqual(float(np.abs(s).max()), 0.5)
            self.assertGreater(float(np.abs(s).max()), 0.1)
            self.assertLess(abs(float(s[0])), 0.01)
            self.assertLess(abs(float(s[-1])), 0.01)

    def test_listening_goes_up_in_two_notes_and_stopped_is_one_lower_note(self):
        start, stop = sounds.tone(sounds.START), sounds.tone(sounds.STOP)
        first, second = start[:len(start) // 3], start[-len(start) // 3:]
        self.assertGreater(pitch(second), 1.3 * pitch(first), "it rises")
        self.assertLess(pitch(stop), 0.8 * pitch(first), "the other sound is lower than either note of this one")
        self.assertEqual(len([hz for hz, _ in sounds.START if hz]), 2)
        self.assertEqual(len([hz for hz, _ in sounds.STOP if hz]), 1)


    def test_the_note_sound_is_unlike_the_other_two(self):
        note = sounds.tone(sounds.NOTE)
        self.assertEqual(len([hz for hz, _ in sounds.NOTE if hz]), 3, "three pips: neither two notes nor one")
        self.assertEqual(len({hz for hz, _ in sounds.NOTE if hz}), 1, "all on one pitch: it neither rises nor falls")
        self.assertLess(len(note) / sounds.RATE, 0.5)


class CuesTests(unittest.TestCase):
    def test_start_and_stop_play_their_own_sound(self):
        played = []
        cues = sounds.Cues({}, play=lambda samples, notes: played.append((len(samples), notes)))
        cues.start()
        cues.stop()
        cues.note()
        self.assertEqual([notes for _, notes in played], [sounds.START, sounds.STOP, sounds.NOTE])
        self.assertTrue(all(n > 0 for n, _ in played))

    def test_they_can_be_turned_off(self):
        played = []
        cues = sounds.Cues({"cue_sounds": False}, play=lambda samples, notes: played.append(notes))
        cues.start()
        cues.stop()
        self.assertEqual(played, [])

    def test_a_sound_that_cannot_be_played_never_stops_the_loop(self):
        def broken(samples, notes):
            raise OSError("no sound device")
        cues = sounds.Cues({}, play=broken)
        cues.start()   # must not raise
        cues.stop()


if __name__ == "__main__":
    unittest.main()
