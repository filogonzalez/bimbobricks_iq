"""Publica el bloque 'Databricks al día' a partir de un items.json subido a mano.

Sustituye a _proceso-noticias/dbx_news.py: ya no reescribe el HTML. Genera
<media>/news/news_block.html, que la App inserta en caliente (se refresca en ~1 min).

Flujo (Job con disparo por llegada de archivo al Volume `news_inbox`):
  1. Toma los *.json del inbox (el más reciente gana si hay varios).
  2. Valida la estructura. Si es inválido → rejected/ + error.txt y el Job falla (avisa por correo).
  3. Escribe news/news.json y news/news_block.html; archiva el original en news/archive/.
  4. Vacía el inbox.

Formato de items.json (igual que antes):
  {"updated_es": "...", "updated_en": "...",
   "items": [{"date_es","date_en","tag_es","tag_en","title_es","title_en","sum_es","sum_en","url","source"}]}
"""
import argparse
import html as H
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ITEM_KEYS = ("date_es", "date_en", "tag_es", "tag_en", "title_es", "title_en", "sum_es", "sum_en", "url", "source")
MAX_ITEMS = 12
e = H.escape


class InvalidItems(ValueError):
    pass


def validate(data):
    if not isinstance(data, dict):
        raise InvalidItems("La raíz debe ser un objeto JSON.")
    for k in ("updated_es", "updated_en"):
        if not isinstance(data.get(k), str):
            raise InvalidItems("Falta '%s' (texto)." % k)
    items = data.get("items")
    if not isinstance(items, list) or not items:
        raise InvalidItems("'items' debe ser una lista no vacía.")
    if len(items) > MAX_ITEMS:
        raise InvalidItems("Máximo %d items (hay %d)." % (MAX_ITEMS, len(items)))
    for n, it in enumerate(items, 1):
        if not isinstance(it, dict):
            raise InvalidItems("Item %d no es un objeto." % n)
        missing = [k for k in ITEM_KEYS if not isinstance(it.get(k), str) or not it[k].strip()]
        if missing:
            raise InvalidItems("Item %d: faltan o están vacíos %s." % (n, ", ".join(missing)))
        if not it["url"].startswith("https://"):
            raise InvalidItems("Item %d: la url debe empezar por https://" % n)
    return data


def card(it):
    return (f'<a class="bb-dn" href="{e(it["url"])}" target="_blank" rel="noopener noreferrer">'
            f'<span class="bb-dn-tag"><span class="bb-es">{e(it["tag_es"])} · {e(it["date_es"])}</span><span class="bb-en">{e(it["tag_en"])} · {e(it["date_en"])}</span></span>'
            f'<strong><span class="bb-es">{e(it["title_es"])}</span><span class="bb-en">{e(it["title_en"])}</span></strong>'
            f'<p><span class="bb-es">{e(it["sum_es"])}</span><span class="bb-en">{e(it["sum_en"])}</span></p>'
            f'<span class="bb-dn-src"><span class="bb-es">Fuente: {e(it["source"])} · Leer →</span><span class="bb-en">Source: {e(it["source"])} · Read →</span></span></a>')


def block(data):
    return ('<section id="bb-dbx-news" aria-labelledby="bb-dn-h">'
            '<h3 id="bb-dn-h"><span class="bb-es">⚡ Databricks al día</span><span class="bb-en">⚡ Databricks today</span></h3>'
            f'<p class="bb-dn-sub"><span class="bb-es">Lo último de Databricks que importa para tus datos. {e(data["updated_es"])}</span>'
            f'<span class="bb-en">The latest from Databricks that matters for your data. {e(data["updated_en"])}</span></p>'
            '<div class="bb-dn-grid">' + ''.join(card(i) for i in data['items']) + '</div></section>')


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    try:
        tmp.replace(path)
    except OSError:  # por si el FUSE del Volume no soporta rename
        path.write_text(text, encoding="utf-8")
        tmp.unlink(missing_ok=True)


def publish(inbox, media, items_file=None, now=None):
    inbox, media = Path(inbox), Path(media)
    stamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%dT%H%M%SZ")
    news = media / "news"
    if items_file:
        pending = [Path(items_file)]
    else:
        pending = sorted((p for p in inbox.glob("*.json") if p.is_file()), key=lambda p: p.stat().st_mtime)
    if not pending:
        print("Inbox vacío: nada que publicar.")
        return None

    src = pending[-1]
    try:
        data = validate(json.loads(src.read_text(encoding="utf-8")))
    except (InvalidItems, json.JSONDecodeError, UnicodeDecodeError) as err:
        rej = news / "rejected"
        rej.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, rej / f"{stamp}_{src.name}")
        (rej / f"{stamp}_{src.name}.error.txt").write_text(str(err) + "\n", encoding="utf-8")
        if not items_file:
            src.unlink()
        raise SystemExit(f"✖ {src.name} rechazado: {err}")

    _write(news / "news.json", json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    _write(news / "news_block.html", block(data))
    arch = news / "archive"
    arch.mkdir(parents=True, exist_ok=True)
    for p in pending:
        shutil.copyfile(p, arch / f"{stamp}_{p.name}")
        if not items_file:
            p.unlink()
    print(f"✔ Publicadas {len(data['items'])} noticias desde {src.name} → {news / 'news_block.html'}")
    return data


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--inbox", required=True, help="/Volumes/<cat>/<schema>/news_inbox")
    ap.add_argument("--media", required=True, help="/Volumes/<cat>/<schema>/media")
    ap.add_argument("--items", default="", help="(opcional) publicar un archivo concreto sin tocar el inbox")
    a = ap.parse_args(argv)
    publish(a.inbox, a.media, a.items or None)


if __name__ == "__main__":
    main(sys.argv[1:])
