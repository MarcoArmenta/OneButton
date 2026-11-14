// End-to-end: real server + headless Chromium. Args: <workspace> <port>
// Drives the board with the same events the loop posts, and checks the file on disk.
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");
const assert = require("assert");

const [ws, port] = [process.argv[2], process.argv[3]];
const base = `http://127.0.0.1:${port}`;
const file = path.join(ws, "pizarron", "pizarron.md");

async function post(ev) {
  const r = await fetch(base + "/event", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(ev) });
  return (await r.json()).seq;
}
async function waitHandled(seq) {
  for (let i = 0; i < 40; i++) {
    const st = await (await fetch(base + "/state")).json();
    if ((st.seq_handled || 0) >= seq) return st;
    await new Promise(r => setTimeout(r, 100));
  }
  throw new Error("viewer did not handle event " + seq);
}
let p;
const active = () => p.locator(".panel.active").getAttribute("id");
const scrollTop = () => p.evaluate(() => document.scrollingElement.scrollTop);
const panelTop = () => p.evaluate(() => document.getElementById("panel-pizarron").scrollTop);
// a voice event, then wait for the smooth scroll it may have started to come to rest
async function say(text) {
  const st = await waitHandled(await post({ type: "voice", text }));
  let last = -1;
  for (let i = 0; i < 40; i++) {
    await p.waitForTimeout(150);
    const now = (await scrollTop()) + (await panelTop());
    if (now === last) break;
    last = now;
  }
  return st;
}
async function waitFile(pred) {
  for (let i = 0; i < 40; i++) {
    const t = fs.readFileSync(file, "utf8");
    if (pred(t)) return t;
    await new Promise(r => setTimeout(r, 100));
  }
  throw new Error("file never matched: " + fs.readFileSync(file, "utf8"));
}

(async () => {
  fs.writeFileSync(file, "# Pizarrón\n\n## Prueba\n\nSea $x_i^2 + y$ y luego\n\n$$\\frac{a+b}{c}$$\n");
  const b = await chromium.launch();
  p = await b.newPage();
  const errors = []; p.on("pageerror", e => errors.push(String(e)));
  await p.goto(base + "/", { waitUntil: "load" });
  await p.waitForTimeout(800);

  // panels: config, conversation rendering, voice switching, ring menu
  await waitHandled(await post({ type: "config", panels: ["conversacion", "pizarron", "escritorio"], theme: "glasses", layout: "wide", font_size: 30 }));
  assert.strictEqual(await p.locator("#tabs button").count(), 3);
  assert.strictEqual(await p.locator(".panel:visible").count(), 3, "wide layout shows every panel");
  assert.strictEqual(await p.evaluate(() => getComputedStyle(document.body).backgroundColor), "rgb(0, 0, 0)", "glasses theme is true black");
  assert.strictEqual(await p.evaluate(() => getComputedStyle(document.body).fontSize), "30px");
  await waitHandled(await post({ type: "config", panels: ["conversacion", "pizarron", "escritorio"], layout: "tabs" }));
  assert.strictEqual(await p.locator(".panel:visible").count(), 1, "tabs layout shows one panel");
  fs.writeFileSync(path.join(ws, "conversacion.md"), "## 10:00 Tú\n\nhola\n\n## 10:00 Asistente\n\nHola, **José**. $x^2$\n\n");
  await p.waitForTimeout(900);
  assert.ok((await p.locator("#panel-conversacion .turn").count()) === 2, "conversation turns rendered");
  assert.strictEqual(await active(), "panel-conversacion", "a reply shows the conversation; the board that was already there is not news");
  let st = await waitHandled(await post({ type: "voice", text: "pizarrón" }));
  assert.strictEqual(st.panel, "pizarron"); assert.strictEqual(st.handled, true);
  st = await waitHandled(await post({ type: "voice", text: "escribe en el pizarrón la suma de los primeros n números" }));
  assert.strictEqual(st.handled, false, "long sentences are not panel switches");
  await waitHandled(await post({ type: "voice", text: "conversación" }));
  for (const text of ["borra el pizarrón", "pizarrón nuevo", "nuevo escrito"]) {
    st = await waitHandled(await post({ type: "voice", text }));
    assert.strictEqual(st.handled, false, text + " is a request to Claude, not a panel switch");
    assert.strictEqual(st.panel, "conversacion");
  }
  st = await waitHandled(await post({ type: "voice", text: "ve al pizarrón" }));
  assert.strictEqual(st.panel, "pizarron"); assert.strictEqual(st.handled, true);
  st = await waitHandled(await post({ type: "menu" }));
  assert.strictEqual(st.mode, "menu");
  await post({ type: "button", button: "no", gesture: "short" });          // -> Pizarrón
  await post({ type: "button", button: "no", gesture: "short" });          // -> Escritorio
  st = await waitHandled(await post({ type: "button", button: "talk", gesture: "long" }));
  assert.strictEqual(st.mode, "idle"); assert.strictEqual(st.panel, "escritorio");
  // manuscript with numbered blocks, then reading mode driven by button 2
  fs.mkdirSync(path.join(ws, "escritos", "tesis"), { recursive: true });
  fs.writeFileSync(path.join(ws, "escritos", "tesis", "manuscrito.md"), "# Tesis\n\nUno.\n\nDos.\n\nTres.\n");
  fs.writeFileSync(path.join(ws, "escritos", "actual"), "tesis");
  await p.waitForTimeout(900);
  assert.strictEqual(await p.locator("#panel-escritorio .block").count(), 4);
  st = await waitHandled(await post({ type: "voice", text: "lee el dos" }));
  assert.strictEqual(st.mode, "reading");
  assert.strictEqual((await p.locator("#panel-escritorio .block.current").innerText()).replace(/\s+/g, ""), "2Uno.");
  await waitHandled(await post({ type: "button", button: "no", gesture: "short" }));
  assert.strictEqual((await p.locator("#panel-escritorio .block.current").innerText()).replace(/\s+/g, ""), "3Dos.");
  st = await waitHandled(await post({ type: "exit" }));
  assert.strictEqual(st.mode, "idle");
  await waitHandled(await post({ type: "voice", text: "pizarrón" }));

  // enter: hints for the last formula
  st = await waitHandled(await post({ type: "enter" }));
  assert.strictEqual(st.mode, "hints");
  assert.strictEqual(st.formula, 1);
  assert.ok((await p.locator(".hint").count()) >= 4, "hint chips rendered");

  // step with button 2, open menu with a held button 1, step to Decorar > barra, apply
  await post({ type: "button", button: "no", gesture: "short" });            // select 1: \frac{a+b}{c}
  await post({ type: "button", button: "no", gesture: "short" });            // select 2: a
  st = await waitHandled(await post({ type: "button", button: "talk", gesture: "long" }));
  assert.strictEqual(st.mode, "menu");
  assert.strictEqual((await p.locator(".ring-item.current").innerText()), "Decorar");
  await post({ type: "button", button: "talk", gesture: "long" });           // into Decorar
  st = await waitHandled(await post({ type: "button", button: "talk", gesture: "long" }));  // barra
  await waitFile(t => t.includes("\\frac{\\bar{a}+b}{c}"));

  // voice fast path: "sombrero en el dos" on the previous formula
  await waitHandled(await post({ type: "voice", text: "fórmula anterior" }));
  st = await waitHandled(await post({ type: "voice", text: "sombrero en el dos" }));
  await waitFile(t => t.includes("$\\hat{x}_i^2 + y$"));

  // content path: "subíndice" on hint 1 asks for content; the loop then posts latex
  st = await waitHandled(await post({ type: "voice", text: "subíndice en el uno" }));
  assert.strictEqual(st.mode, "awaiting");
  assert.strictEqual(st.awaiting, "el subíndice");
  await waitHandled(await post({ type: "latex", text: "jk" }));
  await waitFile(t => t.includes("{\\hat{x}_i^2}_{jk}"));

  // unmatched free text with a selection is reported unhandled so the loop can convert it
  await waitHandled(await post({ type: "voice", text: "tres" }));
  st = await waitHandled(await post({ type: "voice", text: "cámbialo por una suma" }));
  assert.strictEqual(st.handled, false);
  assert.strictEqual(st.selected, true);
  await waitHandled(await post({ type: "latex", text: "\\sum_k a_k" }));
  await waitFile(t => t.includes("\\sum_k a_k"));

  // undo and exit
  await waitHandled(await post({ type: "voice", text: "deshacer" }));
  await waitFile(t => !t.includes("\\sum_k a_k"));
  st = await waitHandled(await post({ type: "exit" }));
  assert.strictEqual(st.mode, "idle");
  assert.strictEqual((await p.locator("#board-panel").isVisible()), false);

  // something written on the board while another panel is showing: the board appears at once, at what is new
  await say("conversación");
  assert.strictEqual(await active(), "panel-conversacion");
  const steps = Array.from({ length: 60 }, (_, i) => "Paso " + (i + 1) + ": $a_{" + i + "}$").join("\n\n");
  fs.writeFileSync(file, fs.readFileSync(file, "utf8") + "\n## Nuevo\n\n" + steps + "\n");
  await p.waitForTimeout(900);
  assert.strictEqual(await active(), "panel-pizarron", "the board is shown as soon as it is written");
  const top = await p.evaluate(() => [...document.querySelectorAll("#panel-pizarron h2")].find(h => h.textContent === "Nuevo").getBoundingClientRect().top);
  assert.ok(top > 60 && top < 200, "what is new starts at the top of the screen, below the tabs: " + top);

  // moving around by voice
  const y0 = await scrollTop();
  st = await say("baja");
  assert.strictEqual(st.handled, true);
  const y1 = await scrollTop();
  assert.ok(y1 > y0 + 200, "baja moves most of a screen: " + y0 + " -> " + y1);
  await say("sube un poco");
  const y2 = await scrollTop();
  assert.ok(y2 < y1 && y2 > y0, "sube un poco moves back less than a screen");
  await say("al final");
  const end = await scrollTop();
  assert.ok(end > y1 && Math.abs(end - await p.evaluate(() => document.scrollingElement.scrollHeight - document.scrollingElement.clientHeight)) < 3);
  st = await say("baja");
  assert.strictEqual(st.handled, true); assert.strictEqual(await scrollTop(), end, "nothing below the end");
  await say("al principio del pizarrón");
  assert.strictEqual(await scrollTop(), 0);
  await say("baja dos");
  const mid = await scrollTop();
  assert.ok(mid > 400);
  await say("conversación");
  await say("pizarrón");
  assert.ok(Math.abs(await scrollTop() - mid) < 3, "a panel comes back where it was left");
  st = await say("sube el volumen");
  assert.strictEqual(st.handled, false, "volume is not scrolling");

  // the reply of a turn that wrote on the board leaves the board showing; the next plain reply shows the conversation
  const conv = path.join(ws, "conversacion.md");
  fs.appendFileSync(conv, "## 10:01 Tú\n\nescribe los pasos\n\n## 10:01 Asistente\n\nEstán en el pizarrón.\n\n");
  await p.waitForTimeout(900);
  assert.strictEqual(await active(), "panel-pizarron");
  fs.appendFileSync(conv, "## 10:02 Tú\n\ngracias\n\n## 10:02 Asistente\n\nDe nada.\n\n");
  await p.waitForTimeout(900);
  assert.strictEqual(await active(), "panel-conversacion");

  // with the computadora module on, a bare "baja" is ours only while this page is the window in front
  await waitHandled(await post({ type: "config", panels: ["conversacion", "pizarron", "escritorio"], desktop: true }));
  await p.evaluate(() => { document.hasFocus = () => false; });
  await p.waitForTimeout(700);
  assert.strictEqual((await (await fetch(base + "/state")).json()).focused, false);
  st = await say("baja");
  assert.strictEqual(st.handled, false, "another application is in front: the loop scrolls that one");
  st = await say("baja el pizarrón");
  assert.strictEqual(st.handled, true); assert.strictEqual(st.panel, "pizarron");
  assert.ok(await scrollTop() > mid, "naming the panel always scrolls it");
  await p.evaluate(() => { document.hasFocus = () => true; });
  await p.waitForTimeout(700);
  assert.strictEqual((await (await fetch(base + "/state")).json()).focused, true);
  st = await say("sube");
  assert.strictEqual(st.handled, true);

  // wide layout: each panel scrolls on its own
  await waitHandled(await post({ type: "config", panels: ["conversacion", "pizarron", "escritorio"], layout: "wide" }));
  await say("al principio del pizarrón");
  await say("baja el pizarrón");
  assert.ok(await panelTop() > 200);
  assert.strictEqual(await scrollTop(), 0, "the window itself does not move in the wide layout");
  await waitHandled(await post({ type: "config", panels: ["conversacion", "pizarron", "escritorio"], layout: "tabs" }));

  await p.screenshot({ path: path.join(ws, "board.png"), fullPage: true });
  await b.close();
  assert.deepStrictEqual(errors, []);
  console.log("board e2e ok");
})().catch(e => { console.error(e); process.exit(1); });
