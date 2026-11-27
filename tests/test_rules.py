import tempfile
import unittest
from pathlib import Path

from onebutton import rules


class RulesTests(unittest.TestCase):
    def test_base_first_then_modules(self):
        text = rules.assemble(["maths-screen"])
        self.assertTrue(text.startswith("# OneButton agent rules"))
        self.assertIn("<!-- módulo: maths-screen -->", text)
        self.assertIn("pizarrón", text)
        self.assertLess(text.index("agent rules"), text.index("módulo: maths-screen"))

    def test_unknown_module_ignored(self):
        self.assertEqual(rules.assemble(["nope"]), rules.assemble([]))

    def test_install_writes_workspace_file(self):
        with tempfile.TemporaryDirectory() as d:
            target = rules.install([], Path(d))
            self.assertEqual(target.name, "CLAUDE.md")
            self.assertIn("Confirmation habits", target.read_text())

    def test_the_user_may_shape_how_it_works_but_not_its_limits(self):
        text = " ".join(rules.assemble([]).split())
        for promise in ["from now on", "de ahora en adelante", "save it in your memory", "forget that",
                        'never relaxes the sections "Confirmation habits" and "Security"']:
            self.assertIn(promise, text)

    def test_every_module_has_rules_and_readme(self):
        for name in rules.available_modules():
            self.assertTrue((rules.MODULES_DIR / name / "README.md").exists(), name)


if __name__ == "__main__":
    unittest.main()
