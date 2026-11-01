import unittest

from onebutton import conversations as cv


class ParseTests(unittest.TestCase):
    def test_new(self):
        for t in ("nueva conversación", "Nueva conversación.", "otra conversación", "abre otra conversación",
                  "quiero una nueva conversación", "conversación nueva", "nueva charla", "nueva sesión"):
            self.assertEqual(cv.parse(t), {"kind": cv.NEW}, t)

    def test_switch(self):
        self.assertEqual(cv.parse("conversación dos"), {"kind": cv.SWITCH, "n": 2})
        self.assertEqual(cv.parse("cambia a la conversación tres"), {"kind": cv.SWITCH, "n": 3})
        self.assertEqual(cv.parse("vuelve a la conversación uno"), {"kind": cv.SWITCH, "n": 1})
        self.assertEqual(cv.parse("ve a la conversación 4"), {"kind": cv.SWITCH, "n": 4})
        self.assertEqual(cv.parse("conversación número dos"), {"kind": cv.SWITCH, "n": 2})
        self.assertEqual(cv.parse("vuelve a la primera"), {"kind": cv.SWITCH, "n": 1})
        self.assertEqual(cv.parse("conversación segunda"), {"kind": cv.SWITCH, "n": 2})

    def test_close_and_list(self):
        self.assertEqual(cv.parse("cierra esta conversación"), {"kind": cv.CLOSE})
        self.assertEqual(cv.parse("cierra la conversación dos"), {"kind": cv.CLOSE, "n": 2})
        self.assertEqual(cv.parse("qué conversaciones hay"), {"kind": cv.LIST})
        self.assertEqual(cv.parse("cuántas conversaciones tengo"), {"kind": cv.LIST})
        self.assertEqual(cv.parse("en qué conversación estoy"), {"kind": cv.LIST})

    def test_not_a_command(self):
        for t in ("conversación", "escribe una conversación entre dos personas", "hola", "",
                  "la conversación de ayer fue larga", "cuéntame una historia sobre dos conversaciones",
                  "resume la conversación"):
            self.assertIsNone(cv.parse(t), t)


class RegistryTests(unittest.TestCase):
    def test_numbering_and_switching(self):
        r = cv.Registry()
        self.assertEqual(r.current.n, 1)
        c2 = r.new(); c3 = r.new()
        self.assertEqual([c.n for c in r.items], [1, 2, 3])
        self.assertIs(r.current, c3)
        self.assertIs(r.switch(2), c2); self.assertIs(r.current, c2)
        self.assertIsNone(r.switch(9)); self.assertIs(r.current, c2)
        self.assertNotEqual(c2.session_id, c3.session_id)
        self.assertEqual(c2.file, "conversaciones/2.md")

    def test_close_keeps_one_and_numbers_never_repeat(self):
        r = cv.Registry()
        r.new()
        self.assertEqual(r.close().n, 2)                 # closes the current one
        self.assertEqual(r.current.n, 1)
        self.assertEqual(r.close(1).n, 1)
        self.assertEqual([c.n for c in r.items], [3], "the registry never goes empty; numbers are not reused")
        self.assertIsNone(r.close(7))

    def test_summary_and_unannounced(self):
        r = cv.Registry()
        self.assertIn("una sola conversación", r.summary())
        r.items[0].title = "la suma de los primeros..."
        r.items[0].state = cv.WORKING
        c2 = r.new()
        s = r.summary()
        self.assertIn("Hay dos conversaciones.", s)
        self.assertIn("La uno, sobre la suma de los primeros..., está trabajando.", s)
        self.assertIn("La dos, está libre.", s)
        self.assertIn("Estás en la dos.", s)
        self.assertEqual(r.working(), [r.items[0]])
        r.items[0].add_reply("listo")
        self.assertEqual(r.items[0].state, cv.DONE)
        self.assertEqual(r.unannounced(), [r.items[0]])
        self.assertEqual(r.items[0].take_replies(), ["listo"])
        self.assertEqual(r.items[0].state, cv.IDLE); self.assertEqual(r.unannounced(), [])
        self.assertEqual(cv.short_title("uno dos tres cuatro cinco seis siete"), "uno dos tres cuatro cinco seis...")
        self.assertEqual(cv.spoken(2), "dos"); self.assertEqual(cv.spoken(12), "12")


if __name__ == "__main__":
    unittest.main()
