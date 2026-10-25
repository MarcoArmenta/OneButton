import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BLOCKS = REPO / "modules" / "scribe" / "blocks.py"
spec = importlib.util.spec_from_file_location("blocks", BLOCKS)
blocks = importlib.util.module_from_spec(spec)
spec.loader.exec_module(blocks)

DOC = """# Título

Primer párrafo
con dos líneas.

$$
a = b

c = d
$$

```python
x = 1

y = 2
```

Último.
"""


class SplitTests(unittest.TestCase):
    def test_split_keeps_fences_whole(self):
        b = blocks.split_blocks(DOC)
        self.assertEqual(len(b), 5)
        self.assertEqual(b[0], "# Título")
        self.assertTrue(b[2].startswith("$$") and b[2].endswith("$$"))
        self.assertTrue(b[3].startswith("```") and b[3].endswith("```"))
        self.assertEqual(b[4], "Último.")

    def test_roundtrip(self):
        self.assertEqual(blocks.split_blocks(blocks.join_blocks(blocks.split_blocks(DOC))), blocks.split_blocks(DOC))

    def test_cli_set_insert_delete(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "m.md"
            f.write_text(DOC, encoding="utf-8")
            run = lambda *a, inp="": subprocess.run([sys.executable, str(BLOCKS), *a, str(f)] + list(a[2:]) if False else [sys.executable, str(BLOCKS), a[0], str(f), *a[1:]], input=inp, capture_output=True, text=True)
            out = run("list").stdout
            self.assertIn("1: # Título", out)
            self.assertIn("5: Último.", out)
            self.assertEqual(run("get", "5").stdout.strip(), "Último.")
            run("set", "5", inp="Penúltimo.\n")
            self.assertEqual(blocks.split_blocks(f.read_text())[-1], "Penúltimo.")
            run("insert", "5", inp="Último de verdad.")
            self.assertEqual(blocks.split_blocks(f.read_text())[-1], "Último de verdad.")
            run("set", "1", inp="")
            self.assertEqual(blocks.split_blocks(f.read_text())[0], "Primer párrafo\ncon dos líneas.")
            self.assertEqual(run("get", "99").returncode, 1)

    @unittest.skipUnless(__import__("shutil").which("node"), "needs node")
    def test_page_counts_the_same_way(self):
        js = (REPO / "onebutton" / "screen" / "screen.js").read_text(encoding="utf-8")
        start = js.index("  function blocksOf(text) {")
        end = js.index("  window.blocksOf = blocksOf;")
        fn = js[start:end]
        script = fn + "\nconst t = require('fs').readFileSync(0, 'utf8'); console.log(JSON.stringify(blocksOf(t)));"
        r = subprocess.run(["node", "-e", script], input=DOC, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        import json
        self.assertEqual(json.loads(r.stdout), blocks.split_blocks(DOC))


if __name__ == "__main__":
    unittest.main()
