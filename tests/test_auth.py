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

    def test_login_message_names_helper_and_the_voice_way(self):
        self.assertIn("Marco", auth.login_message("Marco"))
        self.assertIn("inicia sesión", auth.login_message("Marco"))

    def test_login_url(self):
        self.assertEqual(auth.login_url("Browser didn't open? Use: https://claude.ai/oauth/authorize?code=1&x=2."),
                         "https://claude.ai/oauth/authorize?code=1&x=2")
        self.assertIsNone(auth.login_url("Opening browser..."))

    def test_retire_token_comments_out_only_the_live_token(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "credentials.env"
            f.write_text("# header\nCLAUDE_CODE_OAUTH_TOKEN=sk-ant-oat01-old\n# CLAUDE_CODE_OAUTH_TOKEN=\nANTHROPIC_API_KEY=keep\n")
            self.assertTrue(auth.retire_token(f))
            text = f.read_text()
            self.assertIn("# retirado tras iniciar sesión en el navegador: CLAUDE_CODE_OAUTH_TOKEN=sk-ant-oat01-old", text)
            self.assertIn("ANTHROPIC_API_KEY=keep", text)
            self.assertEqual(auth.parse_env(text), {"ANTHROPIC_API_KEY": "keep"})
            self.assertFalse(auth.retire_token(f), "nothing left to retire")
            self.assertFalse(auth.retire_token(Path(d) / "missing.env"))

    def test_status_without_credentials_never_raises(self):
        self.assertFalse(auth.status("definitely-not-a-real-binary", use_credentials=False).get("loggedIn"))


if __name__ == "__main__":
    unittest.main()
