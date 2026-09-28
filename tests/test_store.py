"""Credencial con la que la App abre conexiones a Lakebase y escrituras del LakebaseStore."""
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

import store

ENDPOINT = "projects/bimbobricks-iq-dev/branches/production/endpoints/primary"


class FakeWorkspace:
    def __init__(self):
        self.endpoints = []
        self.postgres = SimpleNamespace(generate_database_credential=self._generate)
        self.config = SimpleNamespace(oauth_token=lambda: SimpleNamespace(access_token="sp-oauth"))

    def _generate(self, endpoint):
        self.endpoints.append(endpoint)
        return SimpleNamespace(token="pg-credential")


def test_password_is_a_credential_for_the_injected_endpoint(monkeypatch):
    monkeypatch.delenv("PGPASSWORD", raising=False)
    monkeypatch.setenv("LAKEBASE_ENDPOINT", ENDPOINT)
    ws = FakeWorkspace()
    assert store.db_password(ws) == "pg-credential" and ws.endpoints == [ENDPOINT]


def test_password_precedence(monkeypatch):
    ws = FakeWorkspace()
    monkeypatch.setenv("LAKEBASE_ENDPOINT", ENDPOINT)
    monkeypatch.setenv("PGPASSWORD", "token-manual")
    assert store.db_password(ws) == "token-manual"
    monkeypatch.delenv("PGPASSWORD")
    monkeypatch.delenv("LAKEBASE_ENDPOINT")
    assert store.db_password(ws) == "sp-oauth" and ws.endpoints == []


class FakeConnection:
    """Registra las sentencias y si se ejecutaron dentro de una transacción."""

    def __init__(self, fail_on=None):
        self.log, self.in_tx, self.committed, self.fail_on = [], False, False, fail_on

    @contextmanager
    def transaction(self):
        self.in_tx = True
        try:
            yield
            self.committed = True
        finally:
            self.in_tx = False

    def execute(self, sql, params):
        if self.fail_on and self.fail_on in sql:
            raise RuntimeError("fallo simulado")
        self.log.append((sql, params, self.in_tx))
        return SimpleNamespace(fetchone=lambda: (True,))


def lakebase_store(conn):
    s = store.LakebaseStore.__new__(store.LakebaseStore)
    s._ready = True
    s._pool = SimpleNamespace(connection=contextmanager(lambda: (yield conn)))
    return s


ROW = {"email": "ana.perez@grupobimbo.com", "ui_language": "es", "submitted_at": None, "raw": {},
       "sso_email": "ana.perez@grupobimbo.com", "sso_user": "1@2", "sso_username": "Ana", "sso_verified": True}


def test_registration_and_newsletter_share_one_transaction():
    conn = FakeConnection()
    assert lakebase_store(conn).upsert_registration({**ROW, "newsletter": True}) is True
    assert [sql for sql, _, _ in conn.log] == [store.UPSERT_REGISTRATION, store.SUBSCRIBE_FROM_REGISTRATION]
    assert all(in_tx for _, _, in_tx in conn.log) and conn.committed
    assert conn.log[1][1]["source"] == "registro" and conn.log[1][1]["sso_verified"] is True


def test_registration_without_newsletter_writes_only_the_registration():
    conn = FakeConnection()
    lakebase_store(conn).upsert_registration({**ROW, "newsletter": False})
    assert [sql for sql, _, _ in conn.log] == [store.UPSERT_REGISTRATION]


def test_failed_subscription_rolls_back_the_registration():
    conn = FakeConnection(fail_on="newsletter_subscriptions")
    with pytest.raises(RuntimeError):
        lakebase_store(conn).upsert_registration({**ROW, "newsletter": True})
    assert not conn.committed
