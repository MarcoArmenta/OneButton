"""Voice login helpers, and the pseudo-terminal against a fake `claude auth login`."""

import sys
import tempfile
import textwrap
import time
import unittest
from pathlib import Path

from onebutton import login

TUI = ("\x1b[2J\x1b[H Welcome to Claude Code v2.1.316\n"
       "\x1b[36mOpening browser to sign in…\x1b[0m\n"
       "Browser didn't open? Use the url below to sign in (c to copy)\n"
       "https://claude.com/cai/oauth/authorize?code=true&client_id=9d1c250a-e61b-44d9-88\n"
       "ed-5944d1962f5e&response_type=code&redirect_uri=https%3A%2F%2Fplatform.claude.co\n"
       "m%2Foauth%2Fcode%2Fcallback&state=abc\n"
       "\x1b]0;title\x07Paste code here if prompted > \r\n")


class HelperTests(unittest.TestCase):
    def test_strip_ansi(self):
        self.assertEqual(login.strip_ansi("\x1b[31mhola\x1b[0m \x1b]0;t\x07x\r"), "hola x")

    def test_url_is_rejoined_across_wrapped_lines(self):
        self.assertEqual(login.extract_url(TUI),
                         "https://claude.com/cai/oauth/authorize?code=true&client_id=9d1c250a-e61b-44d9-88ed-5944d1962f5e"
                         "&response_type=code&redirect_uri=https%3A%2F%2Fplatform.claude.com%2Foauth%2Fcode%2Fcallback&state=abc")
        self.assertIsNone(login.extract_url("nothing here"))

    def test_code_and_prompt(self):
        code = "AbCdEfGhIjKlMnOpQrStUvWxYz0123456789_-abcdef#StateStateState12"
        self.assertEqual(login.extract_code(f"Your code: {code} (copy)"), code)
        self.assertIsNone(login.extract_code("pulsa el siete"))
        self.assertIsNone(login.extract_code("short#short"))
        self.assertTrue(login.waiting_for_code(TUI))
        self.assertFalse(login.waiting_for_code("Opening browser"))
        self.assertTrue(login.looks_successful("✓ Logged in as someone"))

    def test_clean_env_drops_credentials(self):
        import os
        from unittest import mock
        with mock.patch.dict(os.environ, {"CLAUDE_CODE_OAUTH_TOKEN": "x", "ANTHROPIC_API_KEY": "y", "HOME": "/h"}):
            env = login.clean_env()
        self.assertNotIn("CLAUDE_CODE_OAUTH_TOKEN", env); self.assertNotIn("ANTHROPIC_API_KEY", env)
        self.assertEqual(env["HOME"], "/h"); self.assertIn("TERM", env)

    def test_clipboard_never_raises(self):
        self.assertIsInstance(login.read_clipboard(), str)


@unittest.skipIf(sys.platform == "win32", "POSIX pty; Windows uses pywinpty")
class TerminalProcessTests(unittest.TestCase):
    def test_prompt_code_and_exit(self):
        with tempfile.TemporaryDirectory() as d:
            script = Path(d) / "fake_login.py"
            script.write_text(textwrap.dedent('''
                import sys, os
                assert os.isatty(sys.stdin.fileno()), "needs a tty"
                print("\\x1b[36mOpening browser to sign in\\u2026\\x1b[0m")
                print("Paste code here if prompted > ", end="", flush=True)
                code = sys.stdin.readline().strip()
                print("\\nLogged in with " + code[:5])
            '''), encoding="utf-8")
            term = login.TerminalProcess([sys.executable, str(script)])
            self.assertTrue(term.start(), term.error)
            end = time.monotonic() + 5
            while time.monotonic() < end and not login.waiting_for_code(term.snapshot()):
                time.sleep(0.05)
            self.assertTrue(login.waiting_for_code(term.snapshot()), term.snapshot())
            self.assertNotIn("\x1b", term.snapshot(), "output is stored clean")
            term.send_line("ABCDEFGHIJKLMNOPQRSTUVWXYZ#state1234")
            end = time.monotonic() + 5
            while time.monotonic() < end and term.alive():
                time.sleep(0.05)
            self.assertFalse(term.alive())
            self.assertIn("Logged in with ABCDE", term.snapshot())
            term.kill()

    def test_missing_binary(self):
        term = login.TerminalProcess(["/definitely/not/a/binary"])
        self.assertFalse(term.start())
        self.assertFalse(term.alive())


if __name__ == "__main__":
    unittest.main()
