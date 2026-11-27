#!/usr/bin/env python3
"""Build the one-page quick start, in English and in Spanish.

    pip install playwright && playwright install chromium
    python docs/quick-start/build.py

Writes docs/quick-start.pdf and docs/inicio-rapido.pdf: one US Letter page each
(it also fits A4), meant to be printed and handed to a new user. The sheet is
written for one button, which is what the first user has; two buttons get one
line under the box. The words
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
    "steps": [("Press", "the button once. A rising sound: it is listening."),
              ("Speak", "normally. Pauses are fine, take your time."),
              ("Press", "again. A low note: it stopped listening. It answers aloud and on the screen.")],
    "button_title": "The button",
    "button": [("Press", "", "Talk: start, and stop when done. While it speaks: it stops and listens."),
               ("Hold", "about 2 seconds", "Cancel what is going on. If nothing is going on: it explains the controls."),
               ("Keep holding", "5 seconds", "A note for Marco. Another sound plays; say what went wrong and it is sent."),
               ("Yes and no", "", "Say “go ahead” (adelante) for yes, and “cancel” (cancela) for no.")],
    "two_buttons": "Two buttons? Button 2: press for no, cancel or be quiet; hold for the menu of the screen. Hold button 1 for yes.",
    "say_title": "Things to say",
    "say_note": "After pressing the button. Each one also works in Spanish, shown in grey.",
    "groups": [[  # left column, then right column
        ("Ask for anything", [("“Open the paper by Marco Armenta on the Coxeter transformation in the Tamarkin-Tsygan calculus.”", ""),
                              ("“The correspondence of the ideal correspondence theorem of an algebra restricts to homological ideals. "
                               "Write it as a theorem with its proof.”", "")]),
        ("Move a page", [("scroll down", "baja"), ("scroll down a little", "baja un poco"), ("scroll down a lot", "baja mucho"),
                         ("again", "otra vez"), ("go up", "ve hacia arriba"), ("go to the top", "al principio")]),
        ("Hear and see", [("repeat", "repite"), ("read", "lee"), ("conversation", "conversación"), ("board · desk", "pizarrón · escritorio")]),
        ("Two things at once", [("new conversation", "nueva conversación"), ("conversation two", "conversación dos")]),
    ], [
        ("Teach it how you want it to work", [("It remembers what you ask, today and later. You can set conditions and change your mind.", ""),
                                              ("“Remember that I prefer short answers.”", ""),
                                              ("“When I say ‘summary’, read me only the abstract.”", ""),
                                              ("“From now on, do not read aloud what you write on the board.”", "")]),
        ("Write", [("new paper", "nuevo escrito"), ("then dictate: your exact words are written", ""),
                   ("review", "revisión"), ("yes · no · next", "sí · no · siguiente"), ("end dictation", "fin del dictado")]),
        ("Use any program", [("go to Chrome", "ve a Chrome"), ("numbers", "números"),
                             ("puts a number on everything that can be clicked", ""), ("click seven", "pulsa el siete"),
                             ("type hello", "escribe hola"), ("close this window", "cierra esta ventana")]),
        ("Settings", [("speak Spanish", "habla en español"), ("update", "actualiza"), ("undo", "deshacer")]),
    ]],
    "know_title": "Good to know",
    "know": ["The button only talks to OneButton. It never clicks or turns pages by itself.",
             "Before it sends, deletes or pays, it asks “Go ahead?” and waits for your yes.",
             "Your voice stays on this computer. Only the text of what you said is sent to Claude.",
             "You can talk to it while it works: press the button and add what you forgot."],
    "helper": "If it says someone has to help, call", "foot": "Free and open: github.com/MarcoArmenta/OneButton",
}

ES = {
    "file": "inicio-rapido.pdf", "lang": "es",
    "title": "Inicio rápido", "tagline": "Pulsa. Habla. Pulsa otra vez.",
    "lead": "OneButton te deja usar la computadora con la voz. Escucha cuando pulsas, hace lo que "
            "pides y responde en voz alta. Entiende español e inglés.",
    "steps_title": "Cada vez",
    "steps": [("Pulsa", "el botón una vez. Un sonido que sube: está escuchando."),
              ("Habla", "con calma. Puedes hacer pausas, sin prisa."),
              ("Pulsa", "otra vez. Nota grave: dejó de escuchar. Responde en voz alta y en la pantalla.")],
    "button_title": "El botón",
    "button": [("Pulsar", "", "Hablar: empezar, y parar al terminar. Si te habla: se calla y escucha."),
               ("Mantener", "unos 2 segundos", "Cancelar lo que esté pasando. Si no pasa nada: explica los controles."),
               ("Mantener más", "5 segundos", "Una nota para Marco. Suena otro sonido; di qué falló y se le envía."),
               ("Sí y no", "", "Di «adelante» (go ahead) para decir sí, y «cancela» (cancel) para decir no.")],
    "two_buttons": "¿Dos botones? Botón 2: pulsar es no, cancelar o callar; mantener abre el menú de la pantalla. Mantener el botón 1 es sí.",
    "say_title": "Qué decir",
    "say_note": "Después de pulsar el botón. Todo vale también en inglés, en gris.",
    "groups": [[
        ("Pide lo que sea", [("«Abre el artículo de Marco Armenta de la transformación de Coxeter en el cálculo de Tamarkin-Tsygan.»", ""),
                             ("«La correspondencia del teorema de correspondencia de ideales de un álgebra se restringe a ideales "
                              "homológicos. Escríbelo como un teorema con su demostración.»", "")]),
        ("Mover la página", [("baja", "scroll down"), ("baja un poco", "scroll down a little"), ("baja mucho", "scroll down a lot"),
                             ("otra vez", "again"), ("ve hacia arriba", "go up"), ("al principio", "go to the top")]),
        ("Oír y ver", [("repite", "repeat"), ("lee", "read"), ("conversación", "conversation"), ("pizarrón · escritorio", "board · desk")]),
        ("Dos cosas a la vez", [("nueva conversación", "new conversation"), ("conversación dos", "conversation two")]),
    ], [
        ("Enséñale cómo quieres que trabaje", [("Recuerda lo que le pidas, hoy y los demás días. Puedes poner condiciones y cambiar de idea.", ""),
                                               ("«Recuerda que prefiero respuestas cortas.»", ""),
                                               ("«Cuando diga “resumen”, léeme sólo el resumen.»", ""),
                                               ("«De ahora en adelante no leas en voz alta lo que escribes en el pizarrón.»", "")]),
        ("Escribir", [("nuevo escrito", "new paper"), ("y dicta: queda escrito tal como lo dices", ""),
                      ("revisión", "review"), ("sí · no · siguiente", "yes · no · next"), ("fin del dictado", "end dictation")]),
        ("Usar cualquier programa", [("ve a Chrome", "go to Chrome"), ("números", "numbers"),
                                     ("pone un número en cada cosa que se puede pulsar", ""), ("pulsa el siete", "click seven"),
                                     ("escribe hola", "type hello"), ("cierra esta ventana", "close this window")]),
        ("Ajustes", [("habla en inglés", "speak English"), ("actualiza", "update"), ("deshacer", "undo")]),
    ]],
    "know_title": "Conviene saber",
    "know": ["El botón sólo habla con OneButton. Nunca hace clic ni pasa de página por su cuenta.",
             "Antes de enviar, borrar o pagar, pregunta «¿Adelante?» y espera tu sí.",
             "Tu voz se queda en esta computadora. A Claude sólo va el texto de lo que dijiste.",
             "Puedes hablarle mientras trabaja: pulsa el botón y añade lo que faltó."],
    "helper": "Si dice que hace falta ayuda, llama a", "foot": "Libre y abierto: github.com/MarcoArmenta/OneButton",
}

CSS = """
@page { size: Letter; margin: 0; }
* { box-sizing: border-box; margin: 0; padding: 0; }
html { font-size: 10.6pt; }
body { width: 8.5in; height: 11in; padding: 0.4in 0.6in 0.4in; font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
       color: #14181f; line-height: 1.32; display: flex; flex-direction: column; }
:root { --ink: #14181f; --soft: #5d6673; --rule: #d5d9df; --accent: #1f4fa3; --tint: #eef3fb; }
header { display: flex; align-items: flex-end; justify-content: space-between; border-bottom: 2.5pt solid var(--ink); padding-bottom: 7pt; }
h1 { font-size: 30pt; letter-spacing: -0.02em; line-height: 1; font-weight: 700; }
h1 span { color: var(--accent); font-weight: 300; margin-left: 6pt; }
.tagline { font-size: 15pt; font-weight: 600; color: var(--accent); }
.lead { margin: 6pt 0 7pt; font-size: 11.4pt; color: #2a303a; }
h2 { font-size: 8.4pt; letter-spacing: 0.13em; text-transform: uppercase; color: var(--soft); font-weight: 700; margin-bottom: 5pt; }
.steps { display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.2in; margin-bottom: 6pt; }
.steps li { list-style: none; display: grid; grid-template-columns: 19pt 1fr; gap: 6pt; font-size: 10.6pt; line-height: 1.25; }
.steps .n { width: 19pt; height: 19pt; border-radius: 50%; background: var(--ink); color: #fff; font-weight: 700; font-size: 10.5pt;
            display: flex; align-items: center; justify-content: center; }
.steps b { font-weight: 700; }
.btn { border: 1.2pt solid var(--accent); border-radius: 9pt; padding: 6pt 10pt; display: grid; grid-template-columns: 44pt 1fr; gap: 10pt; align-items: center; }
.cap { width: 44pt; height: 44pt; border-radius: 50%; background: var(--accent); color: #fff; display: flex; align-items: center;
       justify-content: center; font-size: 22pt; font-weight: 700; box-shadow: inset 0 -4pt 0 rgba(0,0,0,.22); }
.btn p { font-size: 9.8pt; margin-top: 2.5pt; line-height: 1.25; }
.btn p:first-child { margin-top: 0; }
.btn p b { display: inline-block; min-width: 0; font-weight: 700; }
.btn p i { font-style: normal; color: var(--soft); font-size: 8pt; }
.single { font-size: 9pt; color: var(--soft); margin-top: 4pt; }
.say { margin-top: 7pt; border-top: 1pt solid var(--rule); padding-top: 6pt; flex: 1; }
.say-head { display: flex; align-items: baseline; gap: 10pt; margin-bottom: 6pt; }
.say-head h2 { margin: 0; }
.say-head p { font-size: 8.8pt; color: var(--soft); }
.groups { display: grid; grid-template-columns: 1fr 1fr; column-gap: 0.32in; align-items: start; }
.group { margin-bottom: 5pt; }
.group h3 { font-size: 10.2pt; font-weight: 700; color: var(--accent); margin-bottom: 1.5pt; }
.group li { list-style: none; display: flex; justify-content: space-between; gap: 8pt; align-items: baseline;
            border-bottom: 0.5pt dotted var(--rule); padding: 0.5pt 0; line-height: 1.2; }
.group li .a { font-weight: 600; font-size: 10.2pt; }
.group li .a.plain { font-weight: 400; font-style: italic; }
.group li .b { color: var(--soft); font-size: 8.8pt; text-align: right; white-space: nowrap; }
.know { background: var(--tint); border-radius: 8pt; padding: 6pt 11pt 4pt; margin-top: 2pt; }
.know ul { columns: 2; column-gap: 0.3in; }
.know li { list-style: none; position: relative; padding-left: 10pt; font-size: 9.3pt; margin-bottom: 3pt; break-inside: avoid; }
.know li::before { content: ""; position: absolute; left: 0; top: 5pt; width: 4pt; height: 4pt; border-radius: 50%; background: var(--accent); }
footer { margin-top: 8pt; font-size: 8.8pt; color: var(--soft); }
footer .helper { display: flex; align-items: flex-end; gap: 7pt; color: var(--ink); font-weight: 600; font-size: 10.6pt; }
footer .line { flex: 1; border-bottom: 0.8pt solid var(--ink); height: 13pt; }
footer .foot { text-align: right; margin-top: 4pt; }
"""


def e(text: str) -> str:
    return html.escape(text, quote=False)


def page(t: dict) -> str:
    steps = "".join(f"<li><span class='n'>{i}</span><span><b>{e(verb)}</b> {e(rest)}</span></li>"
                    for i, (verb, rest) in enumerate(t["steps"], 1))

    gestures = "".join(f"<p><b>{e(name)}</b>{f' <i>({e(note)})</i>' if note else ''}<b>:</b> {e(what)}</p>"
                       for name, note, what in t["button"])

    groups = ""
    for column in t["groups"]:
        groups += "<div>"
        for title, rows in column:
            items = "".join(f"<li><span class='a{' plain' if a[0] in '“«' or (not b and len(a) >= 24) else ''}'>{e(a)}</span><span class='b'>{e(b)}</span></li>"
                            for a, b in rows)
            groups += f"<div class='group'><h3>{e(title)}</h3><ul>{items}</ul></div>"
        groups += "</div>"
    know = "".join(f"<li>{e(k)}</li>" for k in t["know"])
    return f"""<!doctype html><html lang="{t['lang']}"><head><meta charset="utf-8"><title>OneButton: {e(t['title'])}</title>
<style>{CSS}</style></head><body>
<header><h1>OneButton<span>{e(t['title'])}</span></h1><div class="tagline">{e(t['tagline'])}</div></header>
<p class="lead">{e(t['lead'])}</p>
<section><h2>{e(t['steps_title'])}</h2><ol class="steps">{steps}</ol></section>
<section><h2>{e(t['button_title'])}</h2><div class="btn"><div class="cap"></div><div>{gestures}</div></div>
<p class="single">{e(t['two_buttons'])}</p></section>
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
