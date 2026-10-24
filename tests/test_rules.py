import tempfile
import unittest
from pathlib import Path

from onebutton import rules


class RulesTests(unittest.TestCase):
    def test_base_first_then_modules(self):
        text = rules.assemble(["maths-screen"])
        self.assertTrue(text.startswith("# OneButton agent rules"))
        self.assertIn("<!-- módulo: maths-screen -->", text)
        self.assertIn("pizarra", text)
        self.assertLess(text.index("agent rules"), text.index("módulo: maths-screen"))

    def test_unknown_module_ignored(self):
        self.assertEqual(rules.assemble(["nope"]), rules.assemble([]))

    def test_install_writes_workspace_file(self):
        with tempfile.TemporaryDirectory() as d:
            target = rules.install([], Path(d))
            self.assertEqual(target.name, "CLAUDE.md")
            self.assertIn("Confirmation habits", target.read_text())

    def test_every_module_has_rules_and_readme(self):
        for name in rules.available_modules():
            self.assertTrue((rules.MODULES_DIR / name / "README.md").exists(), name)


if __name__ == "__main__":
    unittest.main()
