"""The loop with several conversations: a long turn keeps working in the background
while the user opens another one, and is announced once when it finishes."""

import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

from onebutton import __main__ as loop_mod
from onebutton import conversations as cv
from onebutton.config import DEFAULTS
from onebutton.gestures import SHORT, TALK


class FakeSpeaker:
    def __init__(self):
        self.said = []

    def say(self, text, **kw):
        self.said.append(text)
        return True


class FakeButton:
    """Scripted events for wait(); None once the script runs out."""
    def __init__(self, events):
        self.events = list(events)

    def wait(self, timeout=None):
        if self.events:
            return self.events.pop(0)
        time.sleep(min(timeout or 0.05, 0.05))
        return None

    def clear(self):
        pass


class FakeAgent:
    """ask() blocks until release() is called; records which session each turn used."""
    def __init__(self):
        self.gate = threading.Event()
        self.calls = []
        self.cancelled = []

    def ask(self, text, session_id=None, resume=False):
        self.calls.append((text, session_id, resume))
        self.gate.wait(5)
        return f"respuesta a {text}"

    def cancel(self, session_id=None):
        self.cancelled.append(session_id)
        self.gate.set()


def make_loop(ws: Path, button_events, heard):
    lp = loop_mod.Loop.__new__(loop_mod.Loop)
    lp.cfg = dict(DEFAULTS)
    lp.dry_run = False
    lp.speaker = FakeSpeaker()
    lp.last_reply = ""
    lp.progress_interval = 0
    lp.log_path = None
    lp.conversation = ws / "conversacion.md"
    lp.convs = cv.Registry()
    lp.convs_lock = threading.Lock()
    lp.two_buttons = False
    lp.desktop_enabled = False
    lp.screen_alive_until = float("inf")  # screen_try() says no without talking to a server
    lp.button = FakeButton(button_events)
    lp.agent = FakeAgent()
    script = list(heard)
    lp.record_and_transcribe = lambda: script.pop(0) if script else None
    return lp


class LoopConversationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self.tmp.name)
        self.patch = mock.patch.object(loop_mod, "WORKSPACE_DIR", self.ws)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def test_long_task_keeps_working_while_he_opens_another_conversation(self):
        # during the first turn he presses talk and says "nueva conversación"
        lp = make_loop(self.ws, [(TALK, SHORT)], ["nueva conversación"])
        lp.handle_text("escribe la demostración completa")
        c1, c2 = lp.convs.items
        self.assertIs(lp.convs.current, c2)
        self.assertEqual(c1.state, cv.WORKING, "the first turn is still running in the background")
        self.assertEqual(c1.title, "escribe la demostración completa")
        self.assertTrue(any("Conversación dos. Te escucho." in s for s in lp.speaker.said))
        self.assertEqual(lp.agent.calls[0][1], c1.session_id)
        self.assertFalse(lp.agent.calls[0][2], "first turn of a conversation starts the session")
        self.assertEqual(lp.conversation.read_text(encoding="utf-8"), "", "the screen shows the new, empty conversation")

        # the second conversation gets its own session and answers right away
        lp.agent.gate.set()
        lp.handle_text("qué hora es")
        time.sleep(0.3)
        self.assertEqual(lp.agent.calls[1][1], c2.session_id)
        self.assertIn("respuesta a qué hora es", lp.speaker.said[-1])
        self.assertIn("respuesta a qué hora es", lp.conversation.read_text(encoding="utf-8"))
        self.assertIn("respuesta a escribe", (self.ws / c1.file).read_text(encoding="utf-8"))
        self.assertEqual(c1.state, cv.DONE)

        # the finished background conversation is announced once, and read when he switches to it
        lp.announce_finished(); lp.announce_finished()
        self.assertEqual(sum("Terminó la conversación uno" in s for s in lp.speaker.said), 1)
        lp.handle_text("conversación uno")
        self.assertIs(lp.convs.current, c1)
        self.assertEqual(c1.state, cv.IDLE)
        self.assertIn("respuesta a escribe la demostración completa", lp.speaker.said[-1])
        self.assertIn("respuesta a escribe", lp.conversation.read_text(encoding="utf-8"))
        self.assertNotIn("qué hora es", lp.conversation.read_text(encoding="utf-8"))

        # a later turn in conversation one resumes its session
        lp.handle_text("sigue")
        self.assertEqual(lp.agent.calls[-1][1:], (c1.session_id, True))

    def test_talking_while_it_works_without_a_command_is_explained(self):
        lp = make_loop(self.ws, [(TALK, SHORT), (TALK, SHORT)], ["y también suma dos más dos", "cancela"])
        lp.handle_text("tarea larga")
        self.assertTrue(any("sigue trabajando" in s for s in lp.speaker.said))
        self.assertEqual(lp.agent.cancelled, [lp.convs.current.session_id], "'cancela' stops this conversation only")

    def test_list_close_and_unknown(self):
        lp = make_loop(self.ws, [], [])
        lp.agent.gate.set()
        lp.handle_text("qué conversaciones hay")
        self.assertIn("una sola conversación", lp.speaker.said[-1])
        lp.handle_text("nueva conversación"); lp.handle_text("nueva conversación")
        lp.handle_text("conversación nueve")
        self.assertIn("No hay conversación nueve", lp.speaker.said[-1])
        lp.handle_text("cierra esta conversación")
        self.assertEqual([c.n for c in lp.convs.items], [1, 2])
        self.assertIn("Cerrada la conversación tres. Estás en la dos.", lp.speaker.said[-1])
        lp.handle_text("cierra la conversación uno")
        self.assertEqual([c.n for c in lp.convs.items], [2])


if __name__ == "__main__":
    unittest.main()
