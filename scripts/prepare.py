#!/usr/bin/env python3
"""Prepara el HTML del dueño para publicarlo en la Databricks App.

Se ejecuta solo como hook `predeploy` de `databricks bundle deploy` (y desde deploy.sh).
Entrada : el único *.html dentro de html/
Salida  : app/static/index.html  (HTML listo para servir, sin el vídeo base64)
          app/static/build.json  (manifiesto: origen, hashes, tamaños)
          build/video.mp4        (vídeo extraído; deploy.sh lo sube al Volume)

Contrato con el HTML (si algo falta, el deploy se detiene con un mensaje claro):
  - <form id="regForm"> y <form id="bbNl">
  - CONFIG.registrationEndpoint: "..."   -> se cablea a /api/register
  - var NL_ENDPOINT = "..."             -> se cablea a /api/newsletter
  - (opcional, desde v13) CONFIG.ideasEndpoint / CONFIG.accessEndpoint -> /api/ideas y /api/access-requests
  - (opcional) <script type="application/octet-stream" id="bbVideoData"> con el mp4 en base64
  - <section id="bb-dbx-news"> o, si no existe, <form class="bb-nl" id="bbNl"> como ancla

Solo usa la librería estándar (Python >= 3.9).
"""
import base64
import binascii
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HTML_DIR = ROOT / "html"
OUT_HTML = ROOT / "app" / "static" / "index.html"
OUT_MANIFEST = ROOT / "app" / "static" / "build.json"
OUT_VIDEO = ROOT / "build" / "video.mp4"

API_REGISTER = "/api/register"
API_NEWSLETTER = "/api/newsletter"
# Formularios "Envía tu idea" y "Solicita tu acceso" (v13+). Si el HTML no los trae, no se cablean.
OPTIONAL_ENDPOINTS = (
    ("ideasEndpoint", "/api/ideas", "Ideas (CONFIG.ideasEndpoint)"),
    ("accessEndpoint", "/api/access-requests", "Solicitudes de acceso (CONFIG.accessEndpoint)"),
)
VIDEO_URL = "/media/video.mp4"
NEWS_START = "<!--BB_NEWS_START-->"
NEWS_END = "<!--BB_NEWS_END-->"
MAX_APP_FILE_BYTES = 9_500_000  # las Apps limitan cada archivo a 10 MB

NEWS_CSS = """
/* Databricks al día */
#bb-dbx-news{margin:30px 0 6px}
#bb-dbx-news h3{color:#fff;margin:0 0 4px;font-size:22px}
.bb-dn-sub{color:rgba(255,255,255,.82);margin:0 0 14px;font-weight:700}
.bb-dn-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:16px}
@media (max-width:1100px){.bb-dn-grid{grid-template-columns:repeat(2,1fr)}}
@media (max-width:560px){.bb-dn-grid{grid-template-columns:1fr}}
.bb-dn{display:flex;flex-direction:column;gap:8px;background:#fff;border:2px solid var(--card-border);border-left:6px solid #FF3621;border-radius:var(--radius-sm);padding:16px;text-decoration:none;color:var(--navy);box-shadow:var(--shadow);transition:transform .2s ease}
.bb-dn:hover{transform:translateY(-3px)}
.bb-dn-tag{font-size:12px;font-weight:900;letter-spacing:.04em;text-transform:uppercase;color:#C0301A}
.bb-dn strong{font-size:16px;line-height:1.3}
.bb-dn p{margin:0;color:var(--muted);font-size:14px;line-height:1.45}
.bb-dn-src{margin-top:auto;font-size:13px;font-weight:800;color:var(--blue)}
"""

# Bloque vacío si el HTML no trae noticias y el Job aún no ha publicado ninguna.
EMPTY_NEWS = (
    '<section id="bb-dbx-news" aria-labelledby="bb-dn-h">'
    '<h3 id="bb-dn-h"><span class="bb-es">⚡ Databricks al día</span><span class="bb-en">⚡ Databricks today</span><span class="bb-pt">⚡ Databricks em dia</span></h3>'
    '<p class="bb-dn-sub"><span class="bb-es">Muy pronto: lo último de Databricks.</span>'
    '<span class="bb-en">Coming soon: the latest from Databricks.</span>'
    '<span class="bb-pt">Em breve: o mais recente da Databricks.</span></p>'
    '<div class="bb-dn-grid"></div></section>'
)


class ContractError(Exception):
    pass


def find_source(html_dir=HTML_DIR):
    files = sorted(p for p in Path(html_dir).glob("*.html") if not p.name.startswith("."))
    if len(files) != 1:
        names = ", ".join(p.name for p in files) or "(ninguno)"
        raise ContractError(
            "html/ debe contener exactamente UN archivo .html (encontrados: %s). "
            "Borra la versión anterior y deja solo la nueva." % names
        )
    return files[0]


def _replace_once(h, pattern, repl, what):
    matches = list(re.finditer(pattern, h))
    if len(matches) != 1:
        raise ContractError("%s: se esperaba 1 coincidencia de /%s/, hay %d." % (what, pattern, len(matches)))
    m = matches[0]
    return h[: m.start()] + repl(m) + h[m.end():]


def wire_endpoints(h):
    h = _replace_once(
        h, r'registrationEndpoint\s*:\s*"[^"]*"',
        lambda m: 'registrationEndpoint: "%s"' % API_REGISTER, "Registro (CONFIG.registrationEndpoint)")
    h = _replace_once(
        h, r'NL_ENDPOINT\s*=\s*"[^"]*"',
        lambda m: 'NL_ENDPOINT="%s"' % API_NEWSLETTER, "Newsletter (NL_ENDPOINT)")
    for key, api, what in OPTIONAL_ENDPOINTS:
        pattern = r'\b%s\s*:\s*"[^"]*"' % key
        if re.search(pattern, h):
            h = _replace_once(h, pattern, lambda m, key=key, api=api: '%s: "%s"' % (key, api), what)
    return h


def extract_video(h):
    """Devuelve (html, bytes_del_video | None)."""
    m = re.search(r'<script\b[^>]*\bid="bbVideoData"[^>]*>([\s\S]*?)</script>', h)
    if not m:
        return h, None
    b64 = re.sub(r"\s+", "", m.group(1))
    try:
        video = base64.b64decode(b64, validate=True)
    except (binascii.Error, ValueError) as e:
        raise ContractError("bbVideoData no es base64 válido: %s" % e)
    if video[4:8] != b"ftyp":
        raise ContractError("bbVideoData no parece un .mp4 (falta la caja 'ftyp').")
    ver = hashlib.sha256(video).hexdigest()[:12]
    # Se sustituye el <script id="bbVideoData"> por esta URL. El script que antes decodificaba
    # el base64 no encuentra el elemento, cae en su try/catch y deja __bbVideoUrl intacto;
    # CONFIG.videoMain lo lee tal cual.
    shim = '<script>window.__bbVideoUrl="%s?v=%s";</script>' % (VIDEO_URL, ver)
    return h[: m.start()] + shim + h[m.end():], video


def mark_news(h):
    m = re.search(r'<section id="bb-dbx-news"[\s\S]*?</section>', h)
    if m:
        return h[: m.start()] + NEWS_START + m.group(0) + NEWS_END + h[m.end():]
    anchor = '<form class="bb-nl" id="bbNl"'
    i = h.find(anchor)
    if i < 0:
        raise ContractError('No hay <section id="bb-dbx-news"> ni el ancla %s para insertar noticias.' % anchor)
    return h[:i] + NEWS_START + EMPTY_NEWS + NEWS_END + "\n    " + h[i:]


def ensure_news_css(h):
    if "#bb-dbx-news{" in h:
        return h
    t = h.find('id="bb-theme"')
    j = h.find("</style>", t if t >= 0 else 0)
    if j < 0:
        raise ContractError("No hay ningún </style> donde insertar el CSS de noticias.")
    return h[:j] + NEWS_CSS + h[j:]


def check_forms(h):
    for needle, what in (('id="regForm"', "formulario de registro"), ('id="bbNl"', "formulario de newsletter")):
        if needle not in h:
            raise ContractError("Falta el %s (%s)." % (what, needle))
    if "__bbVideoUrl" not in h:
        print("AVISO: CONFIG ya no lee window.__bbVideoUrl; el vídeo del Volume no se usará.", file=sys.stderr)


def build(src, out_html=OUT_HTML, out_manifest=OUT_MANIFEST, out_video=OUT_VIDEO):
    raw = Path(src).read_text(encoding="utf-8")
    check_forms(raw)
    h = wire_endpoints(raw)
    h, video = extract_video(h)
    h = mark_news(h)
    h = ensure_news_css(h)

    data = h.encode("utf-8")
    if len(data) > MAX_APP_FILE_BYTES:
        raise ContractError(
            "El HTML preparado pesa %.1f MB (> %.1f MB permitido por Apps). "
            "Reduce imágenes base64 o muévelas al Volume." % (len(data) / 1e6, MAX_APP_FILE_BYTES / 1e6))

    out_html, out_manifest, out_video = Path(out_html), Path(out_manifest), Path(out_video)
    out_html.parent.mkdir(parents=True, exist_ok=True)
    out_html.write_bytes(data)
    raw_bytes = raw.encode("utf-8")
    manifest = {
        "source_file": Path(src).name,
        "source_sha256": hashlib.sha256(raw_bytes).hexdigest(),
        "source_mb": round(len(raw_bytes) / 1e6, 2),
        "output_sha256": hashlib.sha256(data).hexdigest(),
        "output_mb": round(len(data) / 1e6, 2),
        "video_sha256": hashlib.sha256(video).hexdigest() if video else None,
        "video_mb": round(len(video) / 1e6, 2) if video else None,
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    out_manifest.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if video:
        out_video.parent.mkdir(parents=True, exist_ok=True)
        out_video.write_bytes(video)
    elif out_video.exists():
        out_video.unlink()
    return manifest


def main():
    try:
        m = build(find_source())
    except ContractError as e:
        print("\n✖ prepare.py: el HTML no cumple el contrato.\n  %s\n" % e, file=sys.stderr)
        return 1
    print("✔ %s (%.2f MB) → app/static/index.html (%.2f MB)%s" % (
        m["source_file"], m["source_mb"], m["output_mb"],
        "; vídeo → build/video.mp4 (%.2f MB)" % m["video_mb"] if m["video_mb"] else "; sin vídeo embebido"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
