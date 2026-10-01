# Plan B: desplegar desde el propio workspace con el Databricks Assistant

Úsalo si no puedes ejecutar `./deploy.sh` desde tu laptop: por ejemplo, si el CLI no llega al workspace a través de la VPN. Se abre el Assistant en **modo Agent**, dentro del workspace `https://adb-1844781131568521.1.azuredatabricks.net`.

## Antes de pegar el prompt

1. En tu laptop, ejecuta `python3 scripts/prepare.py`. Genera `app/static/index.html` (ya viene en el repo para la v38) y `build/video.mp4`.
2. Sube la carpeta del repo al workspace: **Workspace → tu carpeta → Import → carpeta/zip**. Si tienes Git conectado, también puedes usar **Create → Git folder**. Ruta sugerida: `/Workspace/Users/<tu-usuario>/bimbobricks-iq-dabs`.
3. Ten a mano `build/video.mp4`, porque el prompt pedirá subirlo al Volume.

## Prompt (cópialo tal cual y ajusta las dos primeras líneas)

```text
Catálogo UC a usar: <CATALOGO>
Carpeta del bundle en el workspace: /Workspace/Users/<tu-usuario>/bimbobricks-iq-dabs

Eres mi asistente de despliegue. En esa carpeta hay un Databricks Asset Bundle (databricks.yml + resources/*.yml)
para la web "BimboBricks IQ · Ola 2". Quiero desplegar el target `dev` y, si todo funciona, `prod`.

1. Abre databricks.yml y cambia `variables.catalog` de los targets dev y prod por el catálogo indicado arriba.
   No cambies nada más sin preguntarme.
2. Despliega el bundle desde el panel de Deployments del workspace (target dev). El hook `experimental.scripts.predeploy`
   puede no ejecutarse en el workspace; no pasa nada, porque app/static/index.html ya está generado. Si el deploy falla
   por ese hook, quita solo el bloque `experimental:` de databricks.yml y reintenta.
3. Verifica que existan estos recursos y enséñame su estado:
   - Esquema <CATALOGO>.bimbobricks_iq_dev con los Volumes `media` y `news_inbox`
   - Proyecto Lakebase Autoscaling `bimbobricks-iq-dev` (rama `production`, cómputo `primary` activo) y el catálogo UC `bimbobricks_forms_dev`
   - Databricks App `bimbobricks-iq-dev` con los recursos `forms-db` (postgres) y `media-volume` (volume), y autorización
     de usuario activa (scope declarado `catalog.catalogs:read`; efectivos también `iam.current-user:read` e `iam.access-control:read`)
   - Job `bimbobricks-iq-news-dev` con trigger de llegada de archivos sobre /Volumes/<CATALOGO>/bimbobricks_iq_dev/news_inbox/
4. Dime que suba el vídeo: debe quedar en /Volumes/<CATALOGO>/bimbobricks_iq_dev/media/media/video.mp4
   (Catalog Explorer → Volume media → crear carpeta "media" → Upload). Espera mi confirmación.
5. Despliega e inicia la App (Deploy desde la carpeta files/app del bundle, o "Run" del recurso app en el panel del bundle).
   Revisa los logs de arranque. Deben aparecer "Uvicorn running" y, al abrir /api/health, "store": "lakebase".
   Al abrir /api/me, después de aceptar el consentimiento, debe aparecer "verified": true.
6. Prueba el Job: sube samples/items.example.json al Volume news_inbox y confirma que en ~2 minutos
   aparece /Volumes/<CATALOGO>/bimbobricks_iq_dev/media/news/news_block.html y que el inbox queda vacío.
7. En el SQL Editor ejecuta:
     SELECT * FROM bimbobricks_forms_dev.forms.registrations ORDER BY created_at DESC LIMIT 5;
   (Las tablas aparecen después del primer arranque de la App.)
8. Si algún paso falla por permisos, dime exactamente qué GRANT hace falta y a qué principal (el service principal
   de la App aparece en la pestaña Authorization de la App). No crees recursos fuera de los definidos en el bundle.
Al terminar, dame la URL de la App y un resumen de lo verificado. Luego repetimos con el target prod.
```

## Prompt para un espacio de Genie sobre los registros (opcional, después del deploy)

Crea un Genie space con las tablas `bimbobricks_forms.forms.registrations`, `bimbobricks_forms.forms.newsletter_subscriptions`, `bimbobricks_forms.forms.ideas` y `bimbobricks_forms.forms.access_requests`. Como instrucciones generales:

```text
Estas tablas contienen los registros del programa de formación BimboBricks IQ · Ola 2 de Grupo Bimbo.
- registrations: una fila por participante (email único). kickoff = asistirá al kick-off; kickoff_mode = remote|onsite;
  wave = se inscribe en la Ola 2; training_language = idioma del curso (es|en|pt); submissions = veces que envió el formulario;
  created_at = primer registro; updated_at = último envío. sso_email = cuenta Databricks con la que se envió
  (sso_verified = true si se confirmó con el token del usuario); email puede ser el de otra persona registrada por ella.
- newsletter_subscriptions: suscriptores del newsletter; unsubscribed_at nulo = suscripción activa; source = 'registro'
  si se suscribió desde el formulario de registro.
- ideas: ideas de casos de uso enviadas desde "Construye" (una fila por idea). access_requests: solicitudes de acceso a
  Databricks (una fila por solicitud; role, urgency). En registrations, raw->>'mentorInterest' y raw->>'newsletter' traen
  el interés en ser mentor/champion y en el newsletter.
Responde en español. Cuenta personas por email distinto. Las fechas están en UTC; conviértelas a America/Mexico_City.
```
