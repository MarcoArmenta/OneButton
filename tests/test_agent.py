import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from onebutton import agent as agent_mod
from onebutton.config import DEFAULTS


class AgentSettingsTests(unittest.TestCase):
    def test_settings_file_has_allow_list_and_absolute_denies(self):
        with tempfile.TemporaryDirectory() as d:
            local = Path(d) / "local"
            with mock.patch.object(agent_mod, "LOCAL_DIR", local):
                a = agent_mod.Agent(dict(DEFAULTS, claude_bin="definitely-not-a-real-binary"))
                path = Path(a._settings_file())
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
                self.assertEqual(a.ask("hola"), agent_mod.MSG_MISSING)

    def test_command_per_conversation(self):
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(agent_mod, "LOCAL_DIR", Path(d) / "local"):
                a = agent_mod.Agent(dict(DEFAULTS, claude_bin="definitely-not-a-real-binary"))
                first = a.command("hola", "abc-123", resume=False)
                self.assertEqual(first[1:3], ["-p", "hola"])
                self.assertIn("--session-id", first); self.assertIn("abc-123", first)
                self.assertNotIn("--resume", first); self.assertNotIn("--continue", first)
                later = a.command("sigue", "abc-123", resume=True)
                self.assertEqual(later[later.index("--resume") + 1], "abc-123")
                self.assertNotIn("--session-id", later)
                # two conversations never share a flag
                other = a.command("otra cosa", "def-456", resume=False)
                self.assertNotIn("abc-123", other)
                # without a session id the old single-conversation behaviour holds
                self.assertNotIn("--continue", a.command("hola"))
                a.first_turn = False
                self.assertIn("--continue", a.command("hola"))

    def test_cancel_only_kills_that_conversation(self):
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(agent_mod, "LOCAL_DIR", Path(d) / "local"):
                a = agent_mod.Agent(dict(DEFAULTS, claude_bin="definitely-not-a-real-binary"))
                p1, p2 = mock.Mock(), mock.Mock()
                p1.poll.return_value = None; p2.poll.return_value = None
                a._procs = {"s1": p1, "s2": p2}
                a.cancel("s1")
                p1.kill.assert_called_once(); p2.kill.assert_not_called()
                self.assertEqual(a._cancelled, {"s1"})
                a.cancel()
                p2.kill.assert_called_once()


if __name__ == "__main__":
    unittest.main()
