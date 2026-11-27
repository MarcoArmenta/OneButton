"""Choosing a voice by language, so Spanish is never read by an English voice."""

import unittest

from onebutton import voices

WINDOWS_ENGLISH = [  # an English Windows 11 as it comes: no Spanish voice at all
    {"engine": "winrt", "name": "Microsoft David", "lang": "en-US"},
    {"engine": "winrt", "name": "Microsoft Zira", "lang": "en-US"},
    {"engine": "sapi", "name": "Microsoft David Desktop", "lang": "en-US"},
]
WINDOWS_MEXICO = WINDOWS_ENGLISH + [
    {"engine": "winrt", "name": "Microsoft Helena", "lang": "es-ES"},
    {"engine": "winrt", "name": "Microsoft Sabina", "lang": "es-MX"},
    {"engine": "winrt", "name": "Microsoft Raul", "lang": "es-MX"},
    {"engine": "sapi", "name": "Microsoft Sabina Desktop", "lang": "es-MX"},
]
SAY = """Albert              en_US    # Hello! My name is Albert.
Eddy (Spanish (Spain)) es_ES    # ¡Hola! Me llamo Eddy.
Eddy (Spanish (Mexico)) es_MX    # ¡Hola! Me llamo Eddy.
Mónica              es_ES    # ¡Hola! Me llamo Mónica.
Paulina             es_MX    # ¡Hola! Me llamo Paulina.
Samantha            en_US    # Hello! My name is Samantha.
"""


class PickTests(unittest.TestCase):
    def test_no_voice_in_the_language_is_none_never_the_default(self):
        self.assertIsNone(voices.pick(WINDOWS_ENGLISH, "es"))

    def test_mexican_voice_first_and_the_engine_listed_first(self):
        v = voices.pick(WINDOWS_MEXICO, "es")
        self.assertEqual((v["engine"], v["name"]), ("winrt", "Microsoft Sabina"))

    def test_any_spanish_beats_none(self):
        only_spain = WINDOWS_ENGLISH + [{"engine": "sapi", "name": "Microsoft Helena Desktop", "lang": "es-ES"}]
        self.assertEqual(voices.pick(only_spain, "es")["name"], "Microsoft Helena Desktop")

    def test_a_natural_voice_beats_a_classic_one_of_the_same_country(self):
        vs = WINDOWS_MEXICO + [{"engine": "winrt", "name": "Microsoft Dalia (Natural)", "lang": "es-MX"}]
        self.assertEqual(voices.pick(vs, "es")["name"], "Microsoft Dalia (Natural)")

    def test_the_voice_asked_for_by_name(self):
        self.assertEqual(voices.pick(WINDOWS_MEXICO, "es", wanted="raul")["name"], "Microsoft Raul")

    def test_a_name_that_is_not_installed_falls_back_to_the_language(self):
        self.assertEqual(voices.pick(WINDOWS_MEXICO, "es", wanted="Dalia")["name"], "Microsoft Sabina")
        self.assertIsNone(voices.pick(WINDOWS_ENGLISH, "es", wanted="Dalia"))

    def test_english_is_a_language_too(self):
        self.assertEqual(voices.pick(WINDOWS_MEXICO, "en")["name"], "Microsoft David")

    def test_a_full_tag_in_the_config(self):
        self.assertEqual(voices.pick(WINDOWS_MEXICO, "es-ES")["name"], "Microsoft Helena")


class ParseTests(unittest.TestCase):
    def test_macos_say(self):
        vs = voices.parse_say(SAY)
        self.assertIn({"engine": "say", "name": "Eddy (Spanish (Mexico))", "lang": "es-MX"}, vs)
        self.assertIn({"engine": "say", "name": "Mónica", "lang": "es-ES"}, vs)
        self.assertEqual(len(vs), 6)
        self.assertEqual(voices.pick(vs, "es")["name"], "Paulina", "the plain voice, not the novelty ones in brackets")
        self.assertEqual(voices.pick(vs, "en")["name"], "Samantha", "the everyday voice, not the first of the alphabet")

    def test_windows_listing(self):
        text = "winrt|es-MX|Microsoft Sabina\r\nsapi|es-MX|Microsoft Sabina Desktop\r\n\r\nbasura\r\n"
        self.assertEqual(voices.parse_windows(text), [
            {"engine": "winrt", "name": "Microsoft Sabina", "lang": "es-MX"},
            {"engine": "sapi", "name": "Microsoft Sabina Desktop", "lang": "es-MX"}])


class PiperTests(unittest.TestCase):
    def test_voice_for_the_language(self):
        self.assertEqual(voices.piper_voice("es"), "es_MX-claude-high")
        self.assertEqual(voices.piper_voice("es-MX"), "es_MX-claude-high")
        self.assertTrue(voices.piper_voice("en").startswith("en_US"))
        self.assertIsNone(voices.piper_voice("xx"))


if __name__ == "__main__":
    unittest.main()
