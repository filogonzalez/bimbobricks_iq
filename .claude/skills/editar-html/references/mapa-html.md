# Mapa del HTML (v12 · bimbobricks-iq_v12_cta-academy.html)

Los números de línea son orientativos: confírmalos con `html_tool.py outline` y `find`.

## Estructura

| Zona | Líneas v12 | Qué contiene |
|---|---|---|
| `<head>`, comentario inicial | 1–14 | metadatos, Google Fonts (Nunito) |
| `<style>` principal | 15–343 | variables de tema en `:root` (`--navy`, `--blue`, `--gold`, `--red`, `--cream`…), layout |
| `<style id="bb-theme">` | 344–~525 | capa de marca "Bimbo" y CSS de "Databricks al día"; el deploy añade aquí el CSS de noticias si falta |
| Banner y cabecera | ~529–540 | logo PNG/SVG en base64 ⚠ |
| Secciones (`<section class="panel" id=…>`) | 543–~870 | `inicio`, `que-es`, `databricks`, `ruta`, `registro`, `eventos`, `noticias` (incluye `bb-dbx-news` y el form `bbNl`), `comunidad`, `recursos` |
| Modal de vídeo | ~872 | `<dialog>` con `#vmBody` |
| `bbVideoData` | 877 | vídeo mp4 en base64 (8 MB en una línea) ⚠ |
| Script principal | 879–~1376 | `CONFIG`, `IMG`, `SECTIONS`, `T` (i18n + datos de la cronología), `CAL` (icono SVG), `R`, lógica de navegación y formularios |
| Script de dominios (v07) | ~1378 | `DOMS`, `OK=` regex, `NL_ENDPOINT`, handler del newsletter |

⚠ = líneas con blobs: no uses `Read` sobre ellas.

## Navegación

Una sola página con paneles. `SECTIONS` (JS) define el menú: `{id, ic, es, en, short?}`. Mostrar un panel = `show(id)`;
los enlaces usan `data-go="<id>"`. Para añadir una sección:
1. Añade `<section class="panel" id="nueva" hidden>` junto a las demás.
2. Añade la entrada en `SECTIONS`.
3. Añade las claves i18n.

## Tres formas de texto bilingüe (ES/EN)

1. **`data-i18n="clave"`** en el HTML y su valor en `const T = { es:{…}, en:{…} }`. El JS reemplaza el
   contenido al cambiar de idioma, así que el texto dentro de la etiqueta es solo el valor por defecto.
   → `html_tool.py i18n clave --es … --en …`. Los valores con HTML van entre comillas simples
   (`t5:'Haz tu <span class="accent">…</span>'`); la herramienta respeta la comilla original.
   Además existe `data-i18n-alt` (texto alternativo de imágenes). Algunas claves de `T` son arrays, no strings
   (`tl`, `countries`…); `i18n` no las edita, así que usa `replace` sobre el fragmento concreto en `T.es` **y** en `T.en`.
2. **Pares `<span class="bb-es">…</span><span class="bb-en">…</span>`**, que se usan en las zonas añadidas después
   (banner, newsletter, "Databricks al día"). El CSS oculta el idioma inactivo. Edita siempre los dos spans.
3. **Objetos de datos con `es:{…}` / `en:{…}`** en `CONFIG` (`pastEvents`, `news`, `testimonials`) y en `SECTIONS`.

## CONFIG (lo más editado)

| Clave | Uso |
|---|---|
| `selfAssessmentUrl` | enlace al Self-Assessment (otra Databricks App) |
| `videoMain` / `videoDatabricks` | vídeos; `videoDatabricks` acepta una URL embebible (YouTube /embed/, Stream, Vimeo) o un .mp4 |
| `registrationEndpoint` | ⚙ lo reescribe el deploy; no lo edites |
| `communityUrl`, `contactEmail`, `contactName` | datos de la comunidad y del contacto (hoy vacíos) |
| `links.{academy, docs, whatIs, support, pastVideos, hackathonReport}` | enlaces de Recursos |
| `pastEvents[]` | `{icon, url, es:{t,d}, en:{t,d}}` |
| `testimonials[]` | `{quote:{es,en}, name, role}` (vacío) |
| `news[]` | tarjetas de la sección Noticias: `{img: clave de IMG, date:"AAAA-MM-DD", es:{tag,t,d}, en:{…}, go: id de sección}` |

Las tarjetas de `CONFIG.news` son las noticias **del programa**. "Databricks al día" (`#bb-dbx-news`) es otra cosa:
se actualiza con el Job subiendo `items.json` y no se edita en el HTML.

## Fechas del programa

- **Cronología de Eventos + cuenta atrás**: `T.es.tl` y `T.en.tl` (arrays paralelos). Cada hito tiene la forma
  `{i: icono, d:"AAAA-MM-DD" inicio, e:"AAAA-MM-DD" fin opcional, w: texto "cuándo", t: título, p: descripción}`.
  `renderEvents()` calcula el estado (pasado, ahora, siguiente) y los días de `#countdown` a partir de `d`/`e`, así que
  basta con cambiar las fechas ISO **en los dos arrays** y el texto `w`.
- Las fechas también aparecen en textos i18n (p. ej. `e5:"Paso 1 · Hasta el 7 de octubre"`), en `CONFIG.news[].date`
  y en textos sueltos. Antes de cambiar una fecha, ejecuta `find "7 de octubre"`, `find "October 7"` y
  `find "2026-10-07"`, y cámbiala en todos los sitios, en ES y en EN.

## Imágenes

`IMG = { map, laptop, grad, trophy }` (línea 918) contiene las ilustraciones de noticias en base64. Las demás
imágenes están inline en `<img src="data:…">`. `html_tool.py blobs` las lista con su índice y una pista (clase/alt/clave).
Prefiere WebP de menos de 100 KB; el HTML publicado debe quedar por debajo de 9,5 MB (el límite por archivo de Apps es 10 MB).
