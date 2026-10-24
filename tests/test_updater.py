"""Updater tests against a throwaway origin repo with real SSH-signed tags.

Skipped when ssh-keygen is unavailable or git lacks SSH signing support.
"""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from onebutton import updater


def run(*args, cwd, env=None, check=True):
    return subprocess.run(args, cwd=cwd, env=env, check=check, capture_output=True, text=True)


@unittest.skipUnless(shutil.which("ssh-keygen") and shutil.which("git"), "needs git and ssh-keygen")
class UpdaterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.good_key = self.tmp / "good"
        self.bad_key = self.tmp / "bad"
        for k in (self.good_key, self.bad_key):
            run("ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(k), cwd=self.tmp)
        self.origin = self.tmp / "origin"
        self.origin.mkdir()
        self.env = dict(os.environ, GIT_CONFIG_GLOBAL="/dev/null", GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@x", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@x")
        g = lambda *a, **kw: run("git", *a, cwd=self.origin, env=self.env, **kw)
        g("init", "-q", "-b", "main")
        g("config", "gpg.format", "ssh")
        g("config", "user.signingkey", str(self.good_key) + ".pub")
        self._commit("## v0.1.0\n\n**Español.** Primera.\n\n## older\n\nx\n", "v0.1.0", self.good_key)
        self._commit("## v0.2.0\n\n**Español.** Segunda, con arreglos.\n\n## v0.1.0\n\n**Español.** Primera.\n", "v0.2.0", self.good_key)
        self._commit("## v0.3.0\n\nevil\n", "v0.3.0", self.bad_key)

        self.clone = self.tmp / "clone"
        run("git", "clone", "-q", str(self.origin), str(self.clone), cwd=self.tmp, env=self.env)
        self.local = self.clone / "local"
        self.local.mkdir()
        pub = (self.good_key.with_suffix(".pub")).read_text().strip()
        (self.local / "allowed_signers").write_text(f't@x namespaces="git" {pub}\n')
        self.patches = [
            mock.patch.dict(os.environ, {"GIT_CONFIG_GLOBAL": "/dev/null"}),
            mock.patch.object(updater, "REPO_DIR", self.clone),
            mock.patch.object(updater, "LOCAL_DIR", self.local),
            mock.patch.object(updater, "STATE_FILE", self.local / "state.json"),
            mock.patch.object(updater, "ALLOWED_SIGNERS", self.local / "allowed_signers"),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _commit(self, changelog, tag, key):
        (self.origin / "CHANGELOG.md").write_text(changelog)
        run("git", "add", ".", cwd=self.origin, env=self.env)
        run("git", "commit", "-q", "-m", tag, cwd=self.origin, env=self.env)
        run("git", "config", "user.signingkey", str(key) + ".pub", cwd=self.origin, env=self.env)
        run("git", "tag", "-s", tag, "-m", tag, cwd=self.origin, env=self.env)

    def test_check_skips_badly_signed_newest_and_reports_error(self):
        with self.assertRaises(updater.UpdateError):
            updater.check(self.clone)

    def test_install_and_undo_flow(self):
        # Remove the rogue tag from origin so the newest is a good one.
        run("git", "tag", "-d", "v0.3.0", cwd=self.origin, env=self.env)
        run("git", "tag", "-d", "v0.3.0", cwd=self.clone, env=self.env, check=False)
        updater.install("v0.1.0", self.clone)
        rel = updater.check(self.clone)
        self.assertEqual(rel.tag, "v0.2.0")
        self.assertIn("Segunda", rel.notes)
        self.assertNotIn("Primera", rel.notes)
        updater.install(rel.tag, self.clone)
        self.assertEqual(updater.read_state(), {"current": "v0.2.0", "previous": "v0.1.0"})
        self.assertIsNone(updater.check(self.clone))
        self.assertEqual(updater.undo(self.clone), "v0.1.0")
        self.assertEqual(updater.read_state()["current"], "v0.1.0")
        head = run("git", "describe", "--tags", "--exact-match", cwd=self.clone).stdout.strip()
        self.assertEqual(head, "v0.1.0")
        self.assertTrue((self.local / "updates.log").read_text().count("\n") == 3)

    def test_install_refuses_unsigned_or_wrong_key(self):
        with self.assertRaises(updater.UpdateError):
            updater.install("v0.3.0", self.clone)
        self.assertEqual(updater.read_state()["current"], None)

    def test_refuses_without_allowed_signers(self):
        (self.local / "allowed_signers").unlink()
        with self.assertRaises(updater.UpdateError):
            updater.verify_tag("v0.1.0", self.clone)


if __name__ == "__main__":
    unittest.main()
