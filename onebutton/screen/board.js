/* Blackboard editing: hints, menu, splicing. Voice composes, buttons point.
 *
 * BoardCore is pure (no DOM) so it can be tested in node:
 *   findFormulas(md) -> [{start, end, inner}]      spans of $...$, $$...$$, \[...\], \(...\)
 *   hints(latex)     -> [{n, start, end, src}]     selectable spans, in reading order
 *   applyOp(latex, span, template, content)        template uses %s (span) and %c (content)
 *   parseNumber(text)                              Spanish or English number words, or digits -> int
 *   findItem(text, items)                          menu item whose words appear in text
 * BoardUI drives the page from events the loop posts to /event.
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory(require("./vendor/katex/katex.min.js"));
  else root.BoardCore = factory(root.katex);
})(typeof self !== "undefined" ? self : this, function (katex) {
  "use strict";

  // ---- menu ---------------------------------------------------------------
  // Every item is understood in Spanish and English (`words`); `label` is said in Spanish, `en` in English.
  const MENU = [
    { id: "decorar", label: "Decorar", en: "Decorate", words: ["decorar", "decorate"], items: [
      { id: "bar", label: "barra", en: "bar", words: ["barra", "bar"], op: "\\bar{%s}" },
      { id: "hat", label: "sombrero", en: "hat", words: ["sombrero", "gorro", "circunflejo", "hat"], op: "\\hat{%s}" },
      { id: "tilde", label: "tilde", en: "tilde", words: ["tilde", "virgulilla"], op: "\\tilde{%s}" },
      { id: "vec", label: "vector", en: "vector", words: ["vector", "flecha", "arrow"], op: "\\vec{%s}" },
      { id: "dot", label: "punto", en: "dot", words: ["punto", "dot"], op: "\\dot{%s}" },
      { id: "prime", label: "prima", en: "prime", words: ["prima", "prime"], op: "{%s}'" },
    ]},
    { id: "indices", label: "Índices", en: "Indices", words: ["indices"], items: [
      { id: "sub", label: "subíndice", en: "subscript", words: ["subindice", "sub", "subscript"], op: "{%s}_{%c}", needs: "el subíndice", needs_en: "the subscript" },
      { id: "sup", label: "superíndice", en: "superscript", words: ["superindice", "super", "exponente", "elevado", "superscript", "exponent", "power"], op: "{%s}^{%c}", needs: "el exponente", needs_en: "the exponent" },
      { id: "sq", label: "al cuadrado", en: "squared", words: ["cuadrado", "squared"], op: "{%s}^{2}" },
      { id: "inv", label: "inverso", en: "inverse", words: ["inverso", "inversa", "inverse"], op: "{%s}^{-1}" },
    ]},
    { id: "estructura", label: "Estructura", en: "Structure", words: ["estructura", "structure"], items: [
      { id: "frac", label: "fracción", en: "fraction", words: ["fraccion", "sobre", "dividido", "fraction", "over", "divided"], op: "\\frac{%s}{%c}", needs: "el denominador", needs_en: "the denominator" },
      { id: "sqrt", label: "raíz", en: "root", words: ["raiz", "root"], op: "\\sqrt{%s}" },
      { id: "paren", label: "paréntesis", en: "parentheses", words: ["parentesis", "parentheses", "parens"], op: "\\left(%s\\right)" },
      { id: "brack", label: "corchetes", en: "square brackets", words: ["corchetes", "corchete", "brackets", "square brackets"], op: "\\left[%s\\right]" },
      { id: "abs", label: "valor absoluto", en: "absolute value", words: ["absoluto", "modulo", "norma", "absolute", "norm"], op: "\\left|%s\\right|" },
    ]},
    { id: "editar", label: "Editar", en: "Edit", words: ["editar", "edit"], items: [
      { id: "replace", label: "reemplazar", en: "replace", words: ["reemplazar", "reemplaza", "cambiar", "cambia", "sustituir", "replace", "change", "substitute"], op: "%c", needs: "el reemplazo", needs_en: "the replacement" },
      { id: "delete", label: "borrar", en: "delete", words: ["borrar", "borra", "eliminar", "elimina", "quitar", "quita", "delete", "remove", "erase"], op: "" },
      { id: "undo", label: "deshacer", en: "undo", words: ["deshacer", "deshaz", "undo"], action: "undo" },
      { id: "prev", label: "fórmula anterior", en: "previous formula", words: ["anterior", "previous"], action: "prevFormula" },
      { id: "next", label: "fórmula siguiente", en: "next formula", words: ["siguiente", "next"], action: "nextFormula" },
    ]},
    { id: "ayuda", label: "Ayuda", en: "Help", words: ["ayuda", "help"], action: "help" },
    { id: "salir", label: "Salir", en: "Exit", words: ["salir", "listo", "terminar", "exit", "done", "finish"], action: "exit" },
  ];

  // ---- language: what the page speaks. Set from the loop's config event. ----
  let LANG = "en";
  function setLang(l) { LANG = (l === "es") ? "es" : "en"; }
  function lang() { return LANG; }
  function T(en, es) { return LANG === "es" ? es : en; }
  function label(it) { return LANG === "es" ? it.label : (it.en || it.label); }
  function needs(it) { return LANG === "es" ? it.needs : (it.needs_en || it.needs); }

  function leaves(items, out) {
    out = out || [];
    for (const it of items) { if (it.items) leaves(it.items, out); else out.push(it); }
    return out;
  }

  // ---- text helpers -------------------------------------------------------
  function normalize(s) {
    return (s || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "")
      .replace(/[^\w\s]/g, " ").replace(/\s+/g, " ").trim();
  }

  const UNITS = { cero: 0, uno: 1, dos: 2, tres: 3, cuatro: 4, cinco: 5, seis: 6, siete: 7, ocho: 8,
    nueve: 9, diez: 10, once: 11, doce: 12, trece: 13, catorce: 14, quince: 15, dieciseis: 16, diecisiete: 17,
    dieciocho: 18, diecinueve: 19, veinte: 20, veintiuno: 21, veintidos: 22, veintitres: 23, veinticuatro: 24,
    veinticinco: 25, veintiseis: 26, veintisiete: 27, veintiocho: 28, veintinueve: 29, treinta: 30, cuarenta: 40,
    zero: 0, one: 1, two: 2, three: 3, four: 4, five: 5, six: 6, seven: 7, eight: 8, nine: 9, ten: 10,
    eleven: 11, twelve: 12, thirteen: 13, fourteen: 14, fifteen: 15, sixteen: 16, seventeen: 17, eighteen: 18,
    nineteen: 19, twenty: 20, thirty: 30, forty: 40 };
  const TENS = { treinta: 1, cuarenta: 1, twenty: 1, thirty: 1, forty: 1 };

  function parseNumber(text) {
    const words = normalize(text).split(" ");
    for (let i = 0; i < words.length; i++) {
      const w = words[i];
      if (/^\d{1,2}$/.test(w)) return parseInt(w, 10);
      if (w in UNITS) {
        let n = UNITS[w];
        if (w in TENS) {   // "treinta y dos", "thirty two"
          const spanish = w === "treinta" || w === "cuarenta";       // Spanish joins with "y", English with nothing
          const j = spanish ? (words[i + 1] === "y" ? i + 2 : -1) : i + 1;
          if (j > 0 && words[j] in UNITS && UNITS[words[j]] > 0 && UNITS[words[j]] < 10) n += UNITS[words[j]];
        }
        return n;
      }
    }
    return null;
  }

  function findItem(text, items) {
    const t = " " + normalize(text) + " ";
    let best = null, bestLen = 0;
    for (const it of items) {
      for (const w of it.words || []) {
        if (t.indexOf(" " + w + " ") >= 0 && w.length > bestLen) { best = it; bestLen = w.length; }
      }
    }
    return best;
  }

  // ---- formulas in markdown -----------------------------------------------
  const FORMULA_RE = /\$\$([\s\S]+?)\$\$|\\\[([\s\S]+?)\\\]|\$([^$\n]+?)\$|\\\(([\s\S]+?)\\\)/g;

  function findFormulas(md) {
    const out = [];
    let m;
    FORMULA_RE.lastIndex = 0;
    while ((m = FORMULA_RE.exec(md)) !== null) {
      let k = 1; while (m[k] === undefined) k++;
      const open = (k === 1) ? 2 : (k === 2) ? 2 : (k === 3) ? 1 : 2;
      const start = m.index + open;
      out.push({ start: start, end: start + m[k].length, inner: m[k], display: k <= 2 });
    }
    return out;
  }

  // ---- hints from the KaTeX parse tree -------------------------------------
  const CHILD_KEYS = ["body", "base", "sup", "sub", "numer", "denom", "index", "value"];

  function spanOf(node, src) {
    if (node.loc) return [node.loc.start, node.loc.end];
    let lo = Infinity, hi = -Infinity;
    for (const k of CHILD_KEYS) {
      const c = node[k];
      if (!c) continue;
      const arr = Array.isArray(c) ? c : [c];
      for (const x of arr) {
        if (!x || typeof x !== "object") continue;
        const s = spanOf(x, src);
        if (s) { lo = Math.min(lo, s[0]); hi = Math.max(hi, s[1]); }
      }
    }
    if (!isFinite(lo)) return null;
    return extend(src, lo, hi);
  }

  function extend(src, lo, hi) {
    // One step only, or we would climb into the parent node: the braces that wrap this
    // node's argument, then the command right before them (\frac, \bar), or \left...\right.
    if (lo > 0 && src[lo - 1] === "{" && src[hi] === "}") { lo--; hi++; }
    const before = src.slice(0, lo);
    const cmd = before.match(/\\[a-zA-Z]+\*?\s*(\[[^\]]*\]\s*)?(\{[^{}]*\}\s*)?$/);
    if (cmd && /^\\(frac|dfrac|tfrac|binom|sqrt|bar|hat|tilde|vec|dot|ddot|overline|underline|widehat|widetilde|overrightarrow|mathbf|mathrm|mathcal|mathbb|boldsymbol|text|operatorname|overset|underset|stackrel)\b/.test(cmd[0])) {
      lo -= cmd[0].length;
      return [lo, hi];
    }
    const left = before.match(/\\left\s*(\\[a-zA-Z]+|[^\s])\s*$/);
    const right = src.slice(hi).match(/^\s*\\right\s*(\\[a-zA-Z]+|[^\s])/);
    if (left && right) { lo -= left[0].length; hi += right[0].length; }
    return [lo, hi];
  }

  function collect(nodes, src, out) {
    for (const n of nodes) {
      if (!n || typeof n !== "object") continue;
      if (n.type === "ordgroup" || n.type === "styling" || n.type === "sizing" || n.type === "color") {
        collect(n.body || [], src, out);
        continue;
      }
      let sp = spanOf(n, src);
      if (n.type === "supsub" && n.base && !spanOf(n.base, src)) {
        // base is a big operator without a location (\sum, \int, \lim): walk back over it
        const m = src.slice(0, sp ? sp[0] : 0).match(/\\[a-zA-Z]+\s*[_^]?\s*$/);
        if (m && sp) sp = [sp[0] - m[0].length, sp[1]];
      }
      if (!sp) continue;
      if (n.type === "spacing" || n.type === "kern") continue;
      // Punctuation and bare brackets are never edit targets; they only add noise to the chips.
      if (n.type === "atom" && (n.family === "punct" || n.family === "open" || n.family === "close")) continue;
      while (sp[1] > sp[0] && /\s/.test(src[sp[1] - 1])) sp[1]--;
      out.push({ start: sp[0], end: sp[1], type: n.type });
      if (n.type === "supsub") {
        if (n.base) collect([n.base], src, out);
        if (n.sub) collect([n.sub], src, out);
        if (n.sup) collect([n.sup], src, out);
      } else if (n.type === "genfrac") {
        collect([n.numer, n.denom], src, out);
      } else if (n.type === "sqrt") {
        if (n.index) collect([n.index], src, out);
        collect([n.body], src, out);
      } else if (n.type === "accent" || n.type === "font") {
        if (n.base && n.base.type !== "mathord" && n.base.type !== "textord") collect([n.base], src, out);
      } else if (n.type === "leftright" || n.type === "underline" || n.type === "overline") {
        collect(n.body || [], src, out);
      }
    }
    return out;
  }

  function hints(latex) {
    let tree;
    try { tree = katex.__parse(latex, { strict: "ignore" }); } catch (e) { return []; }
    const raw = collect(tree, latex, []);
    const seen = new Set();
    const out = [];
    for (const h of raw) {
      if (h.end <= h.start) continue;
      const key = h.start + ":" + h.end;
      if (seen.has(key)) continue;
      seen.add(key);
      out.push(h);
    }
    out.sort((a, b) => a.start - b.start || b.end - a.end);
    return out.map((h, i) => ({ n: i + 1, start: h.start, end: h.end, src: latex.slice(h.start, h.end), type: h.type }));
  }

  function applyOp(latex, span, template, content) {
    const piece = template.split("%s").join(span.src).split("%c").join(content || "");
    return latex.slice(0, span.start) + piece + latex.slice(span.end);
  }

  function highlight(latex, span, color) {
    return latex.slice(0, span.start) + "{\\color{" + color + "}" + span.src + "}" + latex.slice(span.end);
  }

  return { MENU, leaves, normalize, parseNumber, findItem, findFormulas, hints, applyOp, highlight,
    setLang, lang, T, label, needs };
});

// ---------------------------------------------------------------------------
// Browser UI
// ---------------------------------------------------------------------------
(function () {
  if (typeof window === "undefined") return;
  const C = window.BoardCore;
  const ACCENT = "#2a5db0";

  const ui = {
    mode: "idle",          // idle | hints | menu | awaiting
    md: "",                // board text as last loaded
    formulas: [], fIndex: -1,
    hints: [], hIndex: -1,
    path: [], mIndex: 0,   // menu: stack of item arrays
    pending: null,         // leaf item waiting for content
    undo: [],
    lastSeq: 0,
  };

  // ---- speech: provided by screen.js (window.screenSay); falls back to the browser directly
  function say(text) {
    if (window.screenSay) window.screenSay(text);
    const el = document.getElementById("board-status");
    if (el) el.textContent = text;
  }

  // ---- panel ---------------------------------------------------------------
  function panel() {
    let p = document.getElementById("board-panel");
    if (!p) {
      p = document.createElement("div");
      p.id = "board-panel";
      p.innerHTML = '<div id="board-status"></div><div id="board-hints"></div><div id="board-menu"></div>';
      document.body.appendChild(p);
    }
    return p;
  }

  function render() {
    const p = panel();
    p.style.display = ui.mode === "idle" ? "none" : "block";
    document.body.classList.toggle("board-active", ui.mode !== "idle");
    const hintsEl = document.getElementById("board-hints");
    const menuEl = document.getElementById("board-menu");
    hintsEl.innerHTML = ""; menuEl.innerHTML = "";
    if (ui.mode === "idle") return;
    if (ui.mode === "hints" || ui.mode === "awaiting" || ui.mode === "menu") {
      for (const h of ui.hints) {
        const chip = document.createElement("span");
        chip.className = "hint" + (h.n - 1 === ui.hIndex ? " selected" : "");
        let html;
        try { html = katex.renderToString(h.src, { throwOnError: false, strict: "ignore" }); } catch (e) { html = h.src; }
        chip.innerHTML = '<b>' + h.n + '</b>' + html;
        hintsEl.appendChild(chip);
        if (h.n - 1 === ui.hIndex) setTimeout(() => chip.scrollIntoView({ block: "nearest" }), 0);
      }
    }
    if (ui.mode === "menu") {
      const items = ui.path[ui.path.length - 1];
      const ring = document.createElement("div");
      ring.className = "ring";
      const N = items.length;
      items.forEach((it, i) => {
        const el = document.createElement("div");
        el.className = "ring-item" + (i === ui.mIndex ? " current" : "");
        el.textContent = C.label(it);
        const ang = (i / N) * 2 * Math.PI - Math.PI / 2;
        el.style.left = (50 + 36 * Math.cos(ang)) + "%";
        el.style.top = (50 + 42 * Math.sin(ang)) + "%";
        ring.appendChild(el);
      });
      menuEl.appendChild(ring);
    }
    // highlight the selected span inside the rendered board
    if (window.renderBoardWithHighlight) {
      const f = ui.formulas[ui.fIndex];
      const h = ui.hints[ui.hIndex];
      window.renderBoardWithHighlight(ui.md, (f && h) ? { f, h, color: ACCENT } : null);
    }
  }

  // ---- state ---------------------------------------------------------------
  function report(extra) {
    const st = Object.assign({
      mode: ui.mode,
      awaiting: ui.mode === "awaiting" ? (ui.pending && ui.pending.needs) : null,
      selected: ui.hIndex >= 0,
      formula: ui.fIndex, hint: ui.hIndex >= 0 ? ui.hints[ui.hIndex].n : null,
      seq_handled: ui.lastSeq,
    }, extra || {});
    fetch("/state", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(st) }).catch(() => {});
  }

  function loadFormulas(md) {
    ui.md = md;
    ui.formulas = C.findFormulas(md);
    if (ui.fIndex < 0 || ui.fIndex >= ui.formulas.length) ui.fIndex = ui.formulas.length - 1;
    ui.hints = ui.fIndex >= 0 ? C.hints(ui.formulas[ui.fIndex].inner) : [];
    if (ui.hIndex >= ui.hints.length) ui.hIndex = -1;
  }

  function enter() {
    ui.fIndex = -1; ui.hIndex = -1; ui.path = []; ui.pending = null;
    loadFormulas(ui.md);
    if (!ui.formulas.length) {
      ui.mode = "idle"; render();
      say(C.T("The board has no formulas yet. Dictate one first.", "El pizarrón no tiene fórmulas todavía. Dicta una primero."));
      return;
    }
    ui.mode = "hints"; render();
    say(C.T("Board. Say a number to choose, or press button two to step through and hold button one to choose.", "Pizarrón. Di un número para elegir, o pulsa el botón dos para recorrer y mantén el uno para elegir."));
  }

  function exit() {
    ui.mode = "idle"; ui.hIndex = -1; ui.path = []; ui.pending = null;
    render();
  }

  function selectHint(n) {
    if (n < 1 || n > ui.hints.length) { say(C.T("There is no " + n + ". There are " + ui.hints.length + ".", "No hay " + n + ". Hay " + ui.hints.length + ".")); return false; }
    ui.hIndex = n - 1;
    return true;
  }

  function openMenu() {
    ui.mode = "menu"; ui.path = [C.MENU]; ui.mIndex = 0; render();
    say(C.T("Chosen " + (ui.hIndex + 1) + ". " + C.label(C.MENU[0]) + ". Press button two to move on, hold button one to choose, or say what you want.", "Elegido " + (ui.hIndex + 1) + ". " + C.label(C.MENU[0]) + ". Pulsa el dos para pasar, mantén el uno para elegir, o di lo que quieres."));
  }

  function write(newLatex) {
    const f = ui.formulas[ui.fIndex];
    ui.undo.push(ui.md);
    const md = ui.md.slice(0, f.start) + newLatex + ui.md.slice(f.end);
    ui.md = md;
    fetch("/doc/pizarron/pizarron.md", { method: "PUT", headers: { "Content-Type": "text/markdown; charset=utf-8" }, body: md }).catch(() => say(C.T("I could not save.", "No pude guardar.")));
    ui.hIndex = -1; ui.pending = null; ui.path = [];
    loadFormulas(md);
    ui.mode = "hints"; render();
  }

  function runAction(name) {
    if (name === "exit") { exit(); say(C.T("Board closed. Hold button two to come back.", "Pizarrón cerrado. Mantén el botón dos para volver.")); return; }
    if (name === "help") { say(C.T("Say a number to choose a part of the formula. Then say bar, hat, subscript, fraction, delete, or whatever you want to change. Say previous or next to change formula. Say exit to finish.", "Di un número para elegir una parte de la fórmula. Luego di barra, sombrero, subíndice, fracción, borrar, o lo que quieras cambiar. Di anterior o siguiente para cambiar de fórmula. Di salir para terminar.")); return; }
    if (name === "undo") {
      if (!ui.undo.length) { say(C.T("There is nothing to undo.", "No hay nada que deshacer.")); return; }
      const md = ui.undo.pop();
      ui.md = md;
      fetch("/doc/pizarron/pizarron.md", { method: "PUT", headers: { "Content-Type": "text/markdown; charset=utf-8" }, body: md }).catch(() => {});
      ui.hIndex = -1; ui.path = []; loadFormulas(md); ui.mode = "hints"; render();
      say(C.T("Undone.", "Deshecho.")); return;
    }
    if (name === "prevFormula" || name === "nextFormula") {
      if (!ui.formulas.length) return;
      ui.fIndex = (ui.fIndex + (name === "nextFormula" ? 1 : ui.formulas.length - 1)) % ui.formulas.length;
      ui.hIndex = -1; ui.path = []; loadFormulas(ui.md); ui.mode = "hints"; render();
      say(C.T("Formula " + (ui.fIndex + 1) + " of " + ui.formulas.length + ", with " + ui.hints.length + " parts.", "Fórmula " + (ui.fIndex + 1) + " de " + ui.formulas.length + ", con " + ui.hints.length + " partes.")); return;
    }
  }

  function chooseItem(it) {
    if (it.items) { ui.path.push(it.items); ui.mIndex = 0; ui.mode = "menu"; render(); say(C.label(it.items[0])); return; }
    if (it.action) { runAction(it.action); return; }
    if (ui.hIndex < 0) { say(C.T("First choose a part: say its number.", "Primero elige una parte: di su número.")); ui.mode = "hints"; render(); return; }
    if (it.needs) { ui.pending = it; ui.mode = "awaiting"; render(); say(C.T("Dictate ", "Dicta ") + C.needs(it) + "."); report(); return; }
    applyLeaf(it, "");
  }

  function applyLeaf(it, content) {
    const f = ui.formulas[ui.fIndex], h = ui.hints[ui.hIndex];
    write(C.applyOp(f.inner, h, it.op, content));
    say(C.label(it) + C.T(". Done.", ". Hecho."));
  }

  // ---- events from the loop ------------------------------------------------
  function onButton(button, gesture) {
    if (ui.mode === "hints" || ui.mode === "awaiting") {
      if (button === "no" && gesture === "short") {
        if (!ui.hints.length) { say(C.T("No parts.", "Sin partes.")); return; }
        ui.hIndex = (ui.hIndex + 1) % ui.hints.length; ui.mode = "hints"; ui.pending = null; render();
        say(String(ui.hIndex + 1));
      } else if (button === "talk" && gesture === "long") {
        if (ui.hIndex < 0) { say(C.T("First choose a part.", "Primero elige una parte.")); return; }
        openMenu();
      }
    } else if (ui.mode === "menu") {
      const items = ui.path[ui.path.length - 1];
      if (button === "no" && gesture === "short") {
        ui.mIndex = (ui.mIndex + 1) % items.length; render(); say(C.label(items[ui.mIndex]));
      } else if (button === "talk" && gesture === "long") {
        chooseItem(items[ui.mIndex]);
      }
    }
  }

  function onVoice(text) {
    const t = C.normalize(text);
    if (ui.mode === "menu" && (t === "atras" || t === "volver" || t === "back" || t === "go back")) {
      if (ui.path.length > 1) { ui.path.pop(); ui.mIndex = 0; render(); say(C.label(ui.path[ui.path.length - 1][0])); }
      else { ui.mode = "hints"; ui.path = []; render(); say(C.T("Parts.", "Partes.")); }
      return true;
    }
    const n = C.parseNumber(text);
    const item = C.findItem(text, ui.mode === "menu" ? ui.path[ui.path.length - 1] : []) || C.findItem(text, C.leaves(C.MENU)) || C.findItem(text, C.MENU);
    // A number selects only in a short utterance or next to a menu word; "cámbialo por dos x" is content.
    const short = t.split(" ").length <= 4;
    if (n !== null && (short || item) && !(item && item.id === "sq")) {
      if (!selectHint(n)) return true;
      if (item && !item.items && !item.action) { chooseItem(item); return true; }
      openMenu(); return true;
    }
    if (item) { chooseItem(item); return true; }
    return false; // the loop will treat it as a free-form edit if something is selected
  }

  function onLatex(latex) {
    if (ui.mode === "awaiting" && ui.pending) { applyLeaf(ui.pending, latex); return; }
    if (ui.hIndex >= 0) {
      const f = ui.formulas[ui.fIndex], h = ui.hints[ui.hIndex];
      write(C.applyOp(f.inner, h, "%c", latex));
      say(C.T("Changed.", "Cambiado.")); return;
    }
    say(C.T("Nothing is selected.", "No hay nada seleccionado."));
  }

  function handle(ev) {
    let handled = true;
    if (ev.type === "enter") enter();
    else if (ev.type === "exit") exit();
    else if (ev.type === "button") onButton(ev.button, ev.gesture);
    else if (ev.type === "voice") handled = onVoice(ev.text || "");
    else if (ev.type === "latex") onLatex(ev.text || "");
    ui.lastSeq = ev.seq;
    return handled;
  }

  window.BoardUI = {
    setText(md) { if (ui.mode !== "idle") { loadFormulas(md); render(); } else ui.md = md; },
    handle: handle,
    report: report,
    exit: exit,
    state: ui,
  };
  if (window.speechSynthesis) speechSynthesis.getVoices();
})();
