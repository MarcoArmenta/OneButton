import tempfile
import unittest
from pathlib import Path
from unittest import mock

from onebutton import auth


class AuthTests(unittest.TestCase):
    def test_parse_env_keeps_only_accepted_keys(self):
        text = '''
        # comment
        export CLAUDE_CODE_OAUTH_TOKEN="sk-ant-oat01-abc"
        ANTHROPIC_API_KEY=''
        OTHER=1
        junk line
        '''
        self.assertEqual(auth.parse_env(text), {"CLAUDE_CODE_OAUTH_TOKEN": "sk-ant-oat01-abc"})

    def test_subprocess_env_merges_file_over_base(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "credentials.env"
            f.write_text("ANTHROPIC_API_KEY=sk-test\n")
            with mock.patch.object(auth, "CREDENTIALS_FILE", f):
                env = auth.subprocess_env({"PATH": "/bin"})
        self.assertEqual(env, {"PATH": "/bin", "ANTHROPIC_API_KEY": "sk-test"})

    def test_missing_file_is_empty(self):
        with mock.patch.object(auth, "CREDENTIALS_FILE", Path("/nonexistent/credentials.env")):
            self.assertEqual(auth.credentials_env(), {})

    def test_status_never_raises_on_missing_binary(self):
        st = auth.status("definitely-not-a-real-binary")
        self.assertFalse(st.get("loggedIn"))

    def test_login_message_names_helper(self):
        self.assertIn("Marco", auth.login_message("Marco"))


if __name__ == "__main__":
    unittest.main()
