import itertools
import unittest

from onebutton import gestures as g


class GestureTests(unittest.TestCase):
    def test_every_combination_has_an_action(self):
        for btn, ges, st, two in itertools.product((g.TALK, g.NO), (g.SHORT, g.LONG),
                                                   (g.IDLE, g.RECORDING, g.CONFIRMING, g.THINKING), (True, False)):
            self.assertIsInstance(g.interpret((btn, ges), st, two), str)

    def test_two_buttons_talk_button_never_cancels(self):
        for ges, st in itertools.product((g.SHORT, g.LONG), (g.IDLE, g.RECORDING, g.CONFIRMING, g.THINKING)):
            self.assertNotEqual(g.interpret((g.TALK, ges), st, True), g.A_CANCEL, (ges, st))

    def test_two_buttons_no_button_always_means_no(self):
        self.assertEqual(g.interpret((g.NO, g.SHORT), g.RECORDING, True), g.A_CANCEL)
        self.assertEqual(g.interpret((g.NO, g.LONG), g.THINKING, True), g.A_CANCEL)
        self.assertEqual(g.interpret((g.NO, g.SHORT), g.CONFIRMING, True), g.A_NO)
        self.assertEqual(g.interpret((g.NO, g.LONG), g.IDLE, True), g.A_HELP)
        self.assertEqual(g.interpret((g.NO, g.SHORT), g.IDLE, True), g.A_NONE)

    def test_two_buttons_yes_is_a_hold_only_when_asked(self):
        self.assertEqual(g.interpret((g.TALK, g.LONG), g.CONFIRMING, True), g.A_YES)
        self.assertEqual(g.interpret((g.TALK, g.LONG), g.IDLE, True), g.A_REPEAT)
        self.assertEqual(g.interpret((g.TALK, g.SHORT), g.CONFIRMING, True), g.A_TALK)

    def test_one_button_keeps_old_mapping(self):
        self.assertEqual(g.interpret((g.TALK, g.SHORT), g.IDLE, False), g.A_TALK)
        self.assertEqual(g.interpret((g.TALK, g.LONG), g.IDLE, False), g.A_HELP)
        self.assertEqual(g.interpret((g.TALK, g.LONG), g.RECORDING, False), g.A_CANCEL)
        self.assertEqual(g.interpret((g.TALK, g.LONG), g.THINKING, False), g.A_CANCEL)
        self.assertEqual(g.interpret((g.TALK, g.LONG), g.CONFIRMING, False), g.A_CANCEL)
        self.assertEqual(g.interpret((g.TALK, g.SHORT), g.THINKING, False), g.A_REASSURE)

    def test_one_button_ignores_second_button_events(self):
        for ges, st in itertools.product((g.SHORT, g.LONG), (g.IDLE, g.RECORDING, g.CONFIRMING, g.THINKING)):
            self.assertEqual(g.interpret((g.NO, ges), st, False), g.A_NONE)

    def test_help_text_mentions_both_buttons(self):
        self.assertIn("Botón dos", g.help_text(True))
        self.assertNotIn("Botón dos", g.help_text(False))


if __name__ == "__main__":
    unittest.main()
