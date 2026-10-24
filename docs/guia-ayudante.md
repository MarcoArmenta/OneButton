# Guía para quien ayuda en casa

Esta guía es para la persona que instala OneButton en la computadora de quien
lo va a usar. No hace falta saber programar. Se hace una sola vez; después,
las actualizaciones las pide la propia persona con su voz.

## 1. Qué hace falta

- Una computadora con macOS o Linux.
- Un micrófono USB, colocado cerca de la persona.
- Un botón grande USB que funcione como la barra espaciadora. Casi todos los
  botones de accesibilidad lo hacen; si el tuyo manda otra tecla, se cambia en
  la configuración (paso 5).
- Una pantalla donde la persona pueda leer, con letra grande.
- Una suscripción a Claude Code, con la sesión iniciada en esa computadora.

## 2. Instalar Claude Code e iniciar sesión

Sigue las instrucciones de https://docs.anthropic.com/claude-code. Al terminar,
abre una terminal, escribe `claude` y pulsa Intro. Te pedirá iniciar sesión en
el navegador una vez. Cuando veas que responde, escribe `/exit`.

Esta sesión caduca de vez en cuando. Si OneButton dice que no encuentra Claude
Code o que hay que iniciar sesión, repite este paso.

## 3. Instalar OneButton

Abre una terminal y pega esta línea, luego Intro:

```bash
curl -fsSL https://raw.githubusercontent.com/MarcoArmenta/OneButton/main/bootstrap/install.sh | bash
```

Tarda unos minutos la primera vez porque descarga el modelo de voz. Al final
debería decir en voz alta "OneButton instalado correctamente".

## 4. Arrancar

```bash
~/OneButton/bin/onebutton
```

Primero dirá "escuchando el ruido de la sala" (mide el ruido un segundo para
saber cuándo hay silencio) y luego "OneButton listo". Haz la prueba tú: pulsa
el botón, di "hola, qué hora es", pulsa otra vez. Si responde, está funcionando.

El botón tiene dos gestos. **Pulsar** empieza y termina la grabación, y corta
la voz si está hablando. **Mantener pulsado** un segundo y medio cancela lo
que esté pasando. Enséñale los dos; el segundo da tranquilidad.

Para que arranque solo al encender la computadora:

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
- `tts_voice`: la voz. En macOS prueba `Paulina` o `Jorge`.
- `button_key`: si el botón no manda espacio, escribe aquí la tecla.
- `whisper_model`: `small` va bien. Si la computadora es potente, `medium`
  entiende mejor.
- `button_source`: si el botón no reacciona cuando la terminal no está
  delante, pon `terminal`. Entonces la ventana de la terminal tiene que estar
  siempre seleccionada, pero no hace falta ningún permiso.
- `modules`: escribe `[maths-screen]` para activar la pizarra de matemáticas.
  Al arrancar se abre una página del navegador; ponla en la pantalla que la
  persona lee.

Después de cambiar algo, reinicia OneButton.

## 6. Letra grande

Sube el tamaño de letra de la terminal a 28 o más. En macOS: Terminal,
Ajustes, Perfiles, Texto. En Linux depende del programa de terminal; suele
estar en Preferencias.

## 7. Si algo falla

- **No responde al botón.** Comprueba que el botón manda espacio: abre un
  editor de texto y púlsalo. Si aparece un espacio, el botón está bien. En
  macOS, la Terminal necesita el permiso "Monitorización de entrada" en
  Privacidad y seguridad; si no quieres darlo, usa `button_source: terminal`.
- **Corta a la persona a mitad de frase.** Sube `silence_timeout`. Si la sala
  es ruidosa y nunca para sola, pon `silence_rms: 0.02` en la configuración.
- **Quieres ver qué pasó.** `~/OneButton/local/session.log` guarda lo que se
  dijo y se respondió, con hora. No sale de la computadora.
- **No escucha.** Comprueba el micrófono en los ajustes de sonido del sistema.
- **Dice que no encuentra Claude Code.** Repite el paso 2.
- **Se ha quedado colgado.** Cierra la ventana de la terminal y vuelve a
  arrancar (paso 4). OneButton se reinicia solo si se cae, pero no si se
  queda esperando algo.
- **Una actualización rompió algo.** La persona puede decir "deshacer" y
  confirmar con "adelante". Vuelve a la versión anterior.

## 8. Lo que no hace falta hacer nunca

- Crear cuentas nuevas.
- Dar permisos en GitHub.
- Instalar actualizaciones a mano. Se piden con la voz.
