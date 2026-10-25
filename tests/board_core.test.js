// Pure-core tests for the blackboard editor. Run: node tests/board_core.test.js
const assert = require("assert");
const C = require("../modules/maths-screen/board.js");

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

// menu matching
const L = C.leaves(C.MENU);
assert.strictEqual(C.findItem("ponle una barra al cuatro", L).id, "bar");
assert.strictEqual(C.findItem("Subíndice, por favor", L).id, "sub");
assert.strictEqual(C.findItem("al cuadrado", L).id, "sq");
assert.strictEqual(C.findItem("bórralo", L), null);
assert.strictEqual(C.findItem("borra", L).id, "delete");
assert.strictEqual(C.findItem("hola", L), null);

// formulas in markdown
const fs = C.findFormulas("a $x$ b $$y$$ c \\(z\\) \\[w\\] and $5 dollars");
assert.deepStrictEqual(fs.map(f => f.inner), ["x", "y", "z", "w"]);
const md = "t $$a+b$$ u";
const f = fs[0];
assert.strictEqual(md.slice(C.findFormulas(md)[0].start, C.findFormulas(md)[0].end), "a+b");

console.log("board core ok");
