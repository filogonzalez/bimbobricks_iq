# BimboBricks IQ · Ola 2 — Databricks Asset Bundle

La web del programa de formación de Grupo Bimbo, publicada como **Databricks App**, con los formularios en **Lakebase**, el vídeo en un **Volume** y las noticias gestionadas por un **Job**.

Workspace destino: `https://adb-1844781131568521.1.azuredatabricks.net` (hay que estar en la VPN FortiClient).

```
html/<tu-archivo>.html        ← LO ÚNICO QUE CAMBIAS (exactamente un .html)
        │  scripts/prepare.py  (hook predeploy: valida, extrae el vídeo, cablea /api/*)
        ▼
app/static/index.html (~0,6 MB) ──► Databricks App (FastAPI, SSO)
build/video.mp4 (~6 MB)         ──► Volume  media/media/video.mp4 ──► GET /media/video.mp4 (Range)
                                    Volume  media/news/news_block.html ◄── Job de noticias ◄── items.json en news_inbox
POST /api/register, /api/newsletter ──► Lakebase  forms.registrations / forms.newsletter_subscriptions
                                         └─ expuesto en UC como <forms_catalog>.forms.*
```

## Qué crea el bundle

| Recurso | Nombre (prod) | Archivo |
|---|---|---|
| Esquema UC | `<catalog>.bimbobricks_iq` | `resources/storage.yml` |
| Volume `media` | vídeo + bloque de noticias publicado | `resources/storage.yml` |
| Volume `news_inbox` | aquí se sube `items.json` a mano | `resources/storage.yml` |
| Instancia Lakebase | `bimbobricks-iq` (CU_1) | `resources/lakebase.yml` |
| Catálogo UC de Lakebase | `bimbobricks_forms` → base `bimbobricks` | `resources/lakebase.yml` |
| Databricks App | `bimbobricks-iq`, visible para el grupo `users` | `resources/app.yml` |
| Job | `bimbobricks-iq-news-prod`, disparado al llegar un archivo a `news_inbox` | `resources/news_job.yml` |

## Primer despliegue

1. **Ajusta el catálogo** en `databricks.yml` → `targets.<dev|prod>.variables.catalog` (hoy dice `main`). Tiene que ser un catálogo existente donde puedas crear esquemas.
2. Conéctate a la VPN y autentícate:
   ```bash
   databricks auth login --host https://adb-1844781131568521.1.azuredatabricks.net --profile bimbo
   ```
3. Despliega en **dev** (solo lo ven los admins):
   ```bash
   ./deploy.sh dev -p bimbo
   ```
   La primera vez la instancia Lakebase tarda unos minutos en crearse.
4. Abre la URL que imprime el script, envía un registro de prueba y revisa `/healthz` (debe decir `"store": "lakebase", "store_ok": true`).
5. Cuando todo funcione, **prod**: `./deploy.sh prod -p bimbo`

`deploy.sh` ejecuta: `bundle validate` → `bundle deploy` (el hook ejecuta `prepare.py`) → sube `build/video.mp4` al Volume → `bundle run bimbobricks_iq` (publica el código y arranca la App).

## Publicar una nueva versión del HTML

```bash
rm html/*.html
cp ~/Descargas/bimbobricks-iq_v13.html html/
./deploy.sh prod -p bimbo
```

No hay que tocar nada más. Si el HTML nuevo rompe el contrato, `prepare.py` **detiene el deploy** antes de publicar y dice qué falta. Para probarlo sin desplegar: `python3 scripts/prepare.py`.

### Editar el HTML (con o sin Claude Code)

El HTML tiene líneas de hasta 8 MB (base64), así que no conviene abrirlo en un editor normal. Usa `scripts/html_tool.py`:
```bash
python3 scripts/html_tool.py outline                              # mapa del archivo
python3 scripts/html_tool.py find "7 de octubre"                  # buscar (oculta los blobs)
python3 scripts/html_tool.py i18n heroSub --es "…" --en "…"       # textos bilingües
python3 scripts/html_tool.py replace --old "…" --new "…"          # reemplazo exacto y único
python3 scripts/html_tool.py set-video nuevo.mp4                  # también: blobs / set-blob N img.webp
python3 scripts/html_tool.py check                                # validar antes de desplegar
python3 scripts/html_tool.py bump                                 # v12 → v13
```
En Claude Code, el skill de proyecto **`/editar-html`** (`.claude/skills/editar-html/`) sigue este flujo y conoce el
mapa del archivo (`references/mapa-html.md`). Basta con pedir, por ejemplo: *"cambia el cierre de registro al 14 de octubre"*.

### Contrato con el HTML (lo que el dueño del HTML debe conservar)

| Elemento | Para qué |
|---|---|
| `<form … id="regForm">` y `<form class="bb-nl" id="bbNl" …>` | formularios |
| `registrationEndpoint: "…"` dentro de `CONFIG` | se reescribe a `/api/register` |
| `var NL_ENDPOINT="…"` | se reescribe a `/api/newsletter` |
| `videoMain: (window.__bbVideoUrl \|\| "")` | se apunta a `/media/video.mp4` |
| `<script type="application/octet-stream" id="bbVideoData">` (opcional) | el vídeo se extrae de aquí; si no está, se conserva el vídeo que ya esté en el Volume |
| `<section id="bb-dbx-news">…</section>` (o el `<form id="bbNl">` como ancla) | ahí se insertan las noticias |

Los campos del formulario pueden cambiar: la API valida los conocidos y **guarda el payload completo** en la columna `raw` (jsonb), así que un campo nuevo no se pierde. Si se vuelve obligatorio, añádelo en `app/models.py` y `app/schema.sql`.

## Noticias ("Databricks al día")

1. Prepara `items.json` con el mismo formato de siempre (ejemplo: `samples/items.example.json`).
2. Súbelo en **Catalog Explorer → `<catalog>.bimbobricks_iq` → Volumes → `news_inbox` → Upload**.
3. En aproximadamente un minuto se dispara el Job `bimbobricks-iq-news-prod`: valida, genera `news_block.html` en el Volume `media` y archiva el JSON. La web lo muestra al siguiente refresco (la caché de la App dura 60 s). **No hace falta redeploy.**
4. Si el JSON es inválido, el Job falla y te llega un correo; el archivo queda en `media/news/rejected/` junto con un `.error.txt` que explica el problema.

Para republicar a mano un archivo concreto: *Run now with different parameters* → añade `--items /Volumes/.../media/news/archive/<archivo>.json`.

## Formularios en Lakebase

- `forms.registrations`: una fila por email (PK). Si alguien se registra de nuevo, se actualiza y `submissions` suma 1.
- `forms.newsletter_subscriptions`: una fila por email.
- Doble validación de dominio: la API (`app/models.py`, variable `ALLOWED_DOMAINS` en `app/app.yaml`) y un `CHECK` en Postgres.
- `sso_email` guarda la identidad real de quien envió el formulario (cabecera `X-Forwarded-Email` de Databricks Apps).

Consultas (SQL Editor, Genie, dashboards):
```sql
SELECT email, name, country, kickoff, kickoff_mode, training_language, created_at
FROM bimbobricks_forms.forms.registrations ORDER BY created_at DESC;

SELECT count(*) FROM bimbobricks_forms.forms.newsletter_subscriptions WHERE unsubscribed_at IS NULL;
```
Las tablas las crea el service principal de la App. Como quien despliega es el dueño de la instancia (`databricks_superuser`), puede leerlas. Para dar lectura a otras personas, desde el SQL Editor de Lakebase:
```sql
GRANT USAGE ON SCHEMA forms TO "persona@grupobimbo.com";
GRANT SELECT ON ALL TABLES IN SCHEMA forms TO "persona@grupobimbo.com";
```
(Primero hay que crear el rol de Postgres de esa persona desde la pestaña *Roles* de la instancia.)

## Desarrollo local

```bash
python3 scripts/prepare.py
cd app && pip install -r requirements.txt pytest httpx
MEDIA_VOLUME=/tmp/bb-media python run.py      # sin PGHOST usa almacén en memoria
cd .. && pytest -q
```

## Por qué Lakebase y no Delta

Los formularios son OLTP: escrituras pequeñas, concurrentes y con unicidad por email. Postgres resuelve esto con `PRIMARY KEY` + `ON CONFLICT` en milisegundos y sin warehouse. Delta no impone unicidad, cada `MERGE` necesita un SQL Warehouse encendido y los `MERGE` concurrentes pueden chocar. Si hace falta analítica, `database_catalogs` ya expone las tablas en Unity Catalog sin copiar datos.

## Cambiar a Lakebase Autoscaling (opcional)

La instancia Provisioned CU_1 está siempre encendida, así que tiene un coste fijo. Lakebase Autoscaling puede escalar a cero, pero en DABs está en **Beta**. Para usarla, sustituye `database_instances` + `database_catalogs` por `postgres_projects` / `postgres_branches` / `postgres_endpoints` (con `suspend_timeout_duration`) y, en `resources/app.yml`, el recurso `database:` por `postgres: {branch, database, permission: CAN_CONNECT_AND_CREATE}`. El código de la App no cambia: sigue leyendo `PG*`.

## Solución de problemas

| Síntoma | Causa probable |
|---|---|
| `prepare.py: el HTML no cumple el contrato` | el HTML nuevo cambió un punto del contrato; el mensaje dice cuál |
| El formulario dice "No pudimos enviar" | revisa `/healthz` y *Logs* de la App; `store_ok:false` indica un problema de conexión a Lakebase |
| El vídeo no carga (404) | no se subió `build/video.mp4`; ejecuta el paso 3 de `deploy.sh` o vuelve a desplegar |
| `PERMISSION_DENIED` al leer el Volume | el SP de la App necesita `USE CATALOG` en `<catalog>` y `USE SCHEMA` en el esquema: `GRANT USE CATALOG ON CATALOG <catalog> TO \`<app-sp-id>\`` |
| El Job no se dispara | comprueba que el trigger esté *Active* y que el archivo termine en `.json` |
