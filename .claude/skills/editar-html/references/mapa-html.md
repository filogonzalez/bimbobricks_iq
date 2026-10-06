# Mapa del HTML (v38 · bimbobricks-iq_v38_capacitacion-2026.html)

Título: "BimboBricks · Nueva Capacitación 2026". Los números de línea son orientativos: confírmalos con
`html_tool.py outline` y `find`.

## Estructura

| Zona | Líneas v38 | Qué contiene |
|---|---|---|
| `<head>`, comentario inicial | 1–14 | metadatos, Google Fonts (Nunito) |
| `<style>` principal | 15–343 | variables de tema en `:root` (`--navy`, `--blue`, `--gold`, `--red`, `--cream`…), layout |
| `<style id="bb-theme">` | 344–~1058 | capa de marca "Bimbo" (211 KB): avatares de los bots (`.av-*`), ilustraciones de panadería (`.bk-*`), genio (`.rc-genie`) y CSS de "Databricks al día". Tiene blobs ⚠ |
| Cabecera | ~1060–1070 | logo Business Technology y marca en base64 ⚠ |
| Secciones (`<section class="panel" id=…>`) | 1074–~1570 | `inicio` (castillo, genio y lámpara, bots `#crewRow`), `que-es`, `databricks`, `ruta`, `registro`, `eventos`, `noticias` (incluye `bb-dbx-news` y el form `bbNl`), `comunidad` (mentores/champions), `construye` (casos de uso `#ucPills`, sandbox `#sbxBtn`, form `ideaForm`), `recursos` |
| Modal de vídeo | ~1573 | `<dialog>` con `#vmBody` |
| `bbVideoData` | 1578 | vídeo mp4 en base64 (8 MB en una línea) ⚠ |
| Script principal | 1580–~2216 | `CONFIG`, `IMG` (1624 ⚠), `SECTIONS`, `T` (i18n + cronología), `CAL`, rutas (`RT_AV`, `PROD_URL`, `R`), validación y envío del registro, confirmación guiada (`AREA_BOT`, `AREA_UC…`, `L`), parámetros de URL (`QS`: `?lang=en`, `&area=`), dock de pasos |
| Script de dominios / newsletter | ~2218 | `DOMS`, `OK=` regex, `NL_ENDPOINT`, handler del newsletter |
| Script v13 | ~2260 | formularios "Envía tu idea" (`#ideaForm`) y "Solicita tu acceso" (`#accessForm`, dentro de `<details id="accessX">` en Registro), listas de áreas/roles/impacto, casos de uso, botón del sandbox |
| Scripts v23–v25 | ~2358–2420 | turnos de conversación de los bots, diálogos bot ↔ Genie (`.duo`), CTA de mentores (`#chGo`, `#qMentor`, `#chMail`) |

⚠ = líneas con blobs: no uses `Read` sobre ellas. En v38 son 649–723, 926, 1053, 1060–1102, 1126, 1164–1194,
1432, 1452, 1565, 1578, 1624 y 2127 (`html_tool.py blobs` da la lista exacta).

## Navegación

Una sola página con paneles. `SECTIONS` (JS) define el menú: `{id, ic, es, en, short?}`. Mostrar un panel = `show(id)`;
los enlaces usan `data-go="<id>"`. Enlaces útiles: `#registro`, `?lang=en`, `&area=Finanzas` (preselecciona el área).
Para añadir una sección:
1. Añade `<section class="panel" id="nueva" hidden>` junto a las demás.
2. Añade la entrada en `SECTIONS`.
3. Añade las claves i18n.

## Tres formas de texto trilingüe (ES/EN/PT-BR)

La web es trilingüe. El idioma activo sale de `document.documentElement.lang` (`es`/`en`/`pt`), con
`?lang=` y `localStorage("bbiq-lang")`. El selector `.lang` tiene tres botones `data-lang="es|en|pt"`.
El helper global `pick(es,en,pt)` resuelve los ternarios en el JS dinámico (dock, guía, éxito del registro).

1. **`data-i18n="clave"`** en el HTML y su valor en `const T = { es:{…}, en:{…}, pt:{…} }`. El JS reemplaza el
   contenido al cambiar de idioma, así que el texto dentro de la etiqueta es solo el valor por defecto.
   → `html_tool.py i18n clave --es … --en … --pt …`. Los valores con HTML van entre comillas simples
   (`t5:'Haz tu <span class="accent">…</span>'`); la herramienta respeta la comilla original.
   Además existe `data-i18n-alt` (texto alternativo de imágenes). Algunas claves de `T` son arrays, no strings
   (`tl`, `countries`, `routes`…); `i18n` no las edita, así que usa `replace` sobre el fragmento concreto en
   `T.es`, `T.en` **y** `T.pt`.
2. **Tríos `<span class="bb-es">…</span><span class="bb-en">…</span><span class="bb-pt">…</span>`**. Es la forma
   mayoritaria (417 tríos): banner, bots, Construye, formularios de ideas/acceso, newsletter, "Databricks al día".
   El CSS oculta los dos idiomas inactivos (`html:not([lang="es"]) .bb-es, …{display:none}`). Edita siempre los
   tres spans. Lo mismo aplica a los `<em class="bb-es/en/pt">` y a los `<a class="tl-go bb-es/en/pt">`.
3. **Objetos de datos con `es:{…}` / `en:{…}` / `pt:{…}`** en `CONFIG` (`pastEvents`, `news`, `testimonials`) y en
   `SECTIONS` (más `short:{es,en,pt}`), y tríos `["es","en","pt"]` en las listas del script v13 (`ROLES`, `IMPACT`;
   `AREAS` muestra el mismo valor en los tres). Los enlaces externos a docs de Databricks caen al inglés en PT
   (no hay docs en portugués).

## CONFIG (lo más editado)

| Clave | Uso |
|---|---|
| `selfAssessmentUrl` | Self-Assessment de 5 minutos (otra Databricks App, en el workspace sandbox, con su propio Lakebase): `https://bimbo-training-app-709692038187649.9.azure.databricksapps.com/`. El `href` de `#saBtn` en el HTML debe ser el mismo; el JS lo vuelve a poner desde CONFIG |
| `videoMain` / `videoDatabricks` | vídeos; `videoDatabricks` acepta una URL embebible (YouTube /embed/, Stream, Vimeo) o un .mp4 |
| `registrationEndpoint` | ⚙ lo reescribe el deploy (`/api/register`); no lo edites |
| `ideasEndpoint` / `accessEndpoint` | ⚙ los reescribe el deploy (`/api/ideas`, `/api/access-requests`); vacíos = modo demostración |
| `sandboxUrl` | URL del Sandbox de Desarrollo: hoy `https://adb-709692038187649.9.azuredatabricks.net/` (workspace sandbox). El botón `#sbxBtn` de Construye lo abre en otra pestaña; vacío = el botón lleva a "Solicita tu acceso" (que sigue en Registro, `<details id="accessX">`) |
| `communityUrl` | canal de la comunidad; hoy vacío, y así el botón `#commBtn` ("Entrar a la comunidad") queda oculto |
| `contactEmail`, `contactName` | contacto del programa: hoy `yesenia.alejandro@gbsupport.net` / "Yesenia Alejandro". Con correo, "Contáctanos" (`#chMail`, mentores) abre un mailto, aparece el botón de "Comparte tu historia" en Comunidad y el pie muestra el contacto; vacío = "Contáctanos" lleva al registro |
| `links.{academy, docs, whatIs, support, pastVideos, hackathonReport}` | enlaces de Recursos |
| `pastEvents[]` | `{icon, url, es:{t,d}, en:{t,d}}` |
| `testimonials[]` | `{quote:{es,en}, name, role}` (vacío) |
| `news[]` | tarjetas de la sección Noticias: `{img: clave de IMG, date:"AAAA-MM-DD", es:{tag,t,d}, en:{…}, go: id de sección}` |

Las tarjetas de `CONFIG.news` son las noticias **del programa**. "Databricks al día" (`#bb-dbx-news`) es otra cosa:
se actualiza con el Job subiendo `items.json` y no se edita en el HTML.

## Formularios y lo que envían

| Formulario | Endpoint | Campos del payload (los que no tienen columna van a `raw`) |
|---|---|---|
| `#regForm` (Registro) | `/api/register` | `name, email, country, area, kickoff, kickoffMode, wave, trainingLanguage, newsletter, mentorInterest, selfAssessmentDone, hasDatabricksAccount, accessRequest, uiLanguage, submittedAt, source` |
| `#bbNl` (Newsletter) | `/api/newsletter` | `email, lang, source, ts` |
| `#ideaForm` (Construye) | `/api/ideas` | `type:"idea", name, email, area, idea (10–500), problem, dataNeeded, uiLanguage, submittedAt, source` |
| `#accessForm` (Registro → "Solicita tu acceso") | `/api/access-requests` | `type:"accessRequest", name, email, country, area, role, currentAccess[], hasDatabricksAccount, reason, expectedImpact, urgency, uiLanguage, submittedAt, source` |

Los cuatro formularios validan el dominio corporativo en el navegador; el backend lo vuelve a validar (`app/models.py`)
y guarda la identidad del usuario de Databricks en las columnas `sso_*`.

## Fechas del programa

- **Cronología de Eventos + cuenta atrás**: `T.es.tl` y `T.en.tl` (arrays paralelos). Cada hito tiene la forma
  `{i: icono, d:"AAAA-MM-DD" inicio, e:"AAAA-MM-DD" fin opcional, w: texto "cuándo", t: título, p: descripción}`.
  `renderEvents()` calcula el estado (pasado, ahora, siguiente) y los días de `#countdown` a partir de `d`/`e`, así que
  basta con cambiar las fechas ISO **en los dos arrays** y el texto `w`.
- Las fechas también aparecen en textos i18n (p. ej. `"Hasta el 7 de octubre"`), en `CONFIG.news[].date`, en el
  evento de calendario (`icsURL()`, archivo `BimboBricks-8-oct.ics`) y en textos sueltos. Antes de cambiar una fecha,
  ejecuta `find "7 de octubre"`, `find "October 7"`, `find "2026-10-07"` (y lo mismo para el 8), y cámbiala en todos
  los sitios, en ES y en EN.

## Imágenes

`IMG = { map, laptop, grad, trophy }` (línea 1624) contiene las ilustraciones de noticias en base64. Las demás
imágenes están inline en `<img src="data:…">` o como `background-image:url(data:…)` en `bb-theme` (avatares de bots,
genio, lámpara, castillo). `html_tool.py blobs` las lista con su índice y una pista (clase/alt/clave).
Prefiere WebP de menos de 100 KB; el HTML publicado debe quedar por debajo de 9,5 MB (el límite por archivo de Apps es 10 MB).
El paquete del dueño trae aparte el genio y las poses en PNG/WebP (`updates/…/3_genio_assets`): ya están embebidos;
solo hacen falta si se cambia una imagen con `set-blob`.
