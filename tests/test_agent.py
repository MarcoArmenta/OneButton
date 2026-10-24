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


if __name__ == "__main__":
    unittest.main()
