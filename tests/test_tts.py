"""Which engine and voice speak: always one of the configured language when there is any way to have one."""

import contextlib
import io
import unittest

from onebutton.tts import Speaker

ENGLISH_WINDOWS = [
    {"engine": "winrt", "name": "Microsoft David", "lang": "en-US"},
    {"engine": "sapi", "name": "Microsoft David Desktop", "lang": "en-US"},
]
MEXICAN_WINDOWS = ENGLISH_WINDOWS + [
    {"engine": "winrt", "name": "Microsoft Sabina", "lang": "es-MX"},
    {"engine": "sapi", "name": "Microsoft Sabina Desktop", "lang": "es-MX"},
]
MAC = [{"engine": "say", "name": "Samantha", "lang": "en-US"}, {"engine": "say", "name": "Paulina", "lang": "es-MX"}]


class FakeSpeaker(Speaker):
    """A Speaker on a pretend computer: these engines exist, these voices are installed, Piper works or not."""

    def __init__(self, cfg=None, engines=("winrt", "sapi"), installed=(), piper=False, broken=()):
        super().__init__(dict({"language": "es"}, **(cfg or {})))
        self.engines, self.installed, self.piper, self.broken = engines, list(installed), piper, set(broken)
        self.spoke = []

    def _has(self, engine):
        return engine in self.engines

    def _windows_voices(self):
        return [v for v in self.installed if v["engine"] in ("winrt", "sapi")]

    def _say_voices(self):
        return [v for v in self.installed if v["engine"] == "say"]

    def _piper_ready(self):
        return self.piper

    def _speak(self, spoken, until):
        if self.engine in self.broken:
            return None
        self.spoke.append((self.engine, self.voice))
        return True

    def quiet_say(self, text):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.say(text, show=False)
        return err.getvalue()


class ChoosingTests(unittest.TestCase):
    def test_a_spanish_windows_uses_its_own_spanish_voice(self):
        sp = FakeSpeaker(installed=MEXICAN_WINDOWS, piper=True)
        sp.quiet_say("hola")
        self.assertEqual(sp.spoke, [("winrt", "Microsoft Sabina")])

    def test_an_english_windows_speaks_with_piper_not_with_the_english_voice(self):
        sp = FakeSpeaker(installed=ENGLISH_WINDOWS, piper=True)
        warned = sp.quiet_say("hola")
        self.assertEqual(sp.engine, "piper")
        self.assertNotIn("AVISO", warned)

    def test_with_no_spanish_voice_at_all_it_still_speaks_and_says_why_it_sounds_wrong(self):
        sp = FakeSpeaker(installed=ENGLISH_WINDOWS, piper=False)
        warned = sp.quiet_say("hola")
        self.assertEqual(sp.spoke, [("winrt", "")])
        self.assertIn("ninguna voz para el idioma 'es'", warned)

    def test_a_voice_named_in_the_config_that_is_not_installed_does_not_mean_english(self):
        sp = FakeSpeaker({"tts_voice": "Dalia"}, installed=MEXICAN_WINDOWS)
        sp.quiet_say("hola")
        self.assertEqual(sp.spoke, [("winrt", "Microsoft Sabina")])

    def test_a_classic_voice_named_in_the_config_is_found_in_its_engine(self):
        sp = FakeSpeaker({"tts_voice": "Sabina Desktop"}, installed=MEXICAN_WINDOWS)
        sp.quiet_say("hola")
        self.assertEqual(sp.spoke, [("sapi", "Microsoft Sabina Desktop")])

    def test_mac_picks_the_spanish_voice_instead_of_the_system_one(self):
        sp = FakeSpeaker(engines=("say",), installed=MAC)
        sp.quiet_say("hola")
        self.assertEqual(sp.spoke, [("say", "Paulina")])

    def test_an_engine_asked_for_by_name_is_kept(self):
        sp = FakeSpeaker({"tts": "sapi"}, installed=MEXICAN_WINDOWS, piper=True)
        sp.quiet_say("hola")
        self.assertEqual(sp.spoke, [("sapi", "Microsoft Sabina Desktop")])

    def test_piper_asked_for_but_missing_falls_back_to_a_spanish_system_voice(self):
        sp = FakeSpeaker({"tts": "piper"}, installed=MEXICAN_WINDOWS, piper=False)
        sp.quiet_say("hola")
        self.assertEqual(sp.spoke, [("winrt", "Microsoft Sabina")])

    def test_espeak_and_none_are_left_alone(self):
        sp = FakeSpeaker({"tts": "none"}, installed=MEXICAN_WINDOWS, piper=True)
        sp.quiet_say("hola")
        self.assertEqual(sp.engine, "none")


class FailingTests(unittest.TestCase):
    def test_modern_windows_voice_breaks_then_the_classic_spanish_one_speaks(self):
        sp = FakeSpeaker(installed=MEXICAN_WINDOWS, broken={"winrt"})
        sp.quiet_say("hola")
        self.assertEqual(sp.spoke, [("sapi", "Microsoft Sabina Desktop")])
        sp.quiet_say("otra vez")
        self.assertEqual(sp.spoke[-1], ("sapi", "Microsoft Sabina Desktop"), "and it stays there")

    def test_piper_breaks_on_an_english_windows_then_the_system_voice_with_a_warning(self):
        sp = FakeSpeaker(installed=ENGLISH_WINDOWS, piper=True, broken={"piper"})
        warned = sp.quiet_say("hola")
        self.assertEqual(sp.spoke, [("winrt", "")])
        self.assertIn("AVISO", warned)

    def test_everything_broken_gives_up_quietly(self):
        sp = FakeSpeaker(installed=MEXICAN_WINDOWS, piper=True, broken={"winrt", "sapi", "piper"})
        sp.quiet_say("hola")
        self.assertEqual(sp.spoke, [])


if __name__ == "__main__":
    unittest.main()
