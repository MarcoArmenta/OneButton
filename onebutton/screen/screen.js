/* The OneButton screen: panels, the global ring, reading aloud, and event routing.
 *
 * Events from the loop (POST /event):
 *   {type:"config", panels:[...]}       which panels exist
 *   {type:"panel", name}                show a panel
 *   {type:"menu"}                       open the global ring      {type:"exit"} close everything
 *   {type:"enter"}                      board editing (board.js)  {type:"latex", text}
 *   {type:"button", button, gesture}    {type:"voice", text}
 *   {type:"read", from?}                read the current panel aloud
 * The page reports {mode, panel, handled, seq_handled, ...} to POST /state after every event.
 */
(function () {
  "use strict";
  const C = window.BoardCore;

  const PANELS = {
    conversacion: { label: "Conversación", words: ["conversacion", "charla", "respuesta", "respuestas"], doc: "conversacion.md" },
    pizarra:      { label: "Pizarra", words: ["pizarra", "pizarron", "formulas"], doc: "pizarra/pizarra.md" },
    escritorio:   { label: "Escritorio", words: ["escritorio", "escrito", "manuscrito", "articulo", "texto"], doc: null },
  };

  const S = {
    panels: ["conversacion", "pizarra", "escritorio"],
    panel: "conversacion",
    layout: "tabs",
    mode: "idle",            // idle | menu | reading | board (board.js owns its own modes)
    ring: [], ringIndex: 0,
    docs: {},                // path -> text
    mtimes: {},              // path -> mtime_ns
    manuscript: null,        // path of the current manuscript, from /status
    reading: null,           // {blocks:[...], i}
    lastSeq: 0,
    lastConvChange: 0,
  };

  // ---- speech ----------------------------------------------------------------
  function say(text) {
    try {
      if (!window.speechSynthesis) return;
      speechSynthesis.cancel();
      const u = new SpeechSynthesisUtterance(text);
      u.lang = "es-MX";
      const voices = speechSynthesis.getVoices();
      const v = voices.find(x => /^es/.test(x.lang) && /natural|neural/i.test(x.name)) || voices.find(x => /^es/.test(x.lang));
      if (v) u.voice = v;
      speechSynthesis.speak(u);
    } catch (e) {}
    const el = document.getElementById("status");
    if (el) el.textContent = text;
  }
  window.screenSay = say;

  // ---- rendering -------------------------------------------------------------
  function protectMath(md) {
    const slots = [];
    md = md.replace(/\$\$[\s\S]+?\$\$|\\\[[\s\S]+?\\\]|\$[^$\n]+?\$|\\\([\s\S]+?\\\)/g, m => { slots.push(m); return "\u0000" + (slots.length - 1) + "\u0000"; });
    return { md, restore: html => html.replace(/\u0000(\d+)\u0000/g, (_, i) => slots[+i].replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")) };
  }
  function mdToHtml(text) {
    if (!window.marked) return "<pre>" + text.replace(/&/g, "&amp;").replace(/</g, "&lt;") + "</pre>";
    const p = protectMath(text);
    return p.restore(marked.parse(p.md, { mangle: false, headerIds: false }));
  }
  function typeset(el) {
    if (!window.renderMathInElement) return;
    renderMathInElement(el, { delimiters: [
      { left: "$$", right: "$$", display: true }, { left: "\\[", right: "\\]", display: true },
      { left: "$", right: "$", display: false }, { left: "\\(", right: "\\)", display: false }],
      throwOnError: false, strict: "ignore" });
  }

  function blocksOf(text) {
    // Same rule as modules/scribe/blocks.py: blocks are separated by blank lines;
    // fenced code and $$ display math stay whole even if they contain blank lines.
    const out = []; let cur = []; let inCode = false, inMath = false;
    const flush = () => { if (cur.some(x => x.trim())) out.push(cur.join("\n")); cur = []; };
    for (const line of text.split("\n")) {
      const t = line.trim();
      if (t.startsWith("```")) { inCode = !inCode; cur.push(line); if (!inCode) flush(); continue; }
      if (inCode) { cur.push(line); continue; }
      if (t === "$$") { inMath = !inMath; cur.push(line); if (!inMath) flush(); continue; }
      if (inMath) { cur.push(line); continue; }
      if (!t) { flush(); continue; }
      cur.push(line);
    }
    flush();
    return out;
  }
  window.blocksOf = blocksOf;

  function renderConversation() {
    const el = document.getElementById("panel-conversacion");
    const text = S.docs["conversacion.md"] || "";
    const parts = text.split(/^(?=## )/m).filter(x => x.trim()).slice(-24);
    el.innerHTML = parts.map(part => {
      const m = part.match(/^## (\d\d:\d\d) (Tú|Asistente)\n?([\s\S]*)$/);
      if (!m) return "<div class='turn'>" + mdToHtml(part) + "</div>";
      return "<div class='turn " + (m[2] === "Tú" ? "me" : "bot") + "'><div class='who'>" + m[2] + " <span>" + m[1] + "</span></div>" + mdToHtml(m[3]) + "</div>";
    }).join("") || "<p class='empty'>Pulsa el botón y habla. Las respuestas aparecen aquí.</p>";
    typeset(el);
    el.lastElementChild && el.lastElementChild.scrollIntoView({ block: "end" });
  }

  function renderBoard(text, sel) {
    const el = document.getElementById("panel-pizarra");
    if (sel) { const f = sel.f, h = sel.h; text = text.slice(0, f.start) + C.highlight(f.inner, h, sel.color) + text.slice(f.end); }
    el.innerHTML = text.trim() ? mdToHtml(text) : "<p class='empty'>Pizarra vacía. Pide algo con matemáticas y aparecerá aquí.</p>";
    typeset(el);
    if (!sel && el.lastElementChild) el.lastElementChild.scrollIntoView({ block: "end" });
  }
  window.renderBoardWithHighlight = (text, sel) => renderBoard(text, sel);

  function renderManuscript() {
    const el = document.getElementById("panel-escritorio");
    const text = S.manuscript ? (S.docs[S.manuscript] || "") : "";
    if (!S.manuscript) { el.innerHTML = "<p class='empty'>No hay ningún escrito abierto. Di: nuevo escrito, o abre el escrito tal.</p>"; return; }
    const blocks = blocksOf(text);
    el.innerHTML = blocks.map((b, i) => "<div class='block' data-n='" + (i + 1) + "'><span class='n'>" + (i + 1) + "</span>" + mdToHtml(b) + "</div>").join("")
      || "<p class='empty'>El escrito está vacío. Dicta una idea y la desarrollo.</p>";
    typeset(el);
    if (S.reading) highlightBlock(S.reading.i);
  }

  function highlightBlock(i) {
    document.querySelectorAll("#panel-escritorio .block").forEach(b => b.classList.toggle("current", +b.dataset.n === i + 1));
    const cur = document.querySelector("#panel-escritorio .block.current");
    if (cur) cur.scrollIntoView({ block: "center", behavior: "smooth" });
  }

  function applyLook(cfg) {
    if (cfg.theme) document.documentElement.setAttribute("data-theme", cfg.theme);
    if (cfg.font_size) document.documentElement.style.setProperty("--fs", cfg.font_size + "px");
    if (cfg.layout) { S.layout = cfg.layout; document.body.classList.toggle("layout-wide", cfg.layout === "wide"); }
    document.querySelectorAll(".panel").forEach(p => p.classList.toggle("hidden-panel", !S.panels.includes(p.id.replace("panel-", ""))));
  }

  function showPanel(name, silent) {
    if (!PANELS[name] || !S.panels.includes(name)) return;
    S.panel = name;
    document.querySelectorAll(".panel").forEach(p => p.classList.toggle("active", p.id === "panel-" + name));
    document.querySelectorAll("#tabs button").forEach(b => b.classList.toggle("active", b.dataset.panel === name));
    if (!silent) say(PANELS[name].label + ".");
  }

  function renderTabs() {
    const tabs = document.getElementById("tabs");
    tabs.innerHTML = S.panels.map(n => "<button data-panel='" + n + "' class='" + (n === S.panel ? "active" : "") + "'>" + PANELS[n].label + "</button>").join("");
  }

  // ---- ring --------------------------------------------------------------------
  function ringItems() {
    const items = [];
    for (const n of S.panels) items.push({ id: "panel:" + n, label: PANELS[n].label, words: PANELS[n].words, action: () => { closeRing(); showPanel(n); } });
    if (S.panels.includes("pizarra")) items.push({ id: "board", label: "Editar fórmula", words: ["editar", "formula", "editar formula"], action: () => { closeRing(); showPanel("pizarra", true); S.mode = "board"; BoardUI.handle({ type: "enter", seq: S.lastSeq }); } });
    items.push({ id: "read", label: "Leer", words: ["leer", "lee", "leeme"], action: () => { closeRing(); startReading(); } });
    items.push({ id: "help", label: "Ayuda", words: ["ayuda"], action: () => { closeRing(); say("Di el nombre de un panel: conversación, pizarra o escritorio. Di editar fórmula para cambiar una fórmula por su número. Di leer para que te lea el panel. Pulsa el dos para pasar y mantén el uno para elegir. Mantén el dos para salir."); } });
    items.push({ id: "exit", label: "Salir", words: ["salir", "cerrar", "listo"], action: () => { closeRing(); } });
    return items;
  }

  function openRing() {
    S.mode = "menu"; S.ring = ringItems(); S.ringIndex = 0; drawRing();
    say("Menú. " + S.ring[0].label + ". Di a dónde quieres ir, o pulsa el dos para pasar y mantén el uno para elegir.");
  }
  function closeRing() {
    S.mode = "idle"; S.ring = []; drawRing();
  }
  function drawRing() {
    const el = document.getElementById("ring");
    el.style.display = S.mode === "menu" ? "block" : "none";
    el.innerHTML = "";
    if (S.mode !== "menu") return;
    const N = S.ring.length;
    S.ring.forEach((it, i) => {
      const d = document.createElement("div");
      d.className = "ring-item" + (i === S.ringIndex ? " current" : "");
      d.textContent = it.label;
      const ang = (i / N) * 2 * Math.PI - Math.PI / 2;
      d.style.left = (50 + 38 * Math.cos(ang)) + "%";
      d.style.top = (50 + 40 * Math.sin(ang)) + "%";
      el.appendChild(d);
    });
  }

  // ---- reading aloud -------------------------------------------------------------
  function readableBlocks() {
    if (S.panel === "escritorio" && S.manuscript) return blocksOf(S.docs[S.manuscript] || "");
    if (S.panel === "pizarra") return blocksOf(S.docs["pizarra/pizarra.md"] || "");
    const parts = (S.docs["conversacion.md"] || "").split(/^(?=## )/m).filter(x => x.trim());
    const last = parts.reverse().find(p => /^## \d\d:\d\d Asistente/.test(p));
    return last ? blocksOf(last.replace(/^## .*\n?/, "")) : [];
  }
  function spoken(block) {
    return block.replace(/\$\$[\s\S]+?\$\$/g, " fórmula. ").replace(/\$[^$\n]+?\$/g, " fórmula ")
      .replace(/^#+\s*/gm, "").replace(/[*_`#>]/g, "").replace(/\s+/g, " ").trim();
  }
  function startReading(from) {
    const blocks = readableBlocks();
    if (!blocks.length) { say("No hay nada que leer aquí."); return; }
    S.mode = "reading"; S.reading = { blocks, i: Math.max(0, Math.min(blocks.length - 1, (from || 1) - 1)) };
    readCurrent();
  }
  function readCurrent() {
    const r = S.reading; if (!r) return;
    if (S.panel === "escritorio") highlightBlock(r.i);
    try {
      speechSynthesis.cancel();
      const u = new SpeechSynthesisUtterance((r.i + 1) + ". " + spoken(r.blocks[r.i]));
      u.lang = "es-MX";
      const voices = speechSynthesis.getVoices();
      const v = voices.find(x => /^es/.test(x.lang) && /natural|neural/i.test(x.name)) || voices.find(x => /^es/.test(x.lang));
      if (v) u.voice = v;
      u.onend = () => { if (S.mode === "reading" && S.reading === r) { if (r.i + 1 < r.blocks.length) { r.i++; readCurrent(); } else stopReading("Fin."); } };
      speechSynthesis.speak(u);
    } catch (e) { stopReading(""); }
    const el = document.getElementById("status"); if (el) el.textContent = "Leyendo " + (r.i + 1) + " de " + r.blocks.length + ". Botón dos: siguiente. Mantén el dos: parar.";
  }
  function stopReading(msg) {
    try { speechSynthesis.cancel(); } catch (e) {}
    S.mode = "idle"; S.reading = null;
    document.querySelectorAll("#panel-escritorio .block.current").forEach(b => b.classList.remove("current"));
    if (msg) say(msg);
  }

  // ---- events ----------------------------------------------------------------------
  function onVoice(text) {
    const t = C.normalize(text);
    if (S.mode === "menu") {
      const it = C.findItem(text, S.ring);
      if (it) { it.action(); return true; }
      const n = C.parseNumber(text);
      if (n !== null && n >= 1 && n <= S.ring.length) { S.ring[n - 1].action(); return true; }
      return false;
    }
    if (S.mode === "reading") {
      const n = C.parseNumber(text);
      if (n !== null && S.reading && n >= 1 && n <= S.reading.blocks.length) { S.reading.i = n - 1; readCurrent(); return true; }
      if (/\b(para|basta|alto|stop|silencio)\b/.test(t)) { stopReading("Parado."); return true; }
      return false;
    }
    // idle: a short utterance naming a panel, or "lee ...", is handled here; sentences go to Claude
    if (t.split(" ").length > 4) return false;
    for (const n of S.panels) if (C.findItem(text, [{ words: PANELS[n].words }])) { showPanel(n); return true; }
    if (/\b(lee|leer|leeme)\b/.test(t)) { startReading(C.parseNumber(text)); return true; }
    return false;
  }

  function onButton(button, gesture) {
    if (S.mode === "menu") {
      if (button === "no" && gesture === "short") { S.ringIndex = (S.ringIndex + 1) % S.ring.length; drawRing(); say(S.ring[S.ringIndex].label); }
      else if (button === "talk" && gesture === "long") S.ring[S.ringIndex].action();
      return;
    }
    if (S.mode === "reading") {
      const r = S.reading;
      if (button === "no" && gesture === "short") { if (r.i + 1 < r.blocks.length) { r.i++; readCurrent(); } else stopReading("Fin."); }
      else if (button === "talk" && gesture === "long") { readCurrent(); }
      return;
    }
  }

  function report(extra) {
    const b = BoardUI.state;
    const st = Object.assign({
      mode: S.mode === "board" ? b.mode : S.mode,
      panel: S.panel,
      awaiting: (S.mode === "board" && b.mode === "awaiting") ? (b.pending && b.pending.needs) : null,
      selected: S.mode === "board" && b.hIndex >= 0,
      formula: S.mode === "board" ? b.fIndex : null,
      hint: (S.mode === "board" && b.hIndex >= 0) ? b.hints[b.hIndex].n : null,
      seq_handled: S.lastSeq,
    }, extra || {});
    fetch("/state", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(st) }).catch(() => {});
  }

  function handle(ev) {
    let handled = true;
    if (ev.type === "config") { if (Array.isArray(ev.panels) && ev.panels.length) S.panels = ev.panels.filter(p => PANELS[p]); renderTabs(); applyLook(ev); if (!S.panels.includes(S.panel)) showPanel(S.panels[0], true); }
    else if (ev.type === "panel") showPanel(ev.name);
    else if (ev.type === "menu") { if (S.mode === "board") { BoardUI.exit(); } if (S.mode === "reading") stopReading(""); openRing(); }
    else if (ev.type === "exit") { if (S.mode === "board") BoardUI.exit(); if (S.mode === "reading") stopReading(""); closeRing(); S.mode = "idle"; }
    else if (ev.type === "enter") { showPanel("pizarra", true); S.mode = "board"; handled = BoardUI.handle(ev); }
    else if (ev.type === "read") startReading(ev.from);
    else if (S.mode === "board") {
      handled = BoardUI.handle(ev);
      if (BoardUI.state.mode === "idle") S.mode = "idle";
    }
    else if (ev.type === "button") onButton(ev.button, ev.gesture);
    else if (ev.type === "voice") handled = onVoice(ev.text || "");
    else if (ev.type === "latex") handled = false;
    S.lastSeq = ev.seq;
    if (S.mode === "board") BoardUI.state.lastSeq = ev.seq;
    report({ handled });
  }

  // ---- polling ---------------------------------------------------------------------
  let failures = 0;
  function tick() {
    fetch("/status", { cache: "no-store" }).then(r => r.json()).then(st => {
      failures = 0; document.getElementById("bar").className = "";
      if (st.manuscript !== S.manuscript) { S.manuscript = st.manuscript; renderManuscript(); }
      const changed = [];
      for (const path in st.docs) if (st.docs[path] !== S.mtimes[path]) { changed.push(path); S.mtimes[path] = st.docs[path]; }
      const loads = changed.map(path => fetch("/doc/" + path, { cache: "no-store" }).then(r => r.ok ? r.text() : "").then(t => { S.docs[path] = t; return path; }));
      Promise.all(loads).then(paths => {
        if (paths.includes("conversacion.md")) renderConversation();
        if (paths.includes("pizarra/pizarra.md")) { BoardUI.setText(S.docs["pizarra/pizarra.md"]); if (S.mode !== "board") renderBoard(S.docs["pizarra/pizarra.md"]); }
        if (S.manuscript && paths.includes(S.manuscript)) renderManuscript();
        autoSwitch(paths);
      });
      if ((st.seq || 0) > S.lastSeq) {
        fetch("/events?after=" + S.lastSeq, { cache: "no-store" }).then(r => r.json()).then(list => { for (const ev of list) handle(ev); }).catch(() => {});
      }
    }).catch(() => { if (++failures > 3) document.getElementById("bar").className = "stale"; });
  }

  // Show what just changed: a formula written during a turn beats the reply text; a reply beats nothing.
  const turnChanges = new Set();
  function autoSwitch(paths) {
    if (S.mode !== "idle" || !paths.length) return;
    for (const p of paths) if (p !== "conversacion.md" && p !== "escritos/actual") turnChanges.add(p);
    if (paths.includes("conversacion.md")) {
      const conv = S.docs["conversacion.md"] || "";
      const replied = /## \d\d:\d\d Asistente\n?[\s\S]*$/.test(conv.split(/^(?=## )/m).pop() || "");
      if (replied) {
        if (S.manuscript && turnChanges.has(S.manuscript)) showPanel("escritorio", true);
        else if (turnChanges.has("pizarra/pizarra.md")) showPanel("pizarra", true);
        else showPanel("conversacion", true);
        turnChanges.clear();
      }
    }
  }

  document.addEventListener("click", e => { const b = e.target.closest("#tabs button"); if (b) showPanel(b.dataset.panel, true); });
  renderTabs(); showPanel("conversacion", true); renderManuscript();
  if (window.speechSynthesis) speechSynthesis.getVoices();
  tick(); setInterval(tick, 300);
})();
