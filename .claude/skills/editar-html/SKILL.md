---
name: editar-html
description: Modifica la web de BimboBricks IQ (html/*.html, ~8,6 MB con imágenes y vídeo en base64) sin romper el deploy. Úsalo para cambiar textos ES/EN, fechas, eventos, noticias de CONFIG, enlaces, FAQ, estilos, imágenes o el vídeo; para aplicar cambios pedidos por el dueño del HTML, o para sacar una nueva versión (v12 → v13) antes de `./deploy.sh`.
---

# Editar el HTML de BimboBricks IQ

El HTML es un único archivo autocontenido con **líneas de hasta 8 MB** (el vídeo en base64 y
unas 22 imágenes). **Nunca lo leas entero ni con `Read` sin `offset/limit`**, y no uses `cat` o `grep` sin filtrar:
llenarías el contexto de base64. Usa siempre `scripts/html_tool.py`, que oculta los blobs como `«blob:mime:KB»`.

Todos los comandos se ejecutan desde la raíz del repo y trabajan sobre el único `.html` de `html/`.

## Flujo

1. **Orientarte**: `python3 scripts/html_tool.py outline` muestra las secciones, los bloques, CONFIG, i18n y los blobs.
   Si necesitas saber dónde vive cada cosa, lee [references/mapa-html.md](references/mapa-html.md).
2. **Localizar**: `find "texto" [-C 200] [--regex] [-i]` o `show <id>` (p. ej. `show registro`).
3. **Editar** con la herramienta más específica:
   | Cambio | Comando |
   |---|---|
   | Texto con `data-i18n="clave"` | `i18n clave --es "…" --en "…"` (clave nueva: `--create`) |
   | Cualquier otro fragmento | `replace --old "fragmento único" --new "…"` (para textos largos o multilínea: `--old-file/--new-file`) |
   | Imagen embebida | `blobs` → `set-blob N archivo.webp` |
   | Vídeo principal | `set-video nuevo.mp4` |
   `replace` exige que `--old` aparezca **exactamente** `--count` veces (1 por defecto). Si falla, amplía el
   contexto hasta que sea único; no subas `--count` a ciegas. Usa `--dry-run` para probar.
   Para cambios grandes en una zona sin blobs (CSS, JS de `T`/`CONFIG`), puedes usar `Read` con
   `offset/limit` en las líneas que da `find` y después `Edit`. Comprueba antes que esas líneas no sean
   las de blobs (en v12: 529–583, 877 y 918).
4. **Bilingüe siempre**: cada cambio visible va en ES **y** EN (ver las tres formas en el mapa). Si el usuario
   solo te da un idioma, traduce tú y díselo.
5. **Validar**: `python3 scripts/html_tool.py check` comprueba el contrato de deploy, la paridad de claves ES/EN,
   los pares `bb-es`/`bb-en` y el balance de etiquetas. Tiene que terminar en `✔ check OK`.
   Si tocaste formularios, noticias o endpoints, ejecuta también los tests (`pytest -q`).
6. **Versionar** (solo si el usuario quiere una versión nueva): `bump` renombra `_v12_…` → `_v13_…`
   (`--label nuevo-sufijo` para cambiar el sufijo). Así `html/` sigue teniendo un único archivo.
7. **Resumir** al usuario qué cambió (sección, ES/EN y el resultado de `check`) y recordarle que publica con
   `./deploy.sh dev -p bimbo`, y después `prod`.

## Qué NO tocar: el contrato del deploy

`scripts/prepare.py` detiene el deploy si faltan estos elementos. No los borres ni los renombres:
- `<form … id="regForm">` y `<form class="bb-nl" id="bbNl" …>`, junto con los `name`/`id` de sus inputs (el backend
  valida `name`, `email`, `kickoff`, `wave`, `trainingLanguage`…; ver `app/models.py`).
- `registrationEndpoint: "…"` dentro de `CONFIG` y `var NL_ENDPOINT="…"`: su valor da igual, se reescribe en el deploy.
- `videoMain: (window.__bbVideoUrl || "")` y `<script type="application/octet-stream" id="bbVideoData">`.
- `<section id="bb-dbx-news">…</section>`: su contenido lo reemplaza el Job de noticias en producción. Editar las
  tarjetas aquí solo cambia el valor por defecto. Para las noticias reales, sube un `items.json` al Volume `news_inbox`.
- La lista de dominios permitidos (`grupobimbo.com`, `gbsupport.net`) está en el JS (`DOMAIN_RE`, `OK=`), en
  `app/app.yaml` (`ALLOWED_DOMAINS`) y en `app/schema.sql` (`CHECK`). Si cambia, cámbiala en los tres sitios.

## Añadir un campo al formulario de registro

1. Añade el input al `<form id="regForm">` con su label ES/EN.
2. Inclúyelo en `const payload={…}` del JS (busca `find "const payload="`).
3. Se guarda automáticamente en la columna `raw` (jsonb). Si además debe validarse o tener su propia columna,
   añádelo a `app/models.py` (`Registration`) y a `app/schema.sql` + `UPSERT_REGISTRATION` en `app/store.py`,
   con `ALTER TABLE … ADD COLUMN IF NOT EXISTS`. Añade un test en `tests/test_app.py`.

## Si el dueño entrega un HTML nuevo

No lo edites para "arreglarlo" sin avisar. Sustituye el archivo en `html/`, ejecuta `check` y, si falla, explica
al usuario qué punto del contrato cambió y propón el ajuste mínimo.
