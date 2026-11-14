/* The OneButton screen: panels, the global ring, reading aloud, and event routing.
 *
 * Events from the loop (POST /event):
 *   {type:"config", panels:[...], desktop}   which panels exist; desktop: the computadora module is on
 *   {type:"panel", name}                show a panel
 *   {type:"menu"}                       open the global ring      {type:"exit"} close everything
 *   {type:"enter"}                      board editing (board.js)  {type:"latex", text}
 *   {type:"button", button, gesture}    {type:"voice", text}
 *   {type:"read", from?}                read the current panel aloud
 * A voice event that is a scroll ("baja", "al final del pizarrón") or names a panel is handled here.
 * The page reports {mode, panel, handled, seq_handled, ...} to POST /state after every event, and
 * tells the server on every poll whether it is the window in front (/status?f=1).
 */
(function () {
  "use strict";
  const C = window.BoardCore;

  const PANELS = {
    conversacion: { label: "Conversación", words: C.PANEL_WORDS.conversacion, doc: "conversacion.md" },
    pizarron:      { label: "Pizarrón", words: C.PANEL_WORDS.pizarron, doc: "pizarron/pizarron.md" },
    escritorio:   { label: "Escritorio", words: C.PANEL_WORDS.escritorio, doc: null },
  };

  const S = {
    panels: ["conversacion", "pizarron", "escritorio"],
    panel: "conversacion",
    layout: "tabs",
    desktop: false,          // the computadora module is on: a bare "baja" may be meant for another application
    pos: {},                 // tabs layout: where each panel was left
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

  // ---- scrolling ---------------------------------------------------------------
  // tabs layout: the window scrolls, so each panel's place is kept and put back when it is shown
  // again. wide layout: every panel scrolls on its own.
  const want = {};           // panel -> an element to bring to the top, or "end"; done once the panel is on screen
  function scrollerOf(name) { return S.layout === "wide" ? document.getElementById("panel-" + name) : document.scrollingElement; }
  function onScreen(name) { return S.layout === "wide" || S.panel === name; }
  function settle(name) {
    const w = want[name];
    if (!w || !onScreen(name)) return;
    delete want[name];
    const sc = scrollerOf(name);
    if (w === "end" || !w.isConnected) sc.scrollTop = sc.scrollHeight;
    else w.scrollIntoView({ block: "start" });
  }

  function scrollPanel(cmd) {
    if (cmd.panel && cmd.panel !== S.panel) showPanel(cmd.panel, true);
    const sc = scrollerOf(S.panel);
    const view = S.layout === "wide" ? sc.clientHeight : window.innerHeight - 150;   // less the tabs and the status line
    const max = Math.max(0, sc.scrollHeight - sc.clientHeight);
    const from = sc.scrollTop;
    let to = cmd.dir === "top" ? 0 : cmd.dir === "bottom" ? max : from + (cmd.dir === "down" ? 1 : -1) * cmd.steps * 0.8 * view;
    to = Math.max(0, Math.min(max, to));
    if (Math.abs(to - from) < 2) { say(cmd.dir === "down" || cmd.dir === "bottom" ? "Ya es el final." : "Ya es el principio."); return; }
    sc.scrollTo({ top: to, behavior: "smooth" });
  }

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
    want.conversacion = "end"; settle("conversacion");
  }

  // The first block of the pizarrón that differs from what was there before, so that something
  // just written is shown from its beginning and "baja" carries on from there.
  let boardBefore = null;
  function firstChange(el) {
    const now = Array.from(el.children).map(c => c.outerHTML);
    const before = boardBefore; boardBefore = now;
    if (!before) return null;
    let i = 0;
    while (i < now.length && i < before.length && now[i] === before[i]) i++;
    return i < now.length ? el.children[i] : null;
  }

  // fresh: the file changed on disk (as opposed to a redraw while a formula is being edited)
  function renderBoard(text, sel, fresh) {
    const el = document.getElementById("panel-pizarron");
    if (sel) { const f = sel.f, h = sel.h; text = text.slice(0, f.start) + C.highlight(f.inner, h, sel.color) + text.slice(f.end); }
    el.innerHTML = text.trim() ? mdToHtml(text) : "<p class='empty'>Pizarrón vacío. Pide algo con matemáticas y aparecerá aquí.</p>";
    typeset(el);
    if (sel) return;
    want.pizarron = (fresh && firstChange(el)) || "end"; settle("pizarron");
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
    const moved = name !== S.panel && S.layout !== "wide";
    if (moved) S.pos[S.panel] = document.scrollingElement.scrollTop;
    S.panel = name;
    document.querySelectorAll(".panel").forEach(p => p.classList.toggle("active", p.id === "panel-" + name));
    document.querySelectorAll("#tabs button").forEach(b => b.classList.toggle("active", b.dataset.panel === name));
    // Something new waiting in this panel wins; otherwise back to where it was left (the newest
    // end of the conversation and the pizarrón, the top of the manuscript, the first time).
    if (moved && !want[name]) document.scrollingElement.scrollTop = name in S.pos ? S.pos[name] : (name === "escritorio" ? 0 : 1e9);
    settle(name);
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
    if (S.panels.includes("pizarron")) items.push({ id: "board", label: "Editar fórmula", words: ["editar", "formula", "editar formula"], action: () => { closeRing(); showPanel("pizarron", true); S.mode = "board"; BoardUI.handle({ type: "enter", seq: S.lastSeq }); } });
    items.push({ id: "read", label: "Leer", words: ["leer", "lee", "leeme"], action: () => { closeRing(); startReading(); } });
    items.push({ id: "help", label: "Ayuda", words: ["ayuda"], action: () => { closeRing(); say("Di el nombre de un panel: conversación, pizarrón o escritorio. Di baja o sube para moverte por el panel, al principio o al final para ir a un extremo. Di editar fórmula para cambiar una fórmula por su número. Di leer para que te lea el panel. Pulsa el dos para pasar y mantén el uno para elegir. Mantén el dos para salir."); } });
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
    if (S.panel === "pizarron") return blocksOf(S.docs["pizarron/pizarron.md"] || "");
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
    // idle: scrolling, a panel by its name, or "lee ..." are handled here; sentences go to Claude
    const scr = C.parseScroll(text, S.panels);
    if (scr) {
      // With the computadora module on, a bare "baja" is for whatever application is in front. It is
      // for this page when the page is in front, or when the panel is named ("baja el pizarrón").
      if (!scr.panel && S.desktop && !document.hasFocus()) return false;
      scrollPanel(scr); return true;
    }
    const p = C.parsePanel(text, S.panels);
    if (p) { showPanel(p); return true; }
    if (t.split(" ").length <= 4 && /\b(lee|leer|leeme)\b/.test(t)) { startReading(C.parseNumber(text)); return true; }
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
    if (ev.type === "config") { if (Array.isArray(ev.panels) && ev.panels.length) S.panels = ev.panels.filter(p => PANELS[p]); if ("desktop" in ev) S.desktop = !!ev.desktop; renderTabs(); applyLook(ev); if (!S.panels.includes(S.panel)) showPanel(S.panels[0], true); }
    else if (ev.type === "panel") showPanel(ev.name);
    else if (ev.type === "menu") { if (S.mode === "board") { BoardUI.exit(); } if (S.mode === "reading") stopReading(""); openRing(); }
    else if (ev.type === "exit") { if (S.mode === "board") BoardUI.exit(); if (S.mode === "reading") stopReading(""); closeRing(); S.mode = "idle"; }
    else if (ev.type === "enter") { showPanel("pizarron", true); S.mode = "board"; handled = BoardUI.handle(ev); }
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
    fetch("/status?f=" + (document.hasFocus() ? 1 : 0), { cache: "no-store" }).then(r => r.json()).then(st => {
      failures = 0; document.getElementById("bar").className = "";
      if (st.manuscript !== S.manuscript) { S.manuscript = st.manuscript; renderManuscript(); }
      const changed = [];
      for (const path in st.docs) if (st.docs[path] !== S.mtimes[path]) { changed.push(path); S.mtimes[path] = st.docs[path]; }
      const loads = changed.map(path => fetch("/doc/" + path, { cache: "no-store" }).then(r => r.ok ? r.text() : "").then(t => { S.docs[path] = t; return path; }));
      Promise.all(loads).then(paths => {
        if (paths.includes("conversacion.md")) renderConversation();
        if (paths.includes("pizarron/pizarron.md")) { BoardUI.setText(S.docs["pizarron/pizarron.md"]); if (S.mode !== "board") renderBoard(S.docs["pizarron/pizarron.md"], null, true); }
        if (S.manuscript && paths.includes(S.manuscript)) renderManuscript();
        autoSwitch(paths);
      });
      if ((st.seq || 0) > S.lastSeq) {
        fetch("/events?after=" + S.lastSeq, { cache: "no-store" }).then(r => r.json()).then(list => { for (const ev of list) handle(ev); }).catch(() => {});
      }
    }).catch(() => { if (++failures > 3) document.getElementById("bar").className = "stale"; });
  }

  // Show what just changed. Something written on the pizarrón or in the manuscript is shown at once,
  // while Claude is still working; a finished reply shows the conversation unless the turn wrote
  // somewhere else. What is already there when the page opens is not a change.
  let loaded = false;
  const written = new Set();
  function autoSwitch(paths) {
    if (!loaded) { loaded = true; return; }
    if (S.mode !== "idle" || !paths.length) return;
    if (paths.includes("pizarron/pizarron.md") && S.panels.includes("pizarron")) { written.add("pizarron"); showPanel("pizarron", true); }
    if (S.manuscript && paths.includes(S.manuscript) && S.panels.includes("escritorio")) { written.add("escritorio"); showPanel("escritorio", true); }
    if (paths.includes("conversacion.md")) {
      const conv = S.docs["conversacion.md"] || "";
      const replied = /## \d\d:\d\d Asistente\n?[\s\S]*$/.test(conv.split(/^(?=## )/m).pop() || "");
      if (replied) {
        if (!written.size) showPanel("conversacion", true);
        written.clear();
      }
    }
  }

  document.addEventListener("click", e => { const b = e.target.closest("#tabs button"); if (b) showPanel(b.dataset.panel, true); });
  renderTabs(); showPanel("conversacion", true); renderManuscript();
  if (window.speechSynthesis) speechSynthesis.getVoices();
  tick(); setInterval(tick, 300);
})();
