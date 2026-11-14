"""The launcher brings the libraries up to date after the code changed (a `git pull`, an update)."""

import tempfile
import unittest
from pathlib import Path

from onebutton import launcher


class RequirementsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = Path(self.tmp.name)
        self.req, self.stamp = d / "requirements.txt", d / "local" / "requirements.sha256"
        self.req.write_text("pyyaml>=6.0\n", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_never_installed_from_here_counts_as_changed(self):
        self.assertTrue(launcher.requirements_changed(self.req, self.stamp))

    def test_unchanged_after_it_was_recorded(self):
        launcher.record_requirements(launcher.requirements_changed(self.req, self.stamp), self.stamp)
        self.assertIsNone(launcher.requirements_changed(self.req, self.stamp))

    def test_a_new_library_is_noticed(self):
        launcher.record_requirements(launcher.requirements_changed(self.req, self.stamp), self.stamp)
        self.req.write_text("pyyaml>=6.0\npiper-tts>=1.3\n", encoding="utf-8")
        self.assertTrue(launcher.requirements_changed(self.req, self.stamp))

    def test_no_requirements_file_is_nothing_to_do(self):
        self.req.unlink()
        self.assertIsNone(launcher.requirements_changed(self.req, self.stamp))


if __name__ == "__main__":
    unittest.main()
