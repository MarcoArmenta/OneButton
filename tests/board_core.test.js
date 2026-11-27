// Pure-core tests for the blackboard editor. Run: node tests/board_core.test.js
const assert = require("assert");
const C = require("../onebutton/screen/board.js");

const src = "x_i^2 + \\frac{a+b}{c} = \\sqrt{\\bar{y}}";
const H = C.hints(src);
const srcs = H.map(h => h.src);
assert.deepStrictEqual(srcs.slice(0, 6), ["x_i^2", "x", "i", "2", "+", "\\frac{a+b}{c}"]);
assert.ok(srcs.includes("\\sqrt{\\bar{y}}") && srcs.includes("\\bar{y}"), "composite spans found");
assert.strictEqual(new Set(srcs.map((s, i) => H[i].start + ":" + H[i].end)).size, H.length, "no duplicate spans");

// splicing
assert.strictEqual(C.applyOp(src, H[1], "\\bar{%s}", ""), "x_i^2 + \\frac{a+b}{c} = \\sqrt{\\bar{y}}".replace("x_i", "\\bar{x}_i"));
assert.strictEqual(C.applyOp(src, H[0], "{%s}_{%c}", "jk"), "{x_i^2}_{jk} + \\frac{a+b}{c} = \\sqrt{\\bar{y}}");
assert.strictEqual(C.applyOp(src, H[5], "", ""), "x_i^2 +  = \\sqrt{\\bar{y}}");
assert.strictEqual(C.applyOp(src, H[5], "%c", "\\frac{1}{2}"), "x_i^2 + \\frac{1}{2} = \\sqrt{\\bar{y}}");

// big operators and left/right
assert.strictEqual(C.hints("\\sum_{i=1}^{n} a_i")[0].src, "\\sum_{i=1}^{n}");
assert.strictEqual(C.hints("\\left( a + b \\right)^2")[1].src, "\\left( a + b \\right)");

// broken latex never throws
assert.deepStrictEqual(C.hints("\\frac{a}{"), []);

// numbers
assert.strictEqual(C.parseNumber("el siete"), 7);
assert.strictEqual(C.parseNumber("treinta y dos"), 32);
assert.strictEqual(C.parseNumber("barra en el 3"), 3);
assert.strictEqual(C.parseNumber("veintiuno"), 21);
assert.strictEqual(C.parseNumber("una barra"), null, "articles are not numbers");
assert.strictEqual(C.parseNumber("nada"), null);
assert.strictEqual(C.parseNumber("bar on the seven"), 7);
assert.strictEqual(C.parseNumber("thirty two"), 32);
assert.strictEqual(C.parseNumber("twenty"), 20);
assert.strictEqual(C.parseNumber("treinta dos"), 30, "Spanish tens need 'y'");
assert.strictEqual(C.parseNumber("a bar"), null, "articles are not numbers");

// menu matching
const L = C.leaves(C.MENU);
assert.strictEqual(C.findItem("ponle una barra al cuatro", L).id, "bar");
assert.strictEqual(C.findItem("Subíndice, por favor", L).id, "sub");
assert.strictEqual(C.findItem("al cuadrado", L).id, "sq");
assert.strictEqual(C.findItem("bórralo", L), null);
assert.strictEqual(C.findItem("borra", L).id, "delete");
assert.strictEqual(C.findItem("hola", L), null);
assert.strictEqual(C.findItem("put a bar on the four", L).id, "bar");
assert.strictEqual(C.findItem("subscript please", L).id, "sub");
assert.strictEqual(C.findItem("squared", L).id, "sq");
assert.strictEqual(C.findItem("delete it", L).id, "delete");
assert.strictEqual(C.findItem("hello", L), null);

// what the page says follows the language; what it understands does not
assert.strictEqual(C.label(C.MENU[0]), "Decorate");
assert.strictEqual(C.needs(L.find(x => x.id === "sub")), "the subscript");
C.setLang("es");
assert.strictEqual(C.label(C.MENU[0]), "Decorar");
assert.strictEqual(C.needs(L.find(x => x.id === "sub")), "el subíndice");
assert.strictEqual(C.T("yes", "sí"), "sí");
C.setLang("en");

// formulas in markdown
const fs = C.findFormulas("a $x$ b $$y$$ c \\(z\\) \\[w\\] and $5 dollars");
assert.deepStrictEqual(fs.map(f => f.inner), ["x", "y", "z", "w"]);
const md = "t $$a+b$$ u";
const f = fs[0];
assert.strictEqual(md.slice(C.findFormulas(md)[0].start, C.findFormulas(md)[0].end), "a+b");

// panels: only the name, alone or with a verb of going there. Anything else said about a panel is for Claude.
const ALL = ["conversacion", "pizarron", "escritorio"];
assert.strictEqual(C.parsePanel("Pizarrón.", ALL), "pizarron");
assert.strictEqual(C.parsePanel("ve al pizarrón", ALL), "pizarron");
assert.strictEqual(C.parsePanel("abre el pizarrón por favor", ALL), "pizarron");
assert.strictEqual(C.parsePanel("muéstrame la conversación", ALL), "conversacion");
assert.strictEqual(C.parsePanel("quiero ver el escritorio", ALL), "escritorio");
assert.strictEqual(C.parsePanel("pizarra", ALL), "pizarron", "the alias still works");
for (const t of ["borra el pizarrón", "pizarrón nuevo", "guarda el pizarrón", "nuevo escrito", "escribe en el pizarrón",
                 "dame una respuesta corta", "corrige el texto", "pizarrón dos más dos", "hola", ""])
  assert.strictEqual(C.parsePanel(t, ALL), null, t + " is not a panel switch");
assert.strictEqual(C.parsePanel("pizarrón", ["conversacion"]), null, "a panel that is off is not there");

// scrolling by voice
const sc = t => C.parseScroll(t, ALL);
assert.deepStrictEqual(sc("baja"), { dir: "down", steps: 1, panel: null });
assert.deepStrictEqual(sc("Sube."), { dir: "up", steps: 1, panel: null });
assert.deepStrictEqual(sc("más abajo"), { dir: "down", steps: 1, panel: null });
assert.deepStrictEqual(sc("sigue bajando"), { dir: "down", steps: 1, panel: null });
assert.deepStrictEqual(sc("baja el pizarrón"), { dir: "down", steps: 1, panel: "pizarron" });
assert.deepStrictEqual(sc("sube la conversación"), { dir: "up", steps: 1, panel: "conversacion" });
assert.deepStrictEqual(sc("pizarrón arriba"), { dir: "up", steps: 1, panel: "pizarron" });
assert.deepStrictEqual(sc("baja un poco"), { dir: "down", steps: 0.4, panel: null });
assert.deepStrictEqual(sc("baja mucho"), { dir: "down", steps: 3, panel: null });
assert.deepStrictEqual(sc("baja tres"), { dir: "down", steps: 3, panel: null });
assert.deepStrictEqual(sc("sube dos páginas"), { dir: "up", steps: 2, panel: null });
assert.deepStrictEqual(sc("página siguiente"), { dir: "down", steps: 1, panel: null });
assert.deepStrictEqual(sc("página anterior"), { dir: "up", steps: 1, panel: null });
assert.deepStrictEqual(sc("al principio"), { dir: "top", steps: 1, panel: null });
assert.deepStrictEqual(sc("hasta arriba"), { dir: "top", steps: 1, panel: null });
assert.deepStrictEqual(sc("arriba del todo"), { dir: "top", steps: 1, panel: null });
assert.deepStrictEqual(sc("al final del pizarrón"), { dir: "bottom", steps: 1, panel: "pizarron" });
assert.deepStrictEqual(sc("baja hasta el final"), { dir: "bottom", steps: 1, panel: null });
assert.deepStrictEqual(sc("hasta abajo"), { dir: "bottom", steps: 1, panel: null });
// not scrolling: volume, a word for Claude ("sigue"), the cancel word ("para"), sentences
for (const t of ["sube el volumen", "baja el volumen", "sigue", "continúa", "para", "más", "siguiente", "anterior",
                 "baja el brillo de la pantalla", "sube y baja", "pizarrón", "menú inicio", "hola", ""])
  assert.strictEqual(sc(t), null, t + " is not a scroll");
assert.strictEqual(sc("baja el pizarrón").panel, "pizarron");
assert.strictEqual(C.parseScroll("baja el pizarrón", ["conversacion"]), null, "a panel that is off cannot be scrolled");

// panels and scrolling in English
assert.strictEqual(C.parsePanel("board", ALL), "pizarron");
assert.strictEqual(C.parsePanel("go to the board", ALL), "pizarron");
assert.strictEqual(C.parsePanel("show me the conversation", ALL), "conversacion");
assert.strictEqual(C.parsePanel("the writing desk", ALL), "escritorio");
assert.strictEqual(C.parsePanel("bring up the board please", ALL), "pizarron");
for (const t of ["erase the board", "new paper", "write on the board", "change the board", "the board is wrong", "hello"])
  assert.strictEqual(C.parsePanel(t, ALL), null, t + " is not a panel switch");
assert.deepStrictEqual(sc("scroll down"), { dir: "down", steps: 1, panel: null });
assert.deepStrictEqual(sc("go up"), { dir: "up", steps: 1, panel: null });
assert.deepStrictEqual(sc("scroll down a little"), { dir: "down", steps: 0.4, panel: null });
assert.deepStrictEqual(sc("go down a lot"), { dir: "down", steps: 3, panel: null });
assert.deepStrictEqual(sc("scroll down three times"), { dir: "down", steps: 3, panel: null });
assert.deepStrictEqual(sc("scroll down the board"), { dir: "down", steps: 1, panel: "pizarron" });
assert.deepStrictEqual(sc("next page"), { dir: "down", steps: 1, panel: null });
assert.deepStrictEqual(sc("go to the top"), { dir: "top", steps: 1, panel: null });
assert.deepStrictEqual(sc("to the end of the board"), { dir: "bottom", steps: 1, panel: "pizarron" });
assert.deepStrictEqual(sc("all the way up"), { dir: "top", steps: 1, panel: null });
for (const t of ["volume up", "turn it up", "keep going", "go back", "more", "next", "go to the board", "up and down", "zero"])
  assert.strictEqual(sc(t), null, t + " is not a scroll");
// a place that is only named is not an order to go there: he may be dictating it
for (const t of ["fin", "final", "el principio", "the end", "the beginning", "start", "top"])
  assert.strictEqual(sc(t), null, t + " is not a scroll");

// "otra vez", "again": said to the page, they repeat its last scroll
for (const t of ["otra vez", "Otra vez.", "de nuevo", "más", "again", "once more", "again please"])
  assert.strictEqual(C.parseAgain(t), true, t);
for (const t of ["baja", "again and again", "otra conversación", "hola", ""])
  assert.strictEqual(C.parseAgain(t), false, t);

console.log("board core ok");
