import unittest

from onebutton import commands
from onebutton.config import DEFAULTS

C = commands


class ClassifyTests(unittest.TestCase):
    cfg = DEFAULTS

    def test_empty(self):
        self.assertEqual(C.classify("   ", self.cfg).kind, C.EMPTY)
        self.assertEqual(C.classify("...", self.cfg).kind, C.EMPTY)

    def test_update_variants(self):
        for s in ["actualiza", "Actualiza.", "por favor actualiza", "ACTUALIZAR ya"]:
            with self.subTest(s=s):
                self.assertEqual(C.classify(s, self.cfg).kind, C.UPDATE, s)

    def test_update_inside_long_sentence_is_text(self):
        s = "escribe un correo a Juan diciendo que actualiza el documento mañana"
        self.assertEqual(C.classify(s, self.cfg).kind, C.TEXT)

    def test_undo_and_repeat(self):
        self.assertEqual(C.classify("deshacer", self.cfg).kind, C.UNDO)
        self.assertEqual(C.classify("Repite", self.cfg).kind, C.REPEAT)

    def test_text_preserved(self):
        cmd = C.classify("  Resuelve la integral de x al cuadrado  ", self.cfg)
        self.assertEqual(cmd.kind, C.TEXT)
        self.assertEqual(cmd.text, "Resuelve la integral de x al cuadrado")

    def test_confirmation_strict(self):
        yes = ["adelante", "Adelante.", "sí, adelante", "confirmo"]
        for s in yes:
            with self.subTest(s=s):
                self.assertEqual(C.classify(s, self.cfg, awaiting_confirmation=True).kind, C.CONFIRM)
        no = ["", "no", "sí", "espera", "actualiza", "adelante con lo otro que te dije antes de todo esto"]
        for s in no:
            with self.subTest(s=s):
                self.assertNotEqual(C.classify(s, self.cfg, awaiting_confirmation=True).kind, C.CONFIRM)

    def test_normalize(self):
        self.assertEqual(C.normalize("¡Sí, ADELANTE!"), "si adelante")


if __name__ == "__main__":
    unittest.main()
