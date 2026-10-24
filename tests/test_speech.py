import unittest

from onebutton.speech import clean_for_speech as c


class SpeechTests(unittest.TestCase):
    def test_code_fence_replaced(self):
        out = c("Aquí va:\n```python\nprint(1)\n```\nFin.")
        self.assertNotIn("print", out)
        self.assertIn("código en pantalla", out)

    def test_math_not_read_as_symbols(self):
        out = c(r"La integral es $\frac{x^3}{3} + C$ y además $$\sum_{i=1}^n a_i$$.")
        self.assertNotIn("frac", out)
        self.assertNotIn("sum_", out)
        self.assertIn("fórmula en pantalla", out)

    def test_markdown_stripped(self):
        out = c("## Título\n\n- **uno**\n- _dos_\n1. tres\n")
        self.assertEqual(out.split("\n")[0], "Título")
        self.assertNotIn("*", out)
        self.assertNotIn("#", out)
        self.assertIn("uno", out)
        self.assertIn("tres", out)

    def test_links_and_urls(self):
        out = c("Mira [esto](https://example.com/a) o https://example.com/b")
        self.assertIn("esto", out)
        self.assertNotIn("https", out)
        self.assertIn("enlace en pantalla", out)

    def test_table_summarised(self):
        out = c("Datos:\n| a | b |\n|---|---|\n| 1 | 2 |\n")
        self.assertIn("tabla en pantalla", out)
        self.assertNotIn("|", out)

    def test_symbols_and_emoji(self):
        out = c("x ≤ y → z 🚀 50%")
        self.assertIn("menor o igual que", out)
        self.assertIn("flecha", out)
        self.assertIn("por ciento", out)
        self.assertNotIn("🚀", out)

    def test_plain_text_untouched(self):
        s = "Listo. Guardé la carta en cartas, carta a Juan punto md."
        self.assertEqual(c(s), s)

    def test_english_notes(self):
        self.assertIn("formula on screen", c("$x$", lang="en"))


if __name__ == "__main__":
    unittest.main()
