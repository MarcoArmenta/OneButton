# Changelog

Each release has a paragraph that starts **Español.** and one that starts
**English.** Before an update is installed the user hears the one in the
language the computer speaks, so keep both short, concrete and free of jargon.

## Unreleased

**Español.** La computadora ahora habla en inglés y entiende español e inglés
a la vez; di "habla en español" para que vuelva a hablar español, y queda
guardado. Los botones ya no llegan a los programas: antes un botón pasaba de
página un PDF y no había forma de volver. Ahora la página se mueve con la voz:
"baja", "baja un poco", "baja mucho", "otra vez", "ve hacia arriba", "al
principio". En el escritorio, lo que dictas queda escrito tal como lo dices,
sin que el asistente añada ni cambie nada; di "revisión" y te propone
correcciones y añadidos de uno en uno, y tú decides cada uno. Hay una hoja de
inicio rápido para imprimir, en inglés y en español. Ahora un sonido corto
que sube avisa cuando empieza a escuchar, y una nota más grave cuando deja de
escuchar. Si pulsas el botón uno mientras habla, se calla y te escucha en el
acto; antes había que pulsar otra vez. Si algo sale mal, mantén el botón
pulsado cinco segundos para dejarle una nota a Marco.

**English.** The computer now speaks English and understands English and
Spanish at once; say "speak Spanish" to switch, and it is remembered. The
buttons no longer reach applications: a press used to page a PDF down with no
way back. Pages now move by voice: "scroll down", "a little", "a lot",
"again", "go up", "go to the top". On the writing desk what you dictate is
written exactly as you say it, with nothing added or changed; say "review" and
the assistant proposes corrections and additions one at a time, and you decide
each one. There is a one-page quick start to print, in English and Spanish.
A short rising sound now tells you when it starts listening, and a lower note
when it stops. Pressing button 1 while it is speaking makes it stop and listen
at once; before, you had to press again. If something goes wrong, hold the
button for five seconds to leave a note for Marco.
Config: `speak_language` and `listen_languages` replace `language`;
`tts_voices` and `whisper_prompts` are per language; `button_exclusive` is new;
`press_min_hold` is 0 by default, so a quick press counts; `cue_sounds: false`
turns the two sounds off; `note_hold` and `maintainer_name` are new.

Earlier, also unreleased:

**Español.** Primera versión. Uno o dos botones. Con dos: el uno habla y, si
se mantiene pulsado, dice sí; el dos cancela o dice no. Con uno: pulsar para
hablar y para parar, mantener pulsado para cancelar. Dictado, Claude Code, respuesta
hablada sin leer código ni fórmulas símbolo a símbolo. Actualización por voz
con confirmación, y deshacer; "actualiza Claude" actualiza Claude Code; "inicia sesión" vuelve a entrar en Claude
desde el navegador, pulsando Autorizar por voz. Una pantalla con paneles: la
conversación, el pizarrón de matemáticas con edición por números ("barra en el
siete"), y el escritorio para dictar artículos en tu propio estilo y corregir
por párrafo. Lee en voz alta cualquier panel. "Baja", "sube", "al principio" y "al final" mueven
lo que hay en pantalla, y el pizarrón aparece solo en cuanto se escribe en él. Habla siempre con
una voz del idioma en que habla: la del sistema o, si no la hay, una propia que descarga una sola vez.
Se puede hablar a Claude mientras trabaja. Varias conversaciones a la vez: "nueva
conversación" abre otra mientras la primera sigue trabajando, "conversación
uno" vuelve. La primera vez pide el botón
izquierdo y el derecho, comprueba el micrófono y mira las pantallas; con dos,
la página va a pantalla completa en la segunda. Filtra el temblor en los botones y
entiende la voz baja. Maneja cualquier programa: "ve a Chrome", "números",
"pulsa el siete", y lo demás lo hace Claude mirando la pantalla. Funciona sin internet, en Windows, macOS y Linux.

**English.** First version. One or two buttons. With two: button 1 talks and,
held, says yes; button 2 cancels or says no. With one: press to talk and to
stop, hold to cancel. Dictation, Claude Code, spoken replies that do not read
code or formulas symbol by symbol. Voice update with confirmation, and undo; "actualiza Claude" upgrades Claude Code itself; "inicia sesión" signs in again from the
browser, clicking Authorize by voice.
A screen with panels: the conversation, the maths board with editing by
number ("barra en el siete"), and the writing desk for dictating papers in
your own style and correcting by paragraph. Reads any panel aloud. "Baja", "sube", "al principio"
and "al final" scroll what is on screen, and the pizarrón shows itself as soon as something is
written on it. Always speaks with a voice of the language it is speaking: the system's, or an offline
one downloaded once when the system has none. Talk to Claude while it works. Several conversations at once: "nueva conversación"
opens another while the first keeps working, "conversación uno" goes back. On first run it asks for the left and right buttons,
checks the microphone and looks at the screens; with two, the page fills the
second one. Filters tremor on the buttons and handles a soft voice. Controls any
application: "ve a Chrome", "números", "pulsa el siete"; Claude does the rest
by looking at the screen.
Works offline, on Windows, macOS and Linux.
