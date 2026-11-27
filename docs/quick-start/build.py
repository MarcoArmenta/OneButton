#!/usr/bin/env python3
"""Build the one-page quick start, in English and in Spanish.

    pip install playwright && playwright install chromium
    python docs/quick-start/build.py

Writes docs/quick-start.pdf and docs/inicio-rapido.pdf: one US Letter page each
(it also fits A4), meant to be printed and handed to a new user. The words
live here, once per language, so the two sheets cannot drift apart in layout.
When a command changes in the code, change it here and rebuild.
"""

from __future__ import annotations

import html
import sys
from pathlib import Path

DOCS = Path(__file__).resolve().parent.parent

EN = {
    "file": "quick-start.pdf", "lang": "en",
    "title": "Quick start", "tagline": "Press. Speak. Press again.",
    "lead": "OneButton lets you use the computer with your voice. It listens when you press, "
            "does what you ask, and answers aloud. It understands English and Spanish.",
    "steps_title": "Every time",
    "steps": [("Press", "button 1 once. A rising sound: it is listening."),
              ("Speak", "normally. Pauses are fine, take your time."),
              ("Press", "button 1 again. A low note: it stopped. It answers aloud and on the screen.")],
    "buttons_title": "The two buttons",
    "b1": "Button 1", "b1_side": "right hand", "b2": "Button 2", "b2_side": "left hand",
    "press": "Press", "hold": "Hold", "hold_note": "about 2 seconds",
    "b1_press": "Talk: start, and stop when done. While it speaks: it stops and listens.", "b1_hold": "Yes, when it asks. Otherwise: hear the last answer again.",
    "b2_press": "No. Cancel a task. Be quiet.", "b2_hold": "Open the menu of the screen.",
    "one_button": "Only one button? Press to talk, hold to cancel, and say “go ahead” for yes. To just silence it: press twice.",
    "say_title": "Things to say",
    "say_note": "After pressing button 1. Each one also works in Spanish, shown in grey.",
    "groups": [
        ("Ask for anything", [("“Find the paper by Gabriel on arXiv and open it.”", ""),
                              ("“Read me my new email.”", ""),
                              ("“What is on the screen?”", "¿qué hay en pantalla?")]),
        ("Move a page", [("scroll down", "baja"), ("scroll down a little", "baja un poco"), ("scroll down a lot", "baja mucho"),
                         ("again", "otra vez"), ("go up", "ve hacia arriba"), ("go to the top", "al principio")]),
        ("Hear and see", [("repeat", "repite"), ("read", "lee"), ("conversation", "conversación"), ("board · desk", "pizarrón · escritorio")]),
        ("Yes and no", [("go ahead", "adelante"), ("cancel", "cancela")]),
        ("Write", [("new paper", "nuevo escrito"), ("then dictate: your exact words are written", ""),
                   ("review", "revisión"), ("yes · no · next", "sí · no · siguiente"), ("end dictation", "fin del dictado")]),
        ("Use any program", [("go to Chrome", "ve a Chrome"), ("numbers, then click seven", "números, pulsa el siete"),
                             ("type hello", "escribe hola"), ("close this window", "cierra esta ventana")]),
        ("Two things at once", [("new conversation", "nueva conversación"), ("conversation two", "conversación dos")]),
        ("Settings", [("speak Spanish", "habla en español"), ("update", "actualiza"), ("undo", "deshacer")]),
    ],
    "know_title": "Good to know",
    "know": ["The buttons only talk to OneButton. They never click or turn pages by themselves.",
             "Before it sends, deletes or pays, it asks “Go ahead?” and waits for your yes.",
             "Your voice stays on this computer. Only the text of what you said is sent to Claude.",
             "You can talk to it while it works: press button 1 and add what you forgot."],
    "helper": "If it says someone has to help, call", "foot": "Free and open: github.com/MarcoArmenta/OneButton",
}

ES = {
    "file": "inicio-rapido.pdf", "lang": "es",
    "title": "Inicio rápido", "tagline": "Pulsa. Habla. Pulsa otra vez.",
    "lead": "OneButton te deja usar la computadora con la voz. Escucha cuando pulsas, hace lo que "
            "pides y responde en voz alta. Entiende español e inglés.",
    "steps_title": "Cada vez",
    "steps": [("Pulsa", "el botón 1 una vez. Un sonido que sube: está escuchando."),
              ("Habla", "con calma. Puedes hacer pausas, sin prisa."),
              ("Pulsa", "el botón 1 otra vez. Una nota grave. Responde en voz alta y en la pantalla.")],
    "buttons_title": "Los dos botones",
    "b1": "Botón 1", "b1_side": "mano derecha", "b2": "Botón 2", "b2_side": "mano izquierda",
    "press": "Pulsar", "hold": "Mantener", "hold_note": "unos 2 segundos",
    "b1_press": "Hablar: empezar, y parar al terminar. Si te habla: se calla y escucha.", "b1_hold": "Sí, cuando pregunta. Si no: repetir la última respuesta.",
    "b2_press": "No. Cancelar una tarea. Callar.", "b2_hold": "Abrir el menú de la pantalla.",
    "one_button": "¿Un solo botón? Pulsa para hablar, mantén para cancelar, y di «adelante» para decir sí. Para que calle: pulsa dos veces.",
    "say_title": "Qué decir",
    "say_note": "Después de pulsar el botón 1. Todo vale también en inglés, en gris.",
    "groups": [
        ("Pide lo que sea", [("«Busca el artículo de Gabriel en arXiv y ábrelo.»", ""),
                             ("«Léeme el correo nuevo.»", ""),
                             ("«¿Qué hay en pantalla?»", "what is on the screen?")]),
        ("Mover la página", [("baja", "scroll down"), ("baja un poco", "scroll down a little"), ("baja mucho", "scroll down a lot"),
                             ("otra vez", "again"), ("ve hacia arriba", "go up"), ("al principio", "go to the top")]),
        ("Oír y ver", [("repite", "repeat"), ("lee", "read"), ("conversación", "conversation"), ("pizarrón · escritorio", "board · desk")]),
        ("Sí y no", [("adelante", "go ahead"), ("cancela", "cancel")]),
        ("Escribir", [("nuevo escrito", "new paper"), ("y dicta: queda escrito tal como lo dices", ""),
                      ("revisión", "review"), ("sí · no · siguiente", "yes · no · next"), ("fin del dictado", "end dictation")]),
        ("Usar cualquier programa", [("ve a Chrome", "go to Chrome"), ("números, pulsa el siete", "numbers, click seven"),
                                     ("escribe hola", "type hello"), ("cierra esta ventana", "close this window")]),
        ("Dos cosas a la vez", [("nueva conversación", "new conversation"), ("conversación dos", "conversation two")]),
        ("Ajustes", [("habla en inglés", "speak English"), ("actualiza", "update"), ("deshacer", "undo")]),
    ],
    "know_title": "Conviene saber",
    "know": ["Los botones sólo hablan con OneButton. Nunca hacen clic ni pasan de página por su cuenta.",
             "Antes de enviar, borrar o pagar, pregunta «¿Adelante?» y espera tu sí.",
             "Tu voz se queda en esta computadora. A Claude sólo va el texto de lo que dijiste.",
             "Puedes hablarle mientras trabaja: pulsa el botón 1 y añade lo que faltó."],
    "helper": "Si dice que hace falta ayuda, llama a", "foot": "Libre y abierto: github.com/MarcoArmenta/OneButton",
}

CSS = """
@page { size: Letter; margin: 0; }
* { box-sizing: border-box; margin: 0; padding: 0; }
html { font-size: 10.6pt; }
body { width: 8.5in; height: 11in; padding: 0.44in 0.6in 0.4in; font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
       color: #14181f; line-height: 1.32; display: flex; flex-direction: column; }
:root { --ink: #14181f; --soft: #5d6673; --rule: #d5d9df; --accent: #1f4fa3; --tint: #eef3fb; --no: #8a2f2f; }
header { display: flex; align-items: flex-end; justify-content: space-between; border-bottom: 2.5pt solid var(--ink); padding-bottom: 7pt; }
h1 { font-size: 30pt; letter-spacing: -0.02em; line-height: 1; font-weight: 700; }
h1 span { color: var(--accent); font-weight: 300; margin-left: 6pt; }
.tagline { font-size: 15pt; font-weight: 600; color: var(--accent); }
.lead { margin: 7pt 0 9pt; font-size: 11.4pt; color: #2a303a; }
h2 { font-size: 8.4pt; letter-spacing: 0.13em; text-transform: uppercase; color: var(--soft); font-weight: 700; margin-bottom: 5pt; }
.steps { display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.2in; margin-bottom: 8pt; }
.steps li { list-style: none; display: grid; grid-template-columns: 19pt 1fr; gap: 6pt; font-size: 10.6pt; line-height: 1.25; }
.steps .n { width: 19pt; height: 19pt; border-radius: 50%; background: var(--ink); color: #fff; font-weight: 700; font-size: 10.5pt;
            display: flex; align-items: center; justify-content: center; }
.steps b { font-weight: 700; }
.buttons { display: grid; grid-template-columns: 1fr 1fr; gap: 10pt; }
.buttons { gap: 0.2in; }
.btn { border: 1.2pt solid var(--accent); border-radius: 9pt; padding: 7pt 10pt 7pt; display: grid; grid-template-columns: 44pt 1fr; gap: 10pt; align-items: center; }
.btn.two { border-color: var(--no); }
.cap { width: 44pt; height: 44pt; border-radius: 50%; background: var(--accent); color: #fff; display: flex; align-items: center;
       justify-content: center; font-size: 22pt; font-weight: 700; box-shadow: inset 0 -4pt 0 rgba(0,0,0,.22); }
.two .cap { background: var(--no); }
.btn h3 { font-size: 12pt; line-height: 1.1; }
.btn h3 small { font-weight: 400; color: var(--soft); font-size: 8.6pt; margin-left: 4pt; }
.btn p { font-size: 9.8pt; margin-top: 2.5pt; line-height: 1.25; }
.btn p b { display: inline-block; min-width: 0; font-weight: 700; }
.btn p i { font-style: normal; color: var(--soft); font-size: 8pt; }
.single { font-size: 9pt; color: var(--soft); margin-top: 5pt; }
.say { margin-top: 9pt; border-top: 1pt solid var(--rule); padding-top: 8pt; flex: 1; }
.say-head { display: flex; align-items: baseline; gap: 10pt; margin-bottom: 6pt; }
.say-head h2 { margin: 0; }
.say-head p { font-size: 8.8pt; color: var(--soft); }
.groups { columns: 2; column-gap: 0.32in; }
.group { break-inside: avoid; margin-bottom: 7pt; }
.group h3 { font-size: 10.2pt; font-weight: 700; color: var(--accent); margin-bottom: 1.5pt; }
.group li { list-style: none; display: flex; justify-content: space-between; gap: 8pt; align-items: baseline;
            border-bottom: 0.5pt dotted var(--rule); padding: 0.9pt 0; line-height: 1.24; }
.group li .a { font-weight: 600; font-size: 10.2pt; }
.group li .a.plain { font-weight: 400; font-style: italic; }
.group li .b { color: var(--soft); font-size: 8.8pt; text-align: right; white-space: nowrap; }
.know { background: var(--tint); border-radius: 8pt; padding: 7pt 11pt 5pt; margin-top: 2pt; }
.know ul { columns: 2; column-gap: 0.3in; }
.know li { list-style: none; position: relative; padding-left: 10pt; font-size: 9.3pt; margin-bottom: 3pt; break-inside: avoid; }
.know li::before { content: ""; position: absolute; left: 0; top: 5pt; width: 4pt; height: 4pt; border-radius: 50%; background: var(--accent); }
footer { margin-top: 10pt; font-size: 8.8pt; color: var(--soft); }
footer .helper { display: flex; align-items: flex-end; gap: 7pt; color: var(--ink); font-weight: 600; font-size: 10.6pt; }
footer .line { flex: 1; border-bottom: 0.8pt solid var(--ink); height: 13pt; }
footer .foot { text-align: right; margin-top: 6pt; }
"""


def e(text: str) -> str:
    return html.escape(text, quote=False)


def page(t: dict) -> str:
    steps = "".join(f"<li><span class='n'>{i}</span><span><b>{e(verb)}</b> {e(rest)}</span></li>"
                    for i, (verb, rest) in enumerate(t["steps"], 1))

    def button(cls: str, n: str, name: str, side: str, press: str, hold: str) -> str:
        return (f"<div class='btn {cls}'><div class='cap'>{n}</div><div><h3>{e(name)}<small>{e(side)}</small></h3>"
                f"<p><b>{e(t['press'])}:</b> {e(press)}</p>"
                f"<p><b>{e(t['hold'])}</b> <i>({e(t['hold_note'])})</i><b>:</b> {e(hold)}</p></div></div>")

    groups = ""
    for title, rows in t["groups"]:
        items = "".join(f"<li><span class='a{' plain' if a[0] in '“«' or (not b and len(a) >= 24) else ''}'>{e(a)}</span><span class='b'>{e(b)}</span></li>"
                        for a, b in rows)
        groups += f"<div class='group'><h3>{e(title)}</h3><ul>{items}</ul></div>"
    know = "".join(f"<li>{e(k)}</li>" for k in t["know"])
    return f"""<!doctype html><html lang="{t['lang']}"><head><meta charset="utf-8"><title>OneButton: {e(t['title'])}</title>
<style>{CSS}</style></head><body>
<header><h1>OneButton<span>{e(t['title'])}</span></h1><div class="tagline">{e(t['tagline'])}</div></header>
<p class="lead">{e(t['lead'])}</p>
<section><h2>{e(t['steps_title'])}</h2><ol class="steps">{steps}</ol></section>
<section><h2>{e(t['buttons_title'])}</h2><div class="buttons">
  {button('first', '1', t['b1'], t['b1_side'], t['b1_press'], t['b1_hold'])}
  {button('two', '2', t['b2'], t['b2_side'], t['b2_press'], t['b2_hold'])}
</div><p class="single">{e(t['one_button'])}</p></section>
<section class="say"><div class="say-head"><h2>{e(t['say_title'])}</h2><p>{e(t['say_note'])}</p></div>
<div class="groups">{groups}</div></section>
<section class="know"><h2>{e(t['know_title'])}</h2><ul>{know}</ul></section>
<footer><div class="helper"><span>{e(t['helper'])}</span><span class="line"></span></div><div class="foot">{e(t['foot'])}</div></footer>
</body></html>"""


def main() -> int:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for t in (EN, ES):
            tab = browser.new_page()
            tab.set_content(page(t), wait_until="load")
            out = DOCS / t["file"]
            tab.pdf(path=str(out), format="Letter", print_background=True, margin={k: "0" for k in ("top", "right", "bottom", "left")})
            overflow = tab.evaluate("document.body.scrollHeight - document.body.clientHeight")
            print(f"{out.name}: written" + (f" (WARNING: {overflow}px do not fit on the page)" if overflow > 1 else ""))
            tab.close()
        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
