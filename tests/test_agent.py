import json
import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

from onebutton import agent as agent_mod
from onebutton.config import DEFAULTS

FAKE = Path(__file__).resolve().parent / "fake_claude.py"


class AgentSettingsTests(unittest.TestCase):
    def test_settings_file_has_allow_list_and_absolute_denies(self):
        with tempfile.TemporaryDirectory() as d:
            local = Path(d) / "local"
            with mock.patch.object(agent_mod, "LOCAL_DIR", local):
                a = agent_mod.Agent(dict(DEFAULTS, claude_bin="definitely-not-a-real-binary"))
                path = Path(a.settings_file())
                self.assertEqual(path.parent, local)
                data = json.loads(path.read_text(encoding="utf-8"))
                allow, deny = data["permissions"]["allow"], data["permissions"]["deny"]
                self.assertIn("Read", allow)
                self.assertTrue(any("sudo" in r for r in deny))
                self.assertTrue(any(r.startswith("Read(//") and "local" in r for r in deny))
                self.assertTrue(all("\\" not in r for r in deny), "deny paths must be POSIX-style")

    def test_missing_binary_is_a_spoken_message_not_a_crash(self):
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(agent_mod, "LOCAL_DIR", Path(d) / "local"), \
                 mock.patch.object(agent_mod, "WORKSPACE_DIR", Path(d)):
                a = agent_mod.Agent(dict(DEFAULTS, claude_bin="definitely-not-a-real-binary"))
                got = []
                a.send("s1", "hola", got.append)
                self.assertEqual(got, [agent_mod.MSG_MISSING])


class PureTests(unittest.TestCase):
    def test_user_message_line(self):
        m = agent_mod.user_message("hola", "next")
        self.assertEqual(m["type"], "user"); self.assertEqual(m["message"], {"role": "user", "content": "hola"})
        self.assertIsNone(m["parent_tool_use_id"]); self.assertEqual(m["priority"], "next")
        self.assertNotEqual(m["uuid"], agent_mod.user_message("hola")["uuid"])

    def test_reply_from_result(self):
        r = agent_mod.reply_from_result
        self.assertEqual(r({"subtype": "success", "result": " listo "}, "Marco"), "listo")
        self.assertEqual(r({"subtype": "error_max_turns", "result": None}, "Marco"), agent_mod.MSG_MAX_TURNS)
        self.assertIn("Marco", r({"subtype": "error_during_execution", "errors": ["Not logged in: run /login"]}, "Marco"))
        self.assertIn("devolvió un error", r({"subtype": "error_during_execution", "errors": ["boom"]}, "Marco"))
        self.assertEqual(r({"subtype": "success", "is_error": True, "result": "no puedo"}, "Marco"), "no puedo")


def wait_until(pred, seconds=5.0):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if pred():
            return True
        time.sleep(0.02)
    return False


class SessionTests(unittest.TestCase):
    """The real Session against tests/fake_claude.py standing in for Claude Code."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = Path(self.tmp.name)
        self.log = d / "argv.log"
        self.env = mock.patch.dict(os.environ, {"FAKE_CLAUDE_LOG": str(self.log), "FAKE_CLAUDE_DELAY": "0"})
        self.env.start()
        self.patches = [mock.patch.object(agent_mod, "LOCAL_DIR", d / "local"),
                        mock.patch.object(agent_mod, "WORKSPACE_DIR", d)]
        for p in self.patches:
            p.start()
        # run the fake through the current interpreter: Popen([bin, ...]) -> we point bin at a wrapper
        self.wrapper = d / ("claude.cmd" if os.name == "nt" else "claude")
        if os.name == "nt":
            self.wrapper.write_text(f'@echo off\r\n"{sys.executable}" "{FAKE}" %*\r\n', encoding="utf-8")
        else:
            self.wrapper.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{FAKE}" "$@"\n', encoding="utf-8")
            self.wrapper.chmod(0o755)
        self.agent = agent_mod.Agent(dict(DEFAULTS, claude_bin=str(self.wrapper), claude_timeout=5))

    def tearDown(self):
        self.agent.shutdown()
        for p in self.patches:
            p.stop()
        self.env.stop()
        self.tmp.cleanup()

    def argv_log(self):
        return [json.loads(l) for l in self.log.read_text(encoding="utf-8").splitlines()] if self.log.exists() else []

    def test_two_messages_two_replies_in_order_one_process(self):
        got = []
        self.agent.send("sid-1", "uno", got.append)
        self.agent.send("sid-1", "dos", got.append)
        self.assertTrue(wait_until(lambda: len(got) == 2))
        self.assertEqual(got, ["eco: uno", "eco: dos"])
        argv = self.argv_log()
        self.assertEqual(len(argv), 1, "one long-lived process, not one per turn")
        self.assertIn("--session-id", argv[0]); self.assertIn("sid-1", argv[0])
        self.assertIn("--input-format", argv[0]); self.assertIn("stream-json", argv[0]); self.assertIn("--verbose", argv[0])
        self.assertFalse(self.agent.working("sid-1"))

    def test_conversations_are_separate_processes(self):
        a, b = [], []
        self.agent.send("sid-a", "hola", a.append)
        self.agent.send("sid-b", "hola", b.append)
        self.assertTrue(wait_until(lambda: a and b))
        ids = [v[v.index("--session-id") + 1] for v in self.argv_log()]
        self.assertEqual(sorted(ids), ["sid-a", "sid-b"])

    def test_cancel_kills_and_the_next_message_resumes(self):
        with mock.patch.dict(os.environ, {"FAKE_CLAUDE_DELAY": "3"}):
            got = []
            self.agent.send("sid-1", "lento", got.append)
            self.assertTrue(wait_until(lambda: self.agent.sessions["sid-1"].created, 3))
            self.assertTrue(self.agent.working("sid-1"))
            self.agent.cancel("sid-1")
            time.sleep(0.3)
            self.assertEqual(got, [], "a cancelled turn is silent; the loop says 'Cancelado'")
            self.assertFalse(self.agent.working("sid-1"))
        self.agent.send("sid-1", "otra", got.append)
        self.assertTrue(wait_until(lambda: got == ["eco: otra"]))
        argv = self.argv_log()
        self.assertEqual(len(argv), 2)
        self.assertIn("--resume", argv[1]); self.assertEqual(argv[1][argv[1].index("--resume") + 1], "sid-1")
        self.assertNotIn("--session-id", argv[1])

    def test_crash_mid_turn_is_reported_once(self):
        got = []
        self.agent.send("sid-1", "crash", got.append)
        self.assertTrue(wait_until(lambda: got == [agent_mod.MSG_CRASHED]))
        self.assertFalse(self.agent.working("sid-1"))

    def test_timeout_is_reported(self):
        self.agent.timeout = 1
        with mock.patch.dict(os.environ, {"FAKE_CLAUDE_DELAY": "10"}):
            got = []
            self.agent.send("sid-1", "eterno", got.append)
            self.assertTrue(wait_until(lambda: got == [agent_mod.MSG_TIMEOUT], 6))

    def test_idle_close_then_resume(self):
        self.agent.idle_close = 1
        got = []
        self.agent.send("sid-1", "uno", got.append)
        self.assertTrue(wait_until(lambda: got == ["eco: uno"]))
        self.assertTrue(wait_until(lambda: not self.agent.sessions["sid-1"].alive(), 5), "idle process closed")
        self.agent.send("sid-1", "dos", got.append)
        self.assertTrue(wait_until(lambda: got == ["eco: uno", "eco: dos"]))
        self.assertIn("--resume", self.argv_log()[1])


if __name__ == "__main__":
    unittest.main()
