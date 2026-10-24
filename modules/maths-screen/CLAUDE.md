# Módulo: pizarra de matemáticas

Hay una pizarra en pantalla: una página del navegador que muestra, en letra
grande y con las fórmulas renderizadas, el contenido de `pizarra/pizarra.md`
dentro del espacio de trabajo. Se actualiza sola cada vez que el archivo cambia.

## Cuándo usarla

- Siempre que la conversación tenga fórmulas, cálculos, definiciones,
  demostraciones o notación: escribe en la pizarra y habla poco.
- Cuando el usuario dicte una fórmula: escríbela en la pizarra, y en voz alta
  léela en palabras para confirmar que la entendiste. Por ejemplo: "escribí la
  suma desde i igual a uno hasta n de a sub i al cuadrado".
- Cuando una derivación sea larga: pon los pasos en la pizarra, numerados, y
  di en voz alta sólo la conclusión y dónde está.

## Cómo escribir

- Markdown con LaTeX: `$...$` en línea, `$$...$$` para fórmulas centradas.
  Entornos `align*`, `cases`, `pmatrix`, `bmatrix` funcionan dentro de `$$`.
- Cada tema nuevo empieza con un encabezado `## ` y la fecha. Añade al final;
  no borres lo anterior salvo que te lo pidan.
- Frases cortas entre fórmulas. El usuario lee la pizarra; tú le hablas.
- Si el usuario dice "borra la pizarra" o "pizarra nueva": mueve el contenido
  actual a `pizarra/archivo/AAAA-MM-DD-HHMM.md` y deja la pizarra con un solo
  encabezado. Confirma en voz alta que lo guardaste antes de borrar.
- Si pide "guarda la pizarra" o "exporta a PDF": copia `pizarra/pizarra.md` a
  `matematicas/<nombre que te diga>.md` y, si `pandoc` está disponible,
  genera también el PDF. Di el nombre del archivo en palabras.

## Al hablar

- Nunca leas LaTeX en voz alta. Di las fórmulas en palabras, o di "está en la
  pizarra" y una frase de resumen.
- Si no estás seguro de un símbolo que oíste (x o equis, fi o phi, n o m),
  pregunta una sola cosa concreta: "¿dijiste equis o ese?".
