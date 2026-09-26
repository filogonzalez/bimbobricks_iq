"""Prueba la App con almacén en memoria y un 'Volume' local (sin Databricks)."""
import gzip
import importlib

import pytest
from fastapi.testclient import TestClient

REG = {"name": "Ana Pérez", "email": "Ana.Perez@GrupoBimbo.com", "country": "MX", "area": "Finanzas",
       "kickoff": True, "kickoffMode": "remote", "wave": True, "trainingLanguage": "es",
       "selfAssessmentDone": True, "uiLanguage": "es", "submittedAt": "2026-09-26T10:00:00Z",
       "source": "bimbobricks-iq-landing-wave2", "campoNuevo": 42}


@pytest.fixture
def client(tmp_path, monkeypatch):
    (tmp_path / "media").mkdir()
    (tmp_path / "news").mkdir()
    (tmp_path / "media" / "video.mp4").write_bytes(bytes(range(256)) * 4)
    monkeypatch.setenv("MEDIA_VOLUME", str(tmp_path))
    monkeypatch.delenv("PGHOST", raising=False)
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
