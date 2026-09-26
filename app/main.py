"""BimboBricks IQ · Ola 2 — Databricks App (FastAPI).

GET  /                 HTML preparado por scripts/prepare.py + bloque de noticias vigente del Volume
GET  /media/video.mp4  vídeo desde el Volume, con soporte Range
POST /api/register     registro  → Lakebase forms.registrations
POST /api/newsletter   newsletter → Lakebase forms.newsletter_subscriptions
GET  /healthz          estado (build, almacén)
"""
import gzip
import hashlib
import json
import logging
import os
import re
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response

from models import Newsletter, Registration
from store import make_store, to_json
from volume import CachedFile, VolumeReader

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
log = logging.getLogger("bimbobricks")

STATIC = Path(__file__).parent / "static"
NEWS_START, NEWS_END = "<!--BB_NEWS_START-->", "<!--BB_NEWS_END-->"
NEWS_TTL = int(os.getenv("NEWS_TTL_SECONDS", "60"))
VIDEO_TTL = int(os.getenv("VIDEO_TTL_SECONDS", "3600"))


class Page:
    """Divide el HTML en prefijo / bloque de noticias / sufijo y cachea el resultado por versión."""

    def __init__(self, html):
        i, j = html.find(NEWS_START), html.find(NEWS_END)
        if i < 0 or j < i:
            raise RuntimeError("index.html sin marcadores de noticias: ejecuta scripts/prepare.py")
        self.prefix = html[: i + len(NEWS_START)].encode("utf-8")
        self.fallback = html[i + len(NEWS_START): j].encode("utf-8")
        self.suffix = html[j:].encode("utf-8")
        self.build_id = hashlib.sha256(html.encode("utf-8")).hexdigest()[:16]
        self._key = self._body = self._gz = None

    def render(self, news_block):
        block = news_block if news_block and b'id="bb-dbx-news"' in news_block else self.fallback
        key = hashlib.sha256(block).hexdigest()[:16]
        if key != self._key:
            body = self.prefix + block + self.suffix
            self._body, self._gz, self._key = body, gzip.compress(body, 6), key
        return self._body, self._gz, '"%s-%s"' % (self.build_id, key)


def _load_page():
    return Page((STATIC / "index.html").read_text(encoding="utf-8"))


reader = VolumeReader()
news_file = CachedFile(reader, "news/news_block.html", NEWS_TTL)
video_file = CachedFile(reader, "media/video.mp4", VIDEO_TTL)
page = _load_page()
store = make_store()
BUILD = json.loads((STATIC / "build.json").read_text(encoding="utf-8")) if (STATIC / "build.json").exists() else {}

app = FastAPI(title="BimboBricks IQ", docs_url=None, redoc_url=None, openapi_url=None)


def _sso_email(request: Request):
    return (request.headers.get("x-forwarded-email") or "").strip().lower() or None


@app.exception_handler(RequestValidationError)
async def _invalid(request: Request, exc: RequestValidationError):
    errors = [{"field": ".".join(str(p) for p in e["loc"][1:]), "msg": e["msg"]} for e in exc.errors()]
    return JSONResponse({"ok": False, "errors": errors}, status_code=422)


@app.get("/")
@app.get("/index.html")
def index(request: Request):
    body, gz, etag = page.render(news_file.get())
    headers = {"ETag": etag, "Cache-Control": "no-cache", "Vary": "Accept-Encoding"}
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)
    if "gzip" in request.headers.get("accept-encoding", ""):
        headers["Content-Encoding"] = "gzip"
        body = gz
    return Response(body, media_type="text/html; charset=utf-8", headers=headers)


_RANGE = re.compile(r"bytes=(\d*)-(\d*)$")


@app.get("/media/video.mp4")
def video(request: Request):
    data = video_file.get()
    if not data:
        return Response("Vídeo no disponible", status_code=404)
    size = len(data)
    headers = {"Accept-Ranges": "bytes", "Cache-Control": "public, max-age=86400"}
    m = _RANGE.match(request.headers.get("range", "").strip())
    if not m or (not m.group(1) and not m.group(2)):
        return Response(data, media_type="video/mp4", headers=headers)
    if m.group(1):
        start = int(m.group(1))
        end = min(int(m.group(2)) if m.group(2) else size - 1, size - 1)
    else:  # bytes=-N → últimos N bytes
        start, end = max(size - int(m.group(2)), 0), size - 1
    if start >= size or start > end:
        return Response(status_code=416, headers={"Content-Range": "bytes */%d" % size})
    headers["Content-Range"] = "bytes %d-%d/%d" % (start, end, size)
    return Response(data[start: end + 1], status_code=206, media_type="video/mp4", headers=headers)


def _save(fn, row):
    try:
        return {"ok": True, "created": fn(row)}, 200
    except Exception:  # noqa: BLE001
        log.exception("Error guardando en %s", store.kind)
        return {"ok": False, "error": "storage_unavailable"}, 503


@app.post("/api/register")
def register(reg: Registration, request: Request):
    row = reg.model_dump()
    row["raw"] = to_json(reg.model_dump(by_alias=True))
    row["sso_email"] = _sso_email(request)
    body, status = _save(store.upsert_registration, row)
    return JSONResponse(body, status_code=status)


@app.post("/api/newsletter")
def newsletter(sub: Newsletter, request: Request):
    row = sub.model_dump(include={"email", "lang", "source", "ts"})
    row["sso_email"] = _sso_email(request)
    body, status = _save(store.upsert_newsletter, row)
    return JSONResponse(body, status_code=status)


@app.get("/healthz")
def healthz():
    try:
        db = store.ping()
    except Exception:  # noqa: BLE001
        log.exception("healthz: almacén no disponible")
        db = False
    return {"ok": True, "store": store.kind, "store_ok": db, "media_root": reader.root or None,
            "build": {k: BUILD.get(k) for k in ("source_file", "output_sha256", "built_at")}}
