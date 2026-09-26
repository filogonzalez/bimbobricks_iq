# BimboBricks IQ · Ola 2 — Databricks Asset Bundle

La web del programa de formación de Grupo Bimbo, publicada como **Databricks App**, con los formularios en **Lakebase**, el vídeo en un **Volume** y las noticias gestionadas por un **Job**.

Workspace destino: `https://adb-1844781131568521.1.azuredatabricks.net` (hay que estar en la VPN FortiClient).

```
html/<tu-archivo>.html        ← LO ÚNICO QUE CAMBIAS (exactamente un .html)
        │  scripts/prepare.py  (hook predeploy: valida, extrae el vídeo, cablea /api/*)
        ▼
app/static/index.html (~0,6 MB) ──► Databricks App (FastAPI, SSO + autorización en nombre del usuario)
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
| Proyecto Lakebase Autoscaling | `bimbobricks-iq` (rama `production`, cómputo `primary` de 0,5 a 2 CU) | `resources/lakebase.yml` |
| Catálogo UC de Lakebase | `bimbobricks_forms` → base `databricks_postgres` | `resources/lakebase.yml` |
| Databricks App | `bimbobricks-iq`, visible para el grupo `users`, con autorización en nombre del usuario | `resources/app.yml` |
| Job | `bimbobricks-iq-news-prod`, disparado al llegar un archivo a `news_inbox` | `resources/news_job.yml` |

## Primer despliegue

1. **Ajusta el catálogo** en `databricks.yml` → `targets.<dev|prod>.variables.catalog`. `dev` usa `cat_coe_dv`; `prod` todavía dice `main`. Tiene que ser un catálogo existente donde puedas crear esquemas. El catálogo `forms_catalog` (`bimbobricks_forms[_dev]`) es nuevo, así que quien despliega necesita además `CREATE CATALOG` en el metastore.
2. Conéctate a la VPN y autentícate:
   ```bash
   databricks auth login --host https://adb-1844781131568521.1.azuredatabricks.net --profile bimbo
   ```
3. Despliega en **dev** (solo lo ven los admins):
   ```bash
   ./deploy.sh dev -p bimbo
   ```
   La primera vez el proyecto Lakebase tarda unos minutos en crearse.
4. Abre la URL que imprime el script. La primera vez Databricks pide consentimiento para que la App lea tu identidad (ver [Identidad de quien envía](#identidad-de-quien-envía-autorización-en-nombre-del-usuario)). Envía un registro de prueba y revisa `/api/health` (debe decir `"store": "lakebase", "store_ok": true`) y `/api/me` (debe decir `"verified": true`).
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
- `sso_email`, `sso_user`, `sso_username` y `sso_verified` guardan quién envió el formulario según Databricks Apps (ver la sección siguiente). El campo `email` es lo que la persona escribió; puede registrar a un colega, pero `sso_email` dice quién lo hizo.

Consultas (SQL Editor, Genie, dashboards):
```sql
SELECT email, name, country, kickoff, kickoff_mode, training_language, sso_email, sso_verified, created_at
FROM bimbobricks_forms.forms.registrations ORDER BY created_at DESC;

SELECT count(*) FROM bimbobricks_forms.forms.newsletter_subscriptions WHERE unsubscribed_at IS NULL;
```
Las tablas las crea el service principal de la App. Como quien despliega es el dueño del proyecto Lakebase (`databricks_superuser`), puede leerlas. Para dar lectura a otras personas, desde el SQL Editor de Lakebase (o `databricks psql --project bimbobricks-iq`):
```sql
CREATE EXTENSION IF NOT EXISTS databricks_auth;
SELECT databricks_create_role('persona@grupobimbo.com', 'USER');   -- su rol de Postgres, si no lo tiene
GRANT USAGE ON SCHEMA forms TO "persona@grupobimbo.com";
GRANT SELECT ON ALL TABLES IN SCHEMA forms TO "persona@grupobimbo.com";
```

## Identidad de quien envía (autorización en nombre del usuario)

La App usa autorización en nombre del usuario (OBO). Lo que necesita es el scope de identidad `iam.current-user:read`, que Databricks añade siempre junto con `iam.access-control:read` y que la API no deja declarar. Como `user_api_scopes` en `resources/app.yml` no puede ir vacío, se declara el scope de solo lectura más pequeño, `catalog.catalogs:read`, que la App no usa. Ninguno de los tres da acceso a datos de tablas ni a cómputo.

- En cada petición, el proxy de Databricks Apps añade `X-Forwarded-Email`, `X-Forwarded-User`, `X-Forwarded-Preferred-Username` y `X-Forwarded-Access-Token` (el token del usuario, limitado a esos scopes). El proxy reemplaza un `X-Forwarded-Email` enviado por el cliente.
- Al guardar un formulario, la App toma la identidad de esas cabeceras, nunca del cuerpo del formulario, y la confirma llamando a `/Me` **con el token del usuario** (`app/identity.py`). `sso_verified = true` significa que esa confirmación funcionó. Si el correo de la cabecera no coincide con el del token, se guarda el del token.
- Dentro de Databricks Apps, un envío sin identidad se rechaza con `401`.
- `GET /api/me` devuelve la identidad con la que se guardaría un envío. Sirve para comprobar la configuración.
- La primera vez que alguien abre la web, Databricks le pide consentimiento para esos scopes. Un admin puede darlo en nombre de todos.
- A Lakebase escribe el service principal de la App (recurso `forms-db`). Con OAuth, cada identidad que abre una conexión a Postgres necesita su propio rol, y crear uno por empleado no escala; el token del usuario sirve para atribuir cada envío, no para abrir la conexión.
- El vídeo y las noticias se leen con el service principal (recurso `media-volume`), así que nadie necesita permisos sobre el Volume para ver la web.

## Desarrollo local

```bash
python3 scripts/prepare.py
cd app && pip install -r requirements.txt pytest httpx
MEDIA_VOLUME=/tmp/bb-media python run.py      # sin PGHOST usa almacén en memoria
cd .. && pytest -q
```
En local no hay proxy de Databricks Apps: para simular a un usuario, añade las cabeceras a mano, por ejemplo `curl -H 'X-Forwarded-Email: tu.nombre@grupobimbo.com' localhost:8000/api/me`.

## Por qué Lakebase y no Delta

Los formularios son OLTP: escrituras pequeñas, concurrentes y con unicidad por email. Postgres resuelve esto con `PRIMARY KEY` + `ON CONFLICT` en milisegundos y sin warehouse. Delta no impone unicidad, cada `MERGE` necesita un SQL Warehouse encendido y los `MERGE` concurrentes pueden chocar. Si hace falta analítica, `postgres_catalogs` ya expone las tablas en Unity Catalog sin copiar datos.

## Lakebase Autoscaling

Lakebase Provisioned (`database_instances`) ya no admite instancias nuevas, así que el bundle crea un proyecto Lakebase Autoscaling (`postgres_projects`). Al crearlo, Lakebase provisiona la rama `production`, su cómputo `primary` y la base `databricks_postgres`. El cómputo autoescala entre 0,5 CU y `db_max_cu` (2 CU por defecto; ~2 GB de RAM por CU). En `resources/app.yml`, el recurso de la App es `postgres: {branch, database}` y no el antiguo `database:` de Provisioned. La App pide al SDK una credencial OAuth de su service principal para `LAKEBASE_ENDPOINT` cada vez que abre una conexión (`app/store.py`).

## Solución de problemas

| Síntoma | Causa probable |
|---|---|
| `prepare.py: el HTML no cumple el contrato` | el HTML nuevo cambió un punto del contrato; el mensaje dice cuál |
| El formulario dice "No pudimos enviar" | revisa `/api/health` y *Logs* de la App; `store_ok:false` indica un problema de conexión a Lakebase |
| El vídeo no carga (404) | no se subió `build/video.mp4`; ejecuta el paso 3 de `deploy.sh` o vuelve a desplegar |
| `PERMISSION_DENIED` al leer el Volume | el SP de la App necesita `USE CATALOG` en `<catalog>` y `USE SCHEMA` en el esquema: `GRANT USE CATALOG ON CATALOG <catalog> TO \`<app-sp-id>\`` |
| El Job no se dispara | comprueba que el trigger esté *Active* y que el archivo termine en `.json` |
| El CLI responde `Unauthorized network access to workspace` (403) | no estás en la VPN (FortiClient): el workspace filtra por IP |
| `/api/me` dice `"verified": false` | con `"user_token_forwarded": false`, la App no tiene `user_api_scopes` (vuelve a desplegar); con `true`, falló la llamada a `/Me` (mira los *Logs*) |
| Enviar el formulario devuelve `401 unauthenticated` | la petición llegó sin la identidad que añade el proxy de Databricks Apps |
