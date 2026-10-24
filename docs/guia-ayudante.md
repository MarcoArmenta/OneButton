# Guía para quien ayuda en casa

Esta guía es para la persona que instala OneButton en la computadora de quien
lo va a usar. No hace falta saber programar. Se hace una sola vez; después,
las actualizaciones las pide la propia persona con su voz.

## 1. Qué hace falta

- Una computadora con Windows 10 u 11, macOS o Linux.
- Un micrófono USB, colocado cerca de la persona.
- Un botón grande USB que funcione como la barra espaciadora. Casi todos los
  botones de accesibilidad lo hacen; si el tuyo manda otra tecla, se cambia en
  la configuración (paso 5).
- Una pantalla donde la persona pueda leer, con letra grande.
- Una suscripción a Claude Code, con la sesión iniciada en esa computadora.

## 2. Claude Code con la sesión iniciada

Si Claude Code ya está instalado, abre una terminal, escribe `claude` y pulsa
Intro. Si responde, está todo bien: escribe `/exit`. Si pide iniciar sesión,
hazlo en el navegador una vez.

Si no está instalado, sigue https://docs.anthropic.com/claude-code (en Windows
necesita también Git for Windows).

Esta sesión caduca de vez en cuando. Si OneButton dice que hay que iniciar
sesión otra vez, repite este paso.

## 3. Instalar OneButton

**Windows.** Hace falta tener Git for Windows y Python (de python.org, marcando
"Add python.exe to PATH" al instalar). Abre PowerShell y pega esta línea,
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

## 4. Arrancar

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

El botón tiene dos gestos. **Pulsar** empieza y termina la grabación, y corta
la voz si está hablando. **Mantener pulsado** un segundo y medio cancela lo
que esté pasando. Enséñale los dos; el segundo da tranquilidad.

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
- `tts_voice`: la voz. En Windows, `Microsoft Sabina Desktop` (español de
  México) o `Microsoft Helena Desktop`; si no están, se añaden en
  Configuración, Hora e idioma, Voz, "Agregar voces". En macOS prueba
  `Paulina` o `Jorge`.
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

Sube el tamaño de letra de la terminal a 28 o más. En Windows: Terminal de
Windows, Configuración, Perfiles, Predeterminados, Apariencia, Tamaño de
fuente; si se abre la consola clásica, clic derecho en la barra de título,
Propiedades, Fuente. En macOS: Terminal, Ajustes, Perfiles, Texto. En Linux
depende del programa de terminal; suele estar en Preferencias.

## 7. Si algo falla

- **No responde al botón.** Comprueba que el botón manda espacio: abre un
  editor de texto y púlsalo. Si aparece un espacio, el botón está bien. En
  Windows no hace falta ningún permiso. En macOS, la Terminal necesita el permiso "Monitorización de entrada" en
  Privacidad y seguridad; si no quieres darlo, usa `button_source: terminal`.
- **Corta a la persona a mitad de frase.** Sube `silence_timeout`. Si la sala
  es ruidosa y nunca para sola, pon `silence_rms: 0.02` en la configuración.
- **No habla (Windows).** Comprueba que hay una voz en español instalada
  (paso 5). Sin ella usa la voz en inglés que haya, que suena mal pero funciona.
- **Quieres ver qué pasó.** `OneButton\local\session.log` guarda lo que se
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
