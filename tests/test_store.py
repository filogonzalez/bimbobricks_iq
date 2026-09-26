"""Credencial con la que la App abre conexiones a Lakebase."""
from types import SimpleNamespace

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
