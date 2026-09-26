"""Prueba la App con almacén en memoria y un 'Volume' local (sin Databricks)."""
import gzip
import importlib
import re
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import identity
import store

REG = {"name": "Ana Pérez", "email": "Ana.Perez@GrupoBimbo.com", "country": "MX", "area": "Finanzas",
       "kickoff": True, "kickoffMode": "remote", "wave": True, "trainingLanguage": "es",
       "selfAssessmentDone": True, "uiLanguage": "es", "submittedAt": "2026-09-26T10:00:00Z",
       "source": "bimbobricks-iq-landing-wave2", "campoNuevo": 42}

# Cabeceras que añade el proxy de Databricks Apps a cada petición autenticada
SSO = {"X-Forwarded-Email": "Ana.Perez@GrupoBimbo.com", "X-Forwarded-User": "6459219705358936@1844781131568521",
       "X-Forwarded-Preferred-Username": "ana.perez@grupobimbo.com"}


class FakeUserClient:
    """Hace de WorkspaceClient del usuario: current_user.me() devuelve `user_name` o lanza `error`."""

    def __init__(self, user_name=None, error=None):
        self.user_name, self.error, self.current_user = user_name, error, self

    def me(self):
        if self.error:
            raise self.error
        return SimpleNamespace(user_name=self.user_name)


@pytest.fixture
def client(tmp_path, monkeypatch):
    (tmp_path / "media").mkdir()
    (tmp_path / "news").mkdir()
    (tmp_path / "media" / "video.mp4").write_bytes(bytes(range(256)) * 4)
    monkeypatch.setenv("MEDIA_VOLUME", str(tmp_path))
    monkeypatch.delenv("PGHOST", raising=False)
    monkeypatch.delenv("DATABRICKS_APP_NAME", raising=False)
    import main
    main = importlib.reload(main)
    c = TestClient(main.app)
    c.main, c.vol = main, tmp_path
    return c


def test_register_upsert_and_raw(client):
    r = client.post("/api/register", json=REG, headers={"X-Forwarded-Email": "ana.perez@grupobimbo.com"})
    assert r.status_code == 200 and r.json() == {"ok": True, "created": True}
    r = client.post("/api/register", json=REG)
    assert r.json()["created"] is False
    row = client.main.store.registrations["ana.perez@grupobimbo.com"]
    assert row["raw"]["campoNuevo"] == 42 and row["training_language"] == "es"


def test_identity_comes_from_proxy_headers_not_from_body(client):
    body = {**REG, "email": "colega@grupobimbo.com", "sso_email": "otra@grupobimbo.com", "sso_verified": True}
    assert client.post("/api/register", json=body, headers=SSO).status_code == 200
    row = client.main.store.registrations["colega@grupobimbo.com"]
    assert row["sso_email"] == "ana.perez@grupobimbo.com"
    assert row["sso_user"] == SSO["X-Forwarded-User"] and row["sso_username"] == "ana.perez@grupobimbo.com"
    assert row["sso_verified"] is False  # sin token del usuario no hay verificación


def test_obo_token_confirms_identity(client, monkeypatch):
    tokens = []
    monkeypatch.setattr(identity, "user_client", lambda t: tokens.append(t) or FakeUserClient("Ana.Perez@GrupoBimbo.com"))
    r = client.post("/api/newsletter", json={"email": "luis@gbsupport.net"},
                    headers={**SSO, "X-Forwarded-Access-Token": "tok-ana"})
    assert r.status_code == 200 and tokens == ["tok-ana"]
    row = client.main.store.newsletter["luis@gbsupport.net"]
    assert row["sso_email"] == "ana.perez@grupobimbo.com" and row["sso_verified"] is True


def test_token_identity_wins_over_mismatched_header(client, monkeypatch):
    monkeypatch.setattr(identity, "user_client", lambda t: FakeUserClient("real@grupobimbo.com"))
    client.post("/api/register", json=REG, headers={**SSO, "X-Forwarded-Access-Token": "tok"})
    row = client.main.store.registrations["ana.perez@grupobimbo.com"]
    assert row["sso_email"] == "real@grupobimbo.com" and row["sso_verified"] is True


def test_failed_verification_keeps_header_identity_and_never_logs_token(client, monkeypatch, caplog):
    monkeypatch.setattr(identity, "user_client", lambda t: FakeUserClient(error=PermissionError("403 secreto-123")))
    r = client.post("/api/register", json=REG, headers={**SSO, "X-Forwarded-Access-Token": "secreto-123"})
    assert r.status_code == 200
    row = client.main.store.registrations["ana.perez@grupobimbo.com"]
    assert row["sso_email"] == "ana.perez@grupobimbo.com" and row["sso_verified"] is False
    assert "No se pudo verificar" in caplog.text and "secreto-123" not in caplog.text


def test_rejects_anonymous_submissions_inside_databricks_apps(client, monkeypatch):
    monkeypatch.setenv("DATABRICKS_APP_NAME", "bimbobricks-iq-dev")
    r = client.post("/api/register", json=REG)
    assert r.status_code == 401 and r.json() == {"ok": False, "error": "unauthenticated"}
    assert client.post("/api/newsletter", json={"email": "luis@gbsupport.net"}).status_code == 401
    assert client.main.store.registrations == {} and client.main.store.newsletter == {}
    assert client.post("/api/register", json=REG, headers=SSO).status_code == 200


def test_me(client, monkeypatch):
    assert client.get("/api/me", headers=SSO).json() == {
        "email": "ana.perez@grupobimbo.com", "user": SSO["X-Forwarded-User"],
        "username": "ana.perez@grupobimbo.com", "verified": False, "user_token_forwarded": False}
    monkeypatch.setattr(identity, "user_client", lambda t: FakeUserClient("ana.perez@grupobimbo.com"))
    j = client.get("/api/me", headers={**SSO, "X-Forwarded-Access-Token": "tok"}).json()
    assert j["verified"] is True and j["user_token_forwarded"] is True


def test_rows_cover_every_sql_parameter(client):
    client.post("/api/register", json=REG, headers=SSO)
    client.post("/api/newsletter", json={"email": "luis@gbsupport.net"}, headers=SSO)

    def params(sql):
        return set(re.findall(r"%\((\w+)\)s", sql))

    assert params(store.UPSERT_REGISTRATION) <= set(client.main.store.registrations["ana.perez@grupobimbo.com"])
    assert params(store.UPSERT_NEWSLETTER) <= set(client.main.store.newsletter["luis@gbsupport.net"])


@pytest.mark.parametrize("email", ["x@gmail.com", "x@grupobimbo.com.mx", "x@evil-grupobimbo.com", "sin-arroba"])
def test_backend_domain_validation(client, email):
    r = client.post("/api/register", json={**REG, "email": email})
    assert r.status_code == 422 and r.json()["errors"][0]["field"] == "email"
    assert client.post("/api/newsletter", json={"email": email}).status_code == 422


def test_register_rejects_bad_fields(client):
    assert client.post("/api/register", json={**REG, "trainingLanguage": "fr"}).status_code == 422
    assert client.post("/api/register", json={**REG, "name": " "}).status_code == 422


def test_newsletter(client):
    body = {"email": "Luis@gbsupport.net", "lang": "en", "source": "BimboBricks IQ newsletter", "ts": "2026-09-26T10:00:00Z"}
    assert client.post("/api/newsletter", json=body).json()["created"] is True
    assert "luis@gbsupport.net" in client.main.store.newsletter


def test_index_injects_news_and_caches(client):
    r = client.get("/")
    assert r.status_code == 200 and 'registrationEndpoint: "/api/register"' in r.text
    etag = r.headers["etag"]
    assert client.get("/", headers={"If-None-Match": etag}).status_code == 304

    (client.vol / "news" / "news_block.html").write_text(
        '<section id="bb-dbx-news"><h3>NOTICIA NUEVA</h3></section>', encoding="utf-8")
    client.main.news_file._at = float("-inf")  # fuerza relectura (TTL)
    r = client.get("/", headers={"Accept-Encoding": "identity"})
    assert "NOTICIA NUEVA" in r.text and r.headers["etag"] != etag
    raw = client.get("/", headers={"Accept-Encoding": "gzip"})
    assert "NOTICIA NUEVA" in raw.text  # httpx descomprime


def test_video_range(client):
    full = client.get("/media/video.mp4")
    assert full.status_code == 200 and len(full.content) == 1024
    part = client.get("/media/video.mp4", headers={"Range": "bytes=10-19"})
    assert part.status_code == 206 and part.content == bytes(range(10, 20))
    assert part.headers["content-range"] == "bytes 10-19/1024"
    tail = client.get("/media/video.mp4", headers={"Range": "bytes=-4"})
    assert tail.content == bytes(range(252, 256))
    assert client.get("/media/video.mp4", headers={"Range": "bytes=5000-"}).status_code == 416


def test_healthz(client):
    j = client.get("/healthz").json()
    assert j["store"] == "memory" and j["store_ok"] is True
    assert client.get("/api/health").json() == j
