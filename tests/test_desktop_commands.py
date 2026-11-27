import unittest

from onebutton.desktop_commands import parse


class ParseTests(unittest.TestCase):
    def check(self, text, expected):
        self.assertEqual(parse(text), expected, text)

    def test_windows_and_focus(self):
        self.check("qué ventanas hay", {"action": "windows"})
        self.check("ve a Chrome", {"action": "focus", "target": "chrome"})
        self.check("cambia al navegador", {"action": "focus", "target": "navegador"})
        self.check("abre el bloc de notas", {"action": "open", "target": "bloc de notas"})

    def test_screen_panels_are_not_desktop_targets(self):
        self.assertIsNone(parse("ve al pizarrón"))
        self.assertIsNone(parse("ve a la pizarra"))
        self.assertIsNone(parse("muestra el escritorio"))

    def test_anything_about_a_panel_goes_to_claude(self):
        # "escribe ..." types into the focused application; said about the pizarrón it is a request to Claude
        self.assertIsNone(parse("escribe en el pizarrón x al cuadrado más uno"))
        self.assertIsNone(parse("escribe la integral de x al cuadrado en el pizarrón"))
        self.assertIsNone(parse("dicta en el pizarrón el teorema de Pitágoras"))
        self.assertIsNone(parse("muestra en el pizarrón la serie geométrica"))
        self.assertIsNone(parse("escribe en el manuscrito que mañana seguimos"))
        self.assertIsNone(parse("abre el escrito de la tesis"))

    def test_the_same_in_english_without_swallowing_ordinary_typing(self):
        self.assertIsNone(parse("type x squared plus one on the board"))
        self.assertIsNone(parse("type the theorem in my paper"))
        self.assertIsNone(parse("open the paper about quivers"))
        self.assertIsNone(parse("go to the writing desk"))
        # the English names are everyday words: text that merely contains one is still typed
        self.check("type the paper is due on friday", {"action": "type", "text": "the paper is due on friday"})
        self.check("type we should chat tomorrow", {"action": "type", "text": "we should chat tomorrow"})

    def test_numbers_and_clicks(self):
        self.check("muestra los números", {"action": "overlay"})
        self.check("pulsa el siete", {"action": "click_number", "n": 7})
        self.check("clic en el 12", {"action": "click_number", "n": 12})
        self.check("pulsa el treinta y dos", {"action": "click_number", "n": 32})
        self.check("clic derecho", {"action": "right_click"})
        self.check("rejilla", {"action": "grid"})

    def test_keys_and_typing(self):
        self.check("intro", {"action": "key", "keys": "enter"})
        self.check("pulsa escape", {"action": "key", "keys": "esc"})
        self.check("control c", {"action": "key", "keys": "ctrl+c"})
        self.check("copiar", {"action": "key", "keys": "ctrl+c"})
        self.check("cierra esta ventana", {"action": "key", "keys": "alt+f4"})
        self.check("escribe hola, Juan", {"action": "type", "text": "hola juan"})

    def test_volume_scroll_power(self):
        self.check("sube el volumen", {"action": "volume", "what": "up"})
        self.check("baja", {"action": "scroll", "dir": "down", "n": 5})
        self.check("baja diez líneas", {"action": "scroll", "dir": "down", "n": 10})
        self.check("apaga la computadora", {"action": "power", "what": "shutdown", "confirm": True})
        self.check("suspende", {"action": "power", "what": "sleep", "confirm": True})

    def test_sentences_go_to_claude(self):
        self.assertIsNone(parse("escribe un correo a Juan diciendo que mañana no puedo ir a la reunión de las diez"))
        self.assertIsNone(parse("resuelve la integral de x al cuadrado"))
        self.assertIsNone(parse("hola"))


if __name__ == "__main__":
    unittest.main()
