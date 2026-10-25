# Guía para quien ayuda en casa

Esta guía es para la persona que instala OneButton en la computadora de quien
lo va a usar. No hace falta saber programar. Se hace una sola vez; después,
las actualizaciones las pide la propia persona con su voz.

## 1. Qué hace falta

- Una computadora con Windows 10 u 11, macOS o Linux.
- Un micrófono USB, colocado cerca de la persona.
- Uno o dos botones grandes USB. El botón uno debe mandar la barra
  espaciadora y el botón dos la tecla Intro. Casi todas las interfaces de
  botones de accesibilidad lo hacen; si las tuyas mandan otras teclas, se
  cambia en la configuración (paso 5). Con un solo botón funciona todo; el
  segundo permite decir sí y no sin hablar.
- Pregunta a la persona qué mano tiene más fuerza o más control: ahí va el
  botón uno, que es el que más se pulsa.
- Una pantalla donde la persona pueda leer, con letra grande.
- Una suscripción a Claude Code, con la sesión iniciada en esa computadora.

## 2. Claude Code con la sesión iniciada

Si Claude Code ya está instalado, abre una terminal, escribe `claude` y pulsa
Intro. Si responde, está todo bien: escribe `/exit`. Si pide iniciar sesión,
hazlo en el navegador una vez.

Si no está instalado, sigue https://docs.anthropic.com/claude-code (en Windows
necesita también Git for Windows).

Esta sesión caduca de vez en cuando, y la persona no puede iniciarla sola
porque hace falta pulsar un botón en el navegador. Para que no dependa de
nadie, deja una credencial fija: con la sesión iniciada, en la misma
terminal escribe `claude setup-token`, copia el código largo que aparece y
pégalo en `OneButton\local\credentials.env` en la línea que empieza por
`CLAUDE_CODE_OAUTH_TOKEN=`. Más detalles y alternativas en `docs/login.md`.

Si algún día OneButton dice "Claude Code no tiene la sesión iniciada", hay
que repetir esto. Avisará nombrando a la persona de contacto que pongas en
`helper_name` en la configuración.

## 3. Instalar OneButton

**Windows.** Hace falta tener Git for Windows y Python (de python.org, marcando
"Add python.exe to PATH" al instalar). Ojo: en Windows 11 recién instalado,
escribir `python` abre la Tienda en vez de dar error; el instalador lo detecta
y te lo dirá. Abre PowerShell y pega esta línea,
luego Intro:

```powershell
irm https://raw.githubusercontent.com/MarcoArmenta/OneButton/main/bootstrap/install.ps1 | iex
```

**macOS o Linux.** Abre una terminal y pega:

```bash
curl -fsSL https://raw.githubusercontent.com/MarcoArmenta/OneButton/main/bootstrap/install.sh | bash
```

Tarda unos minutos la primera vez porque descarga el modelo de voz. Al final
debería decir en voz alta "OneButton instalado correctamente".

En Windows, comprueba además que las aplicaciones pueden usar el micrófono:
Configuración, Privacidad y seguridad, Micrófono, "Permitir que las
aplicaciones de escritorio accedan al micrófono" activado.

## 4. Arrancar y la primera vez

La primera vez que arranca, OneButton no sabe qué hay conectado y lo
pregunta en voz alta: pide pulsar el botón para hablar, luego el segundo
botón si lo hay (si no, se espera y sigue), después pide decir "hola, me
llamo..." para comprobar el micrófono, y mira qué pantalla hay. Guarda todo
y se reinicia. Dura un minuto. Si cambia algo del equipo, la persona puede
decir "configura los botones" y se repite.

**Windows.** Doble clic en el acceso directo "OneButton" del Escritorio. El
instalador también lo puso en la carpeta Inicio, así que arrancará solo al
encender la computadora.

**macOS o Linux.**

```bash
~/OneButton/bin/onebutton
```

Primero dirá "escuchando el ruido de la sala" (mide el ruido un segundo para
saber cuándo hay silencio) y luego "OneButton listo". Haz la prueba tú: pulsa
el botón, di "hola, qué hora es", pulsa otra vez. Si responde, está funcionando.

Cada botón significa siempre lo mismo, con dos gestos: pulsar, y mantener
pulsado un segundo y medio.

- **Botón uno, pulsar:** hablar. Una vez para empezar, otra para terminar.
  También corta la voz si está hablando.
- **Botón uno, mantener:** sí, cuando OneButton ha hecho una pregunta. Si no
  hay pregunta, repite la última respuesta.
- **Botón dos, pulsar:** no. Cancela lo que esté pasando: una grabación, una
  tarea, una pregunta. También corta la voz.
- **Botón dos, mantener:** abre el menú de la pantalla: ir a un panel, editar
  una fórmula, leer en voz alta, ayuda.

Con un solo botón: mantener pulsado cancela, y el sí se dice con la palabra
"adelante". Enséñale los gestos con calma; el de cancelar da tranquilidad.

Para que arranque solo al encender la computadora (Windows ya lo hace):

**macOS.** Ajustes del Sistema, General, Ítems de inicio, añade
`~/OneButton/bin/onebutton`. También hay que dar permiso de micrófono y de
"Monitorización de entrada" a la Terminal en Privacidad y seguridad; macOS lo
pedirá la primera vez.

**Linux.** Añade `~/OneButton/bin/onebutton` a las aplicaciones de inicio de
tu escritorio, o crea un servicio de usuario con systemd.

## 5. Ajustes habituales

El archivo es `~/OneButton/local/config.yaml`. Ábrelo con cualquier editor de
texto. Lo que más se cambia:

- `silence_timeout`: segundos de silencio antes de que deje de grabar sola.
  Por defecto 90. Si la persona hace pausas largas, súbelo.
- `tts_voice`: la voz. En Windows 11 lo mejor son las voces naturales:
  Configuración, Accesibilidad, Narrador, "Agregar voces naturales", y elige
  Español (México), Dalia o Jorge. OneButton las usa solas en cuanto están
  instaladas; para forzar una, escribe aquí `Dalia` o `Jorge`. Sin voces
  naturales usa la voz clásica del sistema (`Microsoft Sabina Desktop`), que
  se entiende pero suena robótica. En macOS prueba `Paulina` o `Jorge`.
- `button_key`: si el botón uno no manda espacio, escribe aquí la tecla.
- `button2_key`: la tecla del botón dos, normalmente `enter`. Si sólo hay un
  botón, pon `null`.
- `whisper_model`: `small` va bien. Si la computadora es potente, `medium`
  entiende mejor.
- `button_source`: si el botón no reacciona cuando la terminal no está
  delante, pon `terminal`. Entonces la ventana de la terminal tiene que estar
  siempre seleccionada, pero no hace falta ningún permiso.
- `helper_name`: el nombre de quien ayuda, por ejemplo `Marco`. OneButton lo
  dirá en voz alta cuando algo necesite a una persona.
- `modules`: escribe `[maths-screen, scribe]` para activar la pizarra de
  matemáticas y el escritorio de redacción. Al arrancar se abre una página
  del navegador con un panel por función; ponla a pantalla completa en la
  pantalla que la persona lee y deja el sonido del navegador encendido,
  porque la página habla por sí misma al leer y al editar.
- Con `computadora` en la lista de módulos, puede manejar cualquier
  programa: "ve a Chrome", "números" (pone un número en cada botón de la
  ventana), "pulsa el siete", "escribe ...", "cierra esta ventana", "apaga la
  computadora" (pregunta antes). Lo que no sea una orden corta se lo pide a
  Claude, que mira la pantalla y lo hace paso a paso, y pregunta antes de
  cualquier cosa irreversible. Nunca escribe contraseñas: eso lo haces tú.
- Para que aprenda el estilo de la persona al escribir: copia sus artículos
  (PDF, TeX o texto) en `OneButton\workspace\estilo\corpus\` y que diga
  "aprende mi estilo". Esos archivos no salen de la computadora.

Después de cambiar algo, reinicia OneButton.

## 6. Tumbado, y con párkinson

José Antonio usa OneButton tumbado, y los movimientos involuntarios hacen
que los botones se pulsen sin querer o que una pulsación larga se corte.
OneButton lo tiene en cuenta, y hay cosas que ayudan desde fuera:

- **Botones.** Fíjalos a algo que no se mueva (una tabla sobre la cama, un
  brazo articulado), no sueltos sobre el colchón. Que sean grandes y de
  recorrido corto. Una pulsación muy breve o un doble toque se ignoran; si
  aun así se cuelan pulsaciones, sube `press_refractory` a `0.6` y
  `press_min_hold` a `0.12` en la configuración. Si mantener pulsado un
  segundo y medio le cuesta, baja `long_hold` a `1.0`.
- **Micrófono.** La voz puede ser baja. Un micrófono de solapa o uno de
  brazo a un palmo de la boca funciona mucho mejor que uno sobre la mesa.
  OneButton sube el volumen de la voz baja antes de reconocerla; si aun así
  corta frases, baja `vad_threshold` a `0.2`. Si la sala es ruidosa, súbelo a
  `0.5`. En `whisper_prompt` puedes poner palabras que use mucho para que
  las reconozca mejor.
- **Pantalla.** Tumbado, un monitor en un brazo articulado sobre la cama, o
  unas gafas de pantalla (siguiente apartado). Letra grande: `screen_font_size`.
- **Días malos.** Todo funciona con un solo botón y la voz, y casi todo con
  la voz sola. Que nadie se preocupe si un día no usa el segundo botón.

## 7. Gafas de pantalla (Xreal, Viture y similares)

Son unas gafas ligeras que se conectan por USB-C y hacen de monitor. Para
José Antonio son mejores que un monitor fijo: la pantalla va con él.

- Conéctalas al puerto USB-C de la computadora. Windows las ve como un
  monitor más. En Configuración, Sistema, Pantalla, elige "Mostrar sólo en 2"
  (o duplicar, si quieres ver tú lo mismo en el monitor).
- Si el fabricante tiene un programa para Windows que ofrece una pantalla
  virtual ancha o varias pantallas (Xreal Nebula, Viture SpaceWalker),
  instálalo y elige la pantalla ancha: OneButton pone los tres paneles uno
  al lado del otro y aprovecha todo el ancho.
- En `local/config.yaml` deja `screen_preset: glasses`. Fondo negro (en estas
  gafas el negro es transparente y descansa la vista), letra grande y todos
  los paneles visibles. El panel activo lleva un marco azul.
- Pon el navegador a pantalla completa (F11) en las gafas.
- Las gafas no sirven de micrófono. Usa un micrófono de solapa inalámbrico o
  uno de mesa cerca de él; en `input_device` puedes fijar cuál.
- Prueba media hora seguida el primer día y pregúntale por el cansancio de
  ojos y de cuello. Si se cansa, baja `screen_font_size` o vuelve a
  `screen_preset: monitor` en un monitor normal.

## 8. Letra grande

Sube el tamaño de letra de la terminal a 28 o más. En Windows: Terminal de
Windows, Configuración, Perfiles, Predeterminados, Apariencia, Tamaño de
fuente; si se abre la consola clásica, clic derecho en la barra de título,
Propiedades, Fuente. En macOS: Terminal, Ajustes, Perfiles, Texto. En Linux
depende del programa de terminal; suele estar en Preferencias.

## 9. Si algo falla

- **No responde al botón.** Di "configura los botones" (o ejecuta
  `onebutton --setup` desde la terminal) y vuelve a registrarlos. Para ver
  qué tecla manda cada botón, abre un editor de texto y púlsalos. En
  Windows no hace falta ningún permiso. En macOS, la Terminal necesita el permiso "Monitorización de entrada" en
  Privacidad y seguridad; si no quieres darlo, usa `button_source: terminal`.
- **Corta a la persona a mitad de frase.** Sube `silence_timeout`. Si la sala
  es ruidosa y nunca para sola, pon `silence_rms: 0.02` en la configuración.
- **No habla (Windows).** Comprueba que hay una voz en español instalada
  (paso 5). Sin ella usa la voz en inglés que haya, que suena mal pero funciona.
- **Quieres ver qué pasó.** `OneButton\local\session.log` guarda lo que se
  dijo y se respondió, con hora. No sale de la computadora.
- **No escucha.** Comprueba el micrófono en los ajustes de sonido del sistema.
- **Dice que Claude Code no tiene la sesión iniciada.** Repite el paso 2 y
  deja la credencial fija como se explica ahí.
- **Dice que no encuentra Claude Code.** Repite el paso 2.
- **Se ha quedado colgado.** Cierra la ventana de la terminal y vuelve a
  arrancar (paso 4). OneButton se reinicia solo si se cae, pero no si se
  queda esperando algo.
- **Una actualización rompió algo.** La persona puede decir "deshacer" y
  confirmar con "adelante". Vuelve a la versión anterior.

## 10. Acceso remoto para quien mantiene OneButton

Vale la pena instalar una vez un programa de escritorio remoto (Chrome
Remote Desktop, RustDesk o similar) con acceso sin supervisión y una clave
que sólo tenga la persona que mantiene OneButton. Así, cualquier problema
que necesite teclado se arregla desde lejos en minutos. Díselo a la persona
que lo usa: debe saber que existe y cuándo se usa.

## 11. Lo que no hace falta hacer nunca

- Crear cuentas nuevas.
- Dar permisos en GitHub.
- Instalar actualizaciones a mano. Se piden con la voz.
