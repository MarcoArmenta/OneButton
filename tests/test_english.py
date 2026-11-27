"""English and Spanish side by side, voice scrolling, the buttons kept from applications,
and the writing desk taking dictation instead of orders."""

import sys
import tempfile
import threading
import types
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

from onebutton import __main__ as loop_mod
from onebutton import agent, auth, button, commands, config, gestures, hardware, lang, rules, setup, updater
from onebutton import conversations as cv
from onebutton.desktop_commands import parse
from onebutton.speech import clean_for_speech
from onebutton.stt import Transcriber, pick_language

REPO = Path(__file__).resolve().parent.parent


def tearDownModule():
    lang.set_language("en")


class LanguageTests(unittest.TestCase):
    def setUp(self):
        lang.set_language("en")

    def test_english_is_the_default_and_unknown_codes_fall_back_to_it(self):
        self.assertEqual(config.DEFAULTS["speak_language"], "en")
        self.assertEqual(lang.L("yes", "sí"), "yes")
        self.assertEqual(lang.set_language("es-MX"), "es")
        self.assertEqual(lang.L("yes", "sí"), "sí")
        self.assertEqual(lang.set_language("fr"), "en")
        self.assertEqual(lang.set_language(None), "en")

    def test_the_loop_speaks_english(self):
        self.assertIn("Press the button", loop_mod.banner())
        self.assertIn("Button two", gestures.help_text(True))
        self.assertNotIn("Button two", gestures.help_text(False))
        self.assertIn("scroll down", gestures.help_text(True))
        self.assertIn("sign in", auth.login_message("Marco"))
        self.assertIn("Marco", auth.login_message("Marco"))
        self.assertEqual(agent.reply_from_result({"subtype": "error_max_turns"}, "Marco"), agent.msg("max_turns"))
        self.assertIn("ran out of steps", agent.msg("max_turns"))
        self.assertEqual(hardware.spoken_summary({"buttons": {"talk": "space"}, "microphones": [{}], "screens": [{}]}),
                         "I have one button, a microphone, one screen.")
        self.assertIn("one screen", setup.describe_screens([{"width": 1920, "height": 1080}], "monitor", None))
        self.assertEqual(cv.spoken(2), "two")
        self.assertIn("There is one conversation", cv.Registry().summary())
        self.assertEqual(lang.helper({}), "the person who helps you")
        self.assertEqual(lang.helper({"helper_name": "Marco"}), "Marco")

    def test_a_login_message_is_recognised_in_either_language(self):
        for code in ("en", "es"):
            lang.set_language(code)
            self.assertTrue(auth.says_login_needed(auth.login_message("Marco")))
        self.assertFalse(auth.says_login_needed("Paragraph five."))

    def test_spoken_symbols_follow_the_language(self):
        self.assertIn("less than or equal to", clean_for_speech("a ≤ b", "en"))
        self.assertIn("menor o igual que", clean_for_speech("a ≤ b", "es"))
        self.assertIn("formula on screen", clean_for_speech("so $x^2$ holds", "en"))

    def test_release_notes_are_read_in_one_language(self):
        notes = "**Español.** Arreglos varios.\n\n**English.** Several fixes."
        self.assertEqual(updater.spoken_notes(notes, "en"), "Several fixes.")
        self.assertEqual(updater.spoken_notes(notes, "es"), "Arreglos varios.")
        self.assertEqual(updater.spoken_notes("Just a line.", "en"), "Just a line.")

    def test_rules_name_the_language_the_assistant_answers_in(self):
        en, es = rules.assemble(["scribe"], "en"), rules.assemble(["scribe"], "es")
        self.assertIn("Speak English.", en)
        self.assertIn('"Go ahead?"', en)
        self.assertIn("Speak Spanish.", es)
        self.assertIn('"¿Adelante?"', es)
        self.assertNotIn("{{", en + es)
        with tempfile.TemporaryDirectory() as d:
            self.assertIn("Speak Spanish.", rules.install([], Path(d), speak="es").read_text(encoding="utf-8"))


class ConfigTests(unittest.TestCase):
    def test_an_old_spanish_only_config_still_understands_english(self):
        cfg = config.normalise(dict(config.DEFAULTS, language="es", confirm_words=["adelante"], cancel_words=["no"],
                                    tts_voice="Dalia", whisper_prompt="Carcaj, módulo."))
        self.assertEqual(cfg["speak_language"], "en", "`language` is no longer read")
        self.assertEqual(cfg["listen_languages"], ["en", "es"])
        self.assertEqual(cfg["confirm_words"][0], "adelante")
        self.assertIn("go ahead", cfg["confirm_words"])
        self.assertIn("cancel", cfg["cancel_words"])
        self.assertEqual(cfg["tts_voices"], {"en": "", "es": "Dalia"}, "the old voice was chosen for Spanish")
        self.assertEqual(cfg["whisper_prompts"]["es"], "Carcaj, módulo.")
        self.assertIn("theorem", cfg["whisper_prompts"]["en"])

    def test_language_settings_are_tidied(self):
        cfg = config.normalise(dict(config.DEFAULTS, speak_language="ES", listen_languages="es"))
        self.assertEqual((cfg["speak_language"], cfg["listen_languages"]), ("es", ["es"]))
        self.assertEqual(config.normalise(dict(config.DEFAULTS, speak_language="de"))["speak_language"], "en")

    def test_save_local_merges(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(config, "LOCAL_DIR", Path(d)):
            (Path(d) / "config.yaml").write_text("helper_name: Marco\n", encoding="utf-8")
            config.save_local(speak_language="es")
            self.assertEqual(config._read(Path(d) / "config.yaml"), {"helper_name": "Marco", "speak_language": "es"})


class CommandTests(unittest.TestCase):
    cfg = config.DEFAULTS

    def kind(self, text, **kw):
        return commands.classify(text, self.cfg, **kw).kind

    def test_english_commands(self):
        self.assertEqual(self.kind("update"), commands.UPDATE)
        self.assertEqual(self.kind("Update Claude."), commands.UPDATE_CLAUDE)
        self.assertEqual(self.kind("undo"), commands.UNDO)
        self.assertEqual(self.kind("say that again"), commands.REPEAT)
        self.assertEqual(self.kind("sign in"), commands.LOGIN)
        self.assertEqual(self.kind("set up the buttons"), commands.SETUP)
        self.assertEqual(self.kind("go ahead", awaiting_confirmation=True), commands.CONFIRM)
        self.assertEqual(self.kind("adelante", awaiting_confirmation=True), commands.CONFIRM)
        self.assertEqual(self.kind("yes", awaiting_confirmation=True), commands.CANCEL, "one syllable is not a yes")
        self.assertEqual(self.kind("explain how a user signs in to a web page with a password"), commands.TEXT)

    def test_language_switch(self):
        for said, code in [("speak Spanish", "es"), ("habla en español", "es"), ("Habla en inglés.", "en"),
                           ("speak English please", "en")]:
            cmd = commands.classify(said, self.cfg)
            self.assertEqual((cmd.kind, cmd.text), (commands.LANGUAGE, code), said)
        self.assertEqual(self.kind("how do you say carcaj when you speak english in a seminar"), commands.TEXT)

    def test_dictation_starts_and_stops(self):
        for said in ["nuevo escrito", "Nuevo escrito sobre cohomología de Hochschild", "abre el escrito carcaj",
                     "empecemos un artículo", "new paper about quivers", "open the paper quivers", "dictation", "dictado"]:
            self.assertEqual(commands.dictation(said), "start", said)
        for said in ["fin del dictado", "Fin del dictado.", "end dictation", "stop dictating"]:
            self.assertEqual(commands.dictation(said), "stop", said)
        for said in ["revisión", "baja un poco", "sea Q un carcaj finito", "nuevo párrafo", "review"]:
            self.assertIsNone(commands.dictation(said), said)

    def test_conversations_in_english(self):
        self.assertEqual(cv.parse("new conversation"), {"kind": cv.NEW})
        self.assertEqual(cv.parse("conversation two"), {"kind": cv.SWITCH, "n": 2})
        self.assertEqual(cv.parse("go back to conversation 3"), {"kind": cv.SWITCH, "n": 3})
        self.assertEqual(cv.parse("close this conversation"), {"kind": cv.CLOSE})
        self.assertEqual(cv.parse("what conversations are there"), {"kind": cv.LIST})
        self.assertIsNone(cv.parse("go to chrome"))
        self.assertIsNone(cv.parse("go to the top"))


class ScrollTests(unittest.TestCase):
    def check(self, text, expected):
        self.assertEqual(parse(text), expected, text)

    def test_the_phrases_he_asked_for(self):
        self.check("baja un poco", {"action": "scroll", "dir": "down", "n": 2})
        self.check("baja más", {"action": "scroll", "dir": "down", "n": 5})
        self.check("otra vez", {"action": "scroll_again"})
        self.check("ve hacia arriba", {"action": "scroll", "dir": "up", "n": 5})

    def test_amounts_and_directions(self):
        self.check("baja mucho", {"action": "scroll", "dir": "down", "n": 10})
        self.check("sube un poquito", {"action": "scroll", "dir": "up", "n": 2})
        self.check("más abajo", {"action": "scroll", "dir": "down", "n": 5})
        self.check("para arriba un poco", {"action": "scroll", "dir": "up", "n": 2})
        self.check("baja tres veces", {"action": "scroll", "dir": "down", "n": 3})
        self.check("scroll down", {"action": "scroll", "dir": "down", "n": 5})
        self.check("scroll down a little", {"action": "scroll", "dir": "down", "n": 2})
        self.check("please scroll up a bit", {"action": "scroll", "dir": "up", "n": 2})
        self.check("go down a lot", {"action": "scroll", "dir": "down", "n": 10})
        self.check("go up", {"action": "scroll", "dir": "up", "n": 5})
        self.check("again", {"action": "scroll_again"})
        self.check("un poco más", {"action": "scroll_again"})

    def test_top_bottom_and_pages(self):
        self.check("ve al principio", {"action": "key", "keys": "ctrl+home"})
        self.check("go to the top", {"action": "key", "keys": "ctrl+home"})
        self.check("hasta abajo", {"action": "key", "keys": "ctrl+end"})
        self.check("go to the end of the document", {"action": "key", "keys": "ctrl+end"})
        self.check("next page", {"action": "key", "keys": "pagedown"})
        self.check("página anterior", {"action": "key", "keys": "pageup"})

    def test_scrolling_is_not_mistaken_for_something_else(self):
        self.check("sube el volumen", {"action": "volume", "what": "up"})
        self.check("más bajo", {"action": "volume", "what": "down"})
        self.check("lower the volume", {"action": "volume", "what": "down"})
        self.check("arriba", {"action": "key", "keys": "up"})          # the arrow key, as before
        self.assertIsNone(parse("baja la ventana de la izquierda"))
        self.assertIsNone(parse("sube el archivo al servidor de la universidad"))

    def test_english_desktop_commands(self):
        self.check("go to Chrome", {"action": "focus", "target": "chrome"})
        self.check("open notepad", {"action": "open", "target": "notepad"})
        self.check("click seven", {"action": "click_number", "n": 7})
        self.check("click on the 12", {"action": "click_number", "n": 12})
        self.check("pick twenty one", {"action": "click_number", "n": 21})
        self.check("press enter", {"action": "key", "keys": "enter"})
        self.check("select all", {"action": "key", "keys": "ctrl+a"})
        self.check("show the numbers", {"action": "overlay"})
        self.check("close this window", {"action": "key", "keys": "alt+f4"})
        self.check("type hello there", {"action": "type", "text": "hello there"})
        self.check("what's on the screen", {"action": "describe"})
        self.check("shut down the computer", {"action": "power", "what": "shutdown", "confirm": True})
        for panel in ["go to the board", "show me the desk", "go to the conversation"]:
            self.assertIsNone(parse(panel), panel)
        self.assertIsNone(parse("the end"))
        self.assertIsNone(parse("prove that the quiver has no oriented cycles"))


class FakeKey:
    def __init__(self, vk, flags=0):
        self.vkCode, self.flags = vk, flags


class ButtonSwallowTests(unittest.TestCase):
    """The button is a key. An application must never see it; a key a program types is not the button."""

    def setUp(self):
        self.log = []
        self.filter = button.win32_filter({0x20: "talk", 0x0D: "no"}, lambda n: self.log.append(("down", n)),
                                          lambda n: self.log.append(("up", n)), lambda: self.log.append("swallowed"))

    def test_a_physical_press_is_counted_and_swallowed(self):
        self.assertIs(self.filter(0x0100, FakeKey(0x20)), False)
        self.assertIs(self.filter(0x0101, FakeKey(0x20)), False)
        self.assertEqual(self.log, [("down", "talk"), "swallowed", ("up", "talk"), "swallowed"])

    def test_a_typed_space_reaches_the_application_and_is_not_a_press(self):
        self.assertIs(self.filter(0x0100, FakeKey(0x20, flags=0x10)), False)   # False: not for the listener
        self.assertEqual(self.log, [], "neither counted nor swallowed")

    def test_other_keys_are_left_alone(self):
        self.assertIs(self.filter(0x0100, FakeKey(0x41)), True)
        self.assertEqual(self.log, [])

    def test_macos_swallows_only_the_keyboard_s_own_presses(self):
        intercept = button.darwin_intercept({49}, lambda ev: ev["code"], lambda ev: ev["pid"])
        physical, typed, other = {"code": 49, "pid": 0}, {"code": 49, "pid": 512}, {"code": 0, "pid": 0}
        self.assertIsNone(intercept(None, physical))
        self.assertIs(intercept(None, typed), typed)
        self.assertIs(intercept(None, other), other)


class FakeInfo:
    def __init__(self, probs):
        self.all_language_probs, self.language = probs, probs[0][0]


class TwoLanguageModel:
    """Says Portuguese first for everything, as Whisper does now and then with short Spanish."""
    calls: list = []

    def __init__(self, name, device, compute_type):
        pass

    def transcribe(self, audio, language=None, initial_prompt=None, **kw):
        TwoLanguageModel.calls.append((language, initial_prompt))
        seg = types.SimpleNamespace(text=" baja un poco " if language == "es" else " scroll down ")
        return iter([seg]), FakeInfo([("pt", 0.5), ("es", 0.4), ("en", 0.1)] if audio[0] > 0 else [("en", 0.9), ("es", 0.05)])


class ListenTests(unittest.TestCase):
    def setUp(self):
        TwoLanguageModel.calls = []
        fake = types.ModuleType("faster_whisper")
        fake.WhisperModel = TwoLanguageModel
        patcher = mock.patch.dict(sys.modules, {"faster_whisper": fake})
        patcher.start()
        self.addCleanup(patcher.stop)

    def cfg(self, listen):
        return {"whisper_model": "small", "whisper_device": "cpu", "listen_languages": listen,
                "whisper_prompts": {"en": "theorem", "es": "teorema"}}

    def test_only_the_languages_we_listen_for_are_considered(self):
        self.assertEqual(pick_language([("pt", 0.5), ("es", 0.4), ("en", 0.1)], "pt", ["en", "es"], "en"), "es")
        self.assertEqual(pick_language(None, "es", ["en", "es"], "en"), "es")
        self.assertEqual(pick_language(None, "pt", ["en", "es"], "en"), "en", "nothing usable: keep the last one")

    def test_each_utterance_is_transcribed_in_its_own_language_with_its_own_prompt(self):
        t = Transcriber(self.cfg(["en", "es"]))
        self.assertEqual(t.transcribe(np.full(16000, 0.4, dtype=np.float32)), "baja un poco")
        self.assertEqual(TwoLanguageModel.calls[-1], ("es", "teorema"))
        self.assertEqual(t.transcribe(np.full(16000, -0.4, dtype=np.float32)), "scroll down")
        self.assertEqual(TwoLanguageModel.calls[-1], ("en", "theorem"))
        self.assertEqual(t.last_language, "en")

    def test_one_language_is_not_detected(self):
        t = Transcriber(self.cfg(["es"]))
        t.transcribe(np.full(16000, 0.4, dtype=np.float32))
        self.assertEqual(TwoLanguageModel.calls, [("es", "teorema")])


class FakeSpeaker:
    def __init__(self):
        self.said, self.lang = [], "en"

    def say(self, text, **kw):
        self.said.append(text)
        return True

    def set_language(self, code):
        self.lang = code


def make_loop(ws: Path):
    lp = loop_mod.Loop.__new__(loop_mod.Loop)
    lp.cfg = dict(config.DEFAULTS)
    lp.dry_run = False
    lp.speaker = FakeSpeaker()
    lp.last_reply = ""
    lp.log_path = None
    lp.conversation = ws / "conversacion.md"
    lp.convs = cv.Registry()
    lp.convs_lock = threading.Lock()
    lp.two_buttons = False
    lp.desktop_enabled = True
    lp.panels = ["conversacion", "pizarron", "escritorio"]
    lp.mods = ["scribe"]
    lp.last_scroll = None
    lp.screen_alive_until = float("inf")     # screen_try() says no without talking to a server
    lp.button = None
    lp.agent = None
    lp.sent, lp.did = [], []
    lp.handle_claude = lambda text: lp.sent.append(text)
    lp.desktop = lambda *args: lp.did.append(args) or {}
    return lp


class LoopTests(unittest.TestCase):
    def setUp(self):
        lang.set_language("en")
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.lp = make_loop(Path(self.tmp.name))

    def test_scroll_by_voice_and_again(self):
        lp = self.lp
        lp.handle_text("baja un poco")
        lp.handle_text("otra vez")
        lp.handle_text("again")
        lp.handle_text("ve hacia arriba")
        self.assertEqual(lp.did, [("scroll", "down", "2")] * 3 + [("scroll", "up", "5")])
        self.assertEqual(lp.sent, [], "none of it reached Claude")
        self.assertEqual(lp.speaker.said, [], "scrolling is silent")

    def test_again_with_no_recent_scroll_is_for_claude(self):
        lp = self.lp
        lp.handle_text("otra vez")
        self.assertEqual((lp.did, lp.sent), ([], ["otra vez"]))
        lp.handle_text("scroll down")
        lp.last_scroll = (lp.last_scroll[0], lp.last_scroll[1], lp.last_scroll[2] - loop_mod.SCROLL_AGAIN_WINDOW - 1)
        lp.handle_text("again")
        self.assertEqual(lp.sent, ["otra vez", "again"])

    def test_dictation_is_written_down_not_carried_out(self):
        lp = self.lp
        lp.handle_text("abre el bloc de notas")                       # not dictating: an order to the computer
        self.assertEqual(lp.did, [("open", "bloc de notas")])
        lp.handle_text("nuevo escrito sobre carcajes")
        self.assertTrue(lp.convs.current.dictating)
        for said in ["Abre la demostración con un lema.", "Escribe la sucesión exacta corta.", "Ve a la sección dos.",
                     "revisión"]:
            lp.handle_text(said)
        self.assertEqual(lp.did, [("open", "bloc de notas")], "nothing he dictated touched the computer")
        self.assertEqual(lp.sent[1:], ["Abre la demostración con un lema.", "Escribe la sucesión exacta corta.",
                                       "Ve a la sección dos.", "revisión"], "his words reach the assistant untouched")
        lp.handle_text("baja un poco")                                  # scrolling still works at the desk
        self.assertEqual(lp.did[-1], ("scroll", "down", "2"))
        lp.handle_text("fin del dictado")
        self.assertFalse(lp.convs.current.dictating)
        self.assertEqual(lp.sent[-1], "fin del dictado", "the assistant is told too")
        lp.handle_text("abre el bloc de notas")
        self.assertEqual(lp.did[-1], ("open", "bloc de notas"))

    def test_at_the_desk_undo_and_repeat_are_about_his_text(self):
        lp = self.lp
        self.assertEqual(lp.classify("deshacer").kind, commands.UNDO)
        self.assertEqual(lp.classify("repeat").kind, commands.REPEAT)
        lp.handle_text("nuevo escrito")
        for said in ["deshacer", "Repite.", "update"]:
            cmd = lp.classify(said)
            self.assertEqual((cmd.kind, cmd.text), (commands.TEXT, said), said)
        self.assertEqual(lp.classify("habla en español").kind, commands.LANGUAGE, "still the loop's")
        self.assertEqual(lp.classify("  ").kind, commands.EMPTY)
        lp.handle_text("end dictation")
        self.assertEqual(lp.classify("undo").kind, commands.UNDO)

    def test_dictation_belongs_to_one_conversation(self):
        lp = self.lp
        lp.handle_text("new paper about quivers")
        lp.handle_text("new conversation")
        self.assertFalse(lp.convs.current.dictating)
        lp.handle_text("open notepad")
        self.assertEqual(lp.did, [("open", "notepad")])

    def test_speak_spanish_switches_everything_and_is_remembered(self):
        lp = self.lp
        lp.screen = mock.Mock()
        with mock.patch.object(loop_mod, "save_local") as save, mock.patch("onebutton.rules.install") as install:
            lp.handle_language("es")
            save.assert_called_once_with(speak_language="es")
            install.assert_called_once_with(["scribe"], speak="es")
            self.assertEqual((lang.language(), lp.speaker.lang, lp.cfg["speak_language"]), ("es", "es", "es"))
            self.assertIn("Desde ahora hablo español", lp.speaker.said[-1])
            self.assertEqual(lp.screen.post.call_args[0][0]["lang"], "es")
            lp.handle_language("es")
            self.assertIn("Ya estoy hablando español", lp.speaker.said[-1])
            save.assert_called_once()


class EvidenceTests(unittest.TestCase):
    """What a helper needs in local/session.log to see, afterwards, why something he said did nothing."""

    def setUp(self):
        lang.set_language("en")
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.lp = make_loop(Path(self.tmp.name))
        self.logged = []
        self.lp.log = lambda who, text: self.logged.append((who, text))

    def test_every_recording_is_logged_with_its_length_and_level(self):
        lp = self.lp
        lp.recorder = types.SimpleNamespace(rate=16000, record_until=lambda stop: np.full(32000, 0.25, dtype=np.float32))
        lp.transcriber = types.SimpleNamespace(transcribe=lambda audio: "hello")
        lp.action = lambda state, timeout=None: None
        self.assertEqual(lp.record_and_transcribe(), "hello")
        self.assertEqual(self.logged, [("GRABACIÓN", "2.0 s, nivel 0.25"), ("TÚ", "hello")])

    def test_every_press_is_logged_with_what_it_meant_then(self):
        lp = self.lp
        lp.button = types.SimpleNamespace(wait=lambda timeout=None: ("talk", "short"))
        self.assertEqual(lp.action("idle"), "talk")
        self.assertEqual(lp.action("recording"), "stop")
        lp.button = types.SimpleNamespace(wait=lambda timeout=None: None)
        self.assertIsNone(lp.action("idle", 0.1))
        self.assertEqual(self.logged, [("BOTÓN", "talk short (idle) -> talk"), ("BOTÓN", "talk short (recording) -> stop")])

    def test_a_press_that_cut_the_voice_is_logged_with_what_it_did(self):
        lp = self.lp
        for press, what in [(("no", "short"), "una pulsación cortó la voz; no empezó a grabar"),
                            (("talk", "short"), "una pulsación cortó la voz y empieza a escuchar")]:
            pressed = __import__("queue").Queue()
            pressed.put(press)
            lp.button = types.SimpleNamespace(events=pressed, clear=lambda: None, poll=pressed.get_nowait)
            lp.speaker = types.SimpleNamespace(say=lambda text, until=None, clean=False: False)   # False: it was interrupted
            lp.barged = False
            lp.say("A long reply.")
            self.assertEqual(self.logged.pop(), ("BOTÓN", what))

    def test_an_order_to_the_computer_that_failed_is_logged(self):
        lp = self.lp
        del lp.desktop                                   # the real one, with the tool itself faked
        lp.desktop_py = Path("desktop.py")
        failed = types.SimpleNamespace(stdout='{"error": "FailSafeException: pointer in a corner"}')
        with mock.patch.object(loop_mod.subprocess, "run", return_value=failed):
            res = lp.desktop("scroll", "down", "2")
        self.assertEqual(res["error"], "FailSafeException: pointer in a corner")
        self.assertEqual(self.logged, [("EQUIPO", "error en scroll: FailSafeException: pointer in a corner")])


class DeskRulesTests(unittest.TestCase):
    """The promises the writing desk makes, so a later edit cannot quietly drop one."""

    def setUp(self):
        self.text = (REPO / "modules" / "scribe" / "CLAUDE.md").read_text(encoding="utf-8")

    def test_dictation_is_verbatim(self):
        for promise in ["stenographer first", "character for character", "Do not rephrase", "leave `manuscrito.md` **empty**",
                        "blocks.py append"]:
            self.assertIn(promise, self.text)

    def test_review_changes_nothing_without_a_yes(self):
        for promise in ['"Revisión" / "review"', "one at a time", "Do not change anything yet", "Anything unclear is a no",
                        "never\n   apply one they did not hear"]:
            self.assertIn(promise, self.text)


if __name__ == "__main__":
    unittest.main()
