"""Persistencia de formularios.

En la App, el recurso `forms-db` (Lakebase Autoscaling) inyecta PGHOST/PGPORT/PGDATABASE/PGUSER/PGSSLMODE
y app.yaml añade LAKEBASE_ENDPOINT. La App escribe con su service principal: la contraseña es una
credencial OAuth del SP para ese endpoint, que caduca en ~1 h. Lakebase solo la comprueba al abrir la
conexión, así que cada conexión nueva del pool pide una vigente.
Sin PGHOST (local / tests) se usa un almacén en memoria.
"""
import json
import logging
import os
import threading
from pathlib import Path

import psycopg
from databricks.sdk import WorkspaceClient
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

log = logging.getLogger("bimbobricks.store")

SCHEMA_SQL = (Path(__file__).parent / "schema.sql").read_text(encoding="utf-8")

UPSERT_REGISTRATION = """
INSERT INTO forms.registrations AS r (
  email, name, country, area, kickoff, kickoff_mode, wave, training_language,
  self_assessment_done, ui_language, source, sso_email, sso_user, sso_username, sso_verified,
  client_submitted_at, raw)
VALUES (%(email)s, %(name)s, %(country)s, %(area)s, %(kickoff)s, %(kickoff_mode)s, %(wave)s,
  %(training_language)s, %(self_assessment_done)s, %(ui_language)s, %(source)s, %(sso_email)s,
  %(sso_user)s, %(sso_username)s, %(sso_verified)s, %(submitted_at)s, %(raw)s)
ON CONFLICT (email) DO UPDATE SET
  name = EXCLUDED.name, country = EXCLUDED.country, area = EXCLUDED.area,
  kickoff = EXCLUDED.kickoff, kickoff_mode = EXCLUDED.kickoff_mode, wave = EXCLUDED.wave,
  training_language = EXCLUDED.training_language, self_assessment_done = EXCLUDED.self_assessment_done,
  ui_language = EXCLUDED.ui_language, source = EXCLUDED.source, sso_email = EXCLUDED.sso_email,
  sso_user = EXCLUDED.sso_user, sso_username = EXCLUDED.sso_username, sso_verified = EXCLUDED.sso_verified,
  client_submitted_at = EXCLUDED.client_submitted_at, raw = EXCLUDED.raw,
  submissions = r.submissions + 1, updated_at = now()
RETURNING (xmax = 0) AS inserted
"""

UPSERT_NEWSLETTER = """
INSERT INTO forms.newsletter_subscriptions AS n (
  email, lang, source, sso_email, sso_user, sso_username, sso_verified, client_ts)
VALUES (%(email)s, %(lang)s, %(source)s, %(sso_email)s, %(sso_user)s, %(sso_username)s,
  %(sso_verified)s, %(ts)s)
ON CONFLICT (email) DO UPDATE SET
  lang = EXCLUDED.lang, source = EXCLUDED.source, sso_email = EXCLUDED.sso_email,
  sso_user = EXCLUDED.sso_user, sso_username = EXCLUDED.sso_username, sso_verified = EXCLUDED.sso_verified,
  client_ts = EXCLUDED.client_ts, unsubscribed_at = NULL, updated_at = now()
RETURNING (xmax = 0) AS inserted
"""


class MemoryStore:
    kind = "memory"

    def __init__(self):
        self.registrations, self.newsletter = {}, {}
        self._lock = threading.Lock()

    def _put(self, table, row):
        with self._lock:
            inserted = row["email"] not in table
            table[row["email"]] = row
            return inserted

    def upsert_registration(self, row):
        return self._put(self.registrations, row)

    def upsert_newsletter(self, row):
        return self._put(self.newsletter, row)

    def ping(self):
        return True


def db_password(ws):
    # PGPASSWORD permite pruebas locales contra Lakebase con un token generado a mano.
    if os.getenv("PGPASSWORD"):
        return os.environ["PGPASSWORD"]
    endpoint = os.getenv("LAKEBASE_ENDPOINT")
    if endpoint:
        return ws.postgres.generate_database_credential(endpoint=endpoint).token
    # Recurso `database` de Lakebase Provisioned: basta el token OAuth del SP.
    return ws.config.oauth_token().access_token


class LakebaseStore:
    kind = "lakebase"

    def __init__(self):
        ws = WorkspaceClient()

        class OAuthConnection(psycopg.Connection):
            @classmethod
            def connect(cls, conninfo="", **kwargs):
                kwargs["password"] = db_password(ws)
                return super().connect(conninfo, **kwargs)

        # check: descarta conexiones que el cómputo de Lakebase cerró (reinicio o escalado a cero).
        self._pool = ConnectionPool(
            conninfo="", connection_class=OAuthConnection,
            kwargs={"application_name": "bimbobricks-iq", "autocommit": True},
            min_size=1, max_size=int(os.getenv("PG_POOL_MAX", "5")),
            max_lifetime=45 * 60, check=ConnectionPool.check_connection, open=False,
        )
        self._ready = False
        self._lock = threading.Lock()

    def _init(self):
        if self._ready:
            return
        with self._lock:
            if self._ready:
                return
            self._pool.open(wait=True, timeout=30)
            with self._pool.connection() as c:
                c.execute(SCHEMA_SQL)
            self._ready = True
            log.info("Lakebase listo (esquema forms verificado) · host=%s db=%s endpoint=%s",
                     os.getenv("PGHOST"), os.getenv("PGDATABASE"), os.getenv("LAKEBASE_ENDPOINT"))

    def _upsert(self, sql, row):
        self._init()
        params = dict(row)
        if "raw" in params:
            params["raw"] = Jsonb(params["raw"])
        with self._pool.connection() as c:
            return bool(c.execute(sql, params).fetchone()[0])

    def upsert_registration(self, row):
        return self._upsert(UPSERT_REGISTRATION, row)

    def upsert_newsletter(self, row):
        return self._upsert(UPSERT_NEWSLETTER, row)

    def ping(self):
        self._init()
        with self._pool.connection() as c:
            c.execute("SELECT 1")
        return True


def make_store():
    if os.getenv("PGHOST"):
        return LakebaseStore()
    log.warning("PGHOST no definido: usando almacén EN MEMORIA (solo para desarrollo local)")
    return MemoryStore()


def to_json(obj):
    return json.loads(json.dumps(obj, default=str))
