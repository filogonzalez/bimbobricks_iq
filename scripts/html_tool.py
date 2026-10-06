#!/usr/bin/env python3
"""Herramienta para inspeccionar y editar el HTML de BimboBricks IQ sin abrir sus 8+ MB.

El HTML trae imágenes y un vídeo en base64 (líneas de hasta 8 MB), así que no conviene
leerlo entero ni editarlo "a mano". Todos los comandos ocultan los blobs como «blob:mime:KB».

  python3 scripts/html_tool.py outline                     mapa: secciones, scripts, CONFIG, i18n, blobs
  python3 scripts/html_tool.py find "Clase magistral" [-C 200] [--regex]
  python3 scripts/html_tool.py show registro [--max 6000]   elemento con id="registro"
  python3 scripts/html_tool.py replace --old "…" --new "…" [--count N] [--dry-run]
  python3 scripts/html_tool.py replace --old-file a.txt --new-file b.txt
  python3 scripts/html_tool.py i18n heroSub                 ver texto ES/EN/PT de una clave data-i18n
  python3 scripts/html_tool.py i18n heroSub --es "…" --en "…" --pt "…"
  python3 scripts/html_tool.py blobs                        lista imágenes/vídeo embebidos
  python3 scripts/html_tool.py set-blob 3 nueva.webp        sustituye la imagen nº 3
  python3 scripts/html_tool.py set-video nuevo.mp4          sustituye el vídeo embebido
  python3 scripts/html_tool.py check                        contrato del deploy + paridad ES/EN
  python3 scripts/html_tool.py bump [--label cta-academy]   renombra a la siguiente versión (v12 → v13)

Por defecto trabaja sobre el único .html de html/ (o --file RUTA). Solo librería estándar.
"""
import argparse
import base64
import mimetypes
import re
import subprocess
import sys
import tempfile
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import prepare  # noqa: E402

BLOB_RE = re.compile(r"data:([a-z]+/[a-z0-9.+-]+);base64,([A-Za-z0-9+/=]{200,})")
VIDEO_RE = re.compile(r'(<script\b[^>]*\bid="bbVideoData"[^>]*>)([\s\S]*?)(</script>)')


# ───────────────────────── utilidades ─────────────────────────

def load(path):
    return Path(path).read_text(encoding="utf-8")


def save(path, h):
    Path(path).write_text(h, encoding="utf-8")


def elide(s):
    s = BLOB_RE.sub(lambda m: "data:%s;base64,«blob:%s:%dKB»" % (m.group(1), m.group(1), len(m.group(2)) * 3 // 4096), s)
    return re.sub(r"[A-Za-z0-9+/=\s]{20000,}", lambda m: "«base64:%dKB»" % (len(m.group(0)) * 3 // 4096), s)


def lineno(h, i):
    return h.count("\n", 0, i) + 1


def js_block(h, start):
    """Dado el índice de una '{', devuelve el índice de su '}' pareja (ignora strings y comentarios JS)."""
    depth, i, n = 0, start, len(h)
    while i < n:
        c = h[i]
        if c in "\"'`":
            q, i = c, i + 1
            while i < n and h[i] != q:
                i += 2 if h[i] == "\\" else 1
        elif c == "/" and h[i + 1: i + 2] == "/":
            i = h.find("\n", i)
            i = n if i < 0 else i
        elif c == "/" and h[i + 1: i + 2] == "*":
            i = h.find("*/", i + 2) + 1
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    raise ValueError("llave sin cerrar desde %d" % start)


LANGS = ("es", "en", "pt")


def i18n_blocks(h):
    """Rangos (inicio, fin) de T.es, T.en y T.pt dentro de `const T = {…}`."""
    t = h.find("const T = {")
    if t < 0:
        raise SystemExit("No se encontró `const T = {` (diccionario i18n).")
    t_end = js_block(h, h.index("{", t))
    out = {}
    for lang in LANGS:
        m = re.compile(r"\b%s\s*:\s*\{" % lang).search(h, t, t_end)
        if not m:
            raise SystemExit("T.%s no encontrado" % lang)
        b = m.end() - 1
        out[lang] = (b, js_block(h, b))
    return out


KEY_RE = r'(?<![\w$])%s\s*:\s*(?:"((?:[^"\\]|\\.)*)"|\'((?:[^\'\\]|\\.)*)\')'


def i18n_keys(h, rng):
    body = h[rng[0]: rng[1]]
    return set(re.findall(r'(?<![\w$.])([A-Za-z_$][\w$]*)\s*:\s*["\'`]', body))


def js_str(s, q='"'):
    return s.replace("\\", "\\\\").replace(q, "\\" + q).replace("\n", "\\n")


def key_match(h, key, rng):
    """(match, grupo) de `key:"…"` o `key:'…'` dentro del rango; grupo 1 = comillas dobles, 2 = simples."""
    m = re.compile(KEY_RE % re.escape(key)).search(h, *rng)
    return (m, 1 if m and m.group(1) is not None else 2) if m else (None, None)


# ───────────────────────── comandos ─────────────────────────

def cmd_outline(a, h):
    print("Archivo: %s  (%.2f MB, %d líneas)" % (a.file, len(h.encode()) / 1e6, h.count("\n") + 1))
    print("\nSecciones (<section id>):")
    for m in re.finditer(r'<section\b[^>]*\bid="([^"]+)"', h):
        print("  L%-5d #%s" % (lineno(h, m.start()), m.group(1)))
    print("\nBloques <style>/<script>:")
    # Los comentarios se sustituyen por espacios del mismo tamaño para conservar los offsets.
    nocom = re.sub(r"<!--[\s\S]*?-->", lambda c: re.sub(r"[^\n]", " ", c.group(0)), h)
    for m in re.finditer(r"<(style|script)\b([^>]*)>", nocom):
        end = nocom.find("</%s>" % m.group(1), m.end())
        print("  L%-5d <%s%s>  %d KB" % (lineno(h, m.start()), m.group(1), m.group(2)[:60], (end - m.end()) // 1024))
    print("\nConstantes JS:")
    for m in re.finditer(r"\n\s*const ([A-Z_][A-Za-z0-9_]*)\s*=", h):
        print("  L%-5d %s" % (lineno(h, m.start() + 1), m.group(1)))
    i = h.find("const CONFIG = {")
    if i >= 0:
        body = h[i: js_block(h, h.index("{", i)) + 1]
        keys = re.findall(r"^\s{2}([A-Za-z_]\w*)\s*:", body, re.M)
        print("\nCONFIG: " + ", ".join(keys))
    try:
        b = i18n_blocks(h)
        print("\ni18n T.es: %d · T.en: %d · T.pt: %d claves · data-i18n en HTML: %d · pares bb-es/bb-en/bb-pt: %d/%d/%d" % (
            len(i18n_keys(h, b["es"])), len(i18n_keys(h, b["en"])), len(i18n_keys(h, b["pt"])), h.count("data-i18n"),
            h.count('class="bb-es"'), h.count('class="bb-en"'), h.count('class="bb-pt"')))
    except SystemExit as e:
        print("\ni18n: %s" % e)
    blobs = list(BLOB_RE.finditer(h))
    v = VIDEO_RE.search(h)
    print("\nBlobs embebidos: %d imágenes (%d KB)%s" % (
        len(blobs), sum(len(m.group(2)) for m in blobs) * 3 // 4096,
        "; vídeo bbVideoData %.1f MB" % (len(v.group(2)) * 3 / 4 / 1e6) if v else "; sin vídeo embebido"))
    print("\nContrato del deploy: ejecuta `check`.")


def cmd_find(a, h):
    pat = re.compile(a.pattern if a.regex else re.escape(a.pattern), re.I if a.ignore_case else 0)
    hits = list(pat.finditer(h))
    print("%d coincidencia(s)" % len(hits))
    for m in hits[: a.limit]:
        s, e = max(0, m.start() - a.context), min(len(h), m.end() + a.context)
        print("\n── L%d  offset %d" % (lineno(h, m.start()), m.start()))
        print(elide(h[s:m.start()]) + "⟦" + elide(m.group(0)) + "⟧" + elide(h[m.end():e]))
    if len(hits) > a.limit:
        print("\n… %d más (usa --limit)" % (len(hits) - a.limit))


VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}


def element_span(h, el_id):
    m = re.search(r'<([a-zA-Z][\w-]*)\b[^>]*\bid="%s"[^>]*>' % re.escape(el_id), h)
    if not m:
        raise SystemExit('No hay ningún elemento con id="%s".' % el_id)
    tag = m.group(1).lower()
    if tag in VOID:
        return m.start(), m.end()
    depth, pos = 1, m.end()
    tok = re.compile(r"<(/?)%s\b[^>]*>" % tag, re.I)
    while depth:
        t = tok.search(h, pos)
        if not t:
            raise SystemExit("<%s id=%s> sin cierre" % (tag, el_id))
        depth += -1 if t.group(1) else 1
        pos = t.end()
    return m.start(), pos


def cmd_show(a, h):
    s, e = element_span(h, a.id)
    out = elide(h[s:e])
    print("── #%s  L%d–L%d  (%d caracteres)\n" % (a.id, lineno(h, s), lineno(h, e), e - s))
    print(out[: a.max] + ("\n… (recortado; usa --max)" if len(out) > a.max else ""))


def cmd_replace(a, h):
    old = Path(a.old_file).read_text(encoding="utf-8") if a.old_file else a.old
    new = Path(a.new_file).read_text(encoding="utf-8") if a.new_file else a.new
    if old is None or new is None:
        raise SystemExit("Indica --old/--old-file y --new/--new-file.")
    n = h.count(old)
    if n != a.count:
        raise SystemExit("✖ Se esperaban %d coincidencia(s) del texto a reemplazar y hay %d. "
                         "Amplía el contexto de --old para que sea único (o usa --count)." % (a.count, n))
    if a.dry_run:
        print("✔ (dry-run) %d reemplazo(s) en L%d" % (n, lineno(h, h.index(old))))
        return
    save(a.file, h.replace(old, new))
    print("✔ %d reemplazo(s) en L%d" % (n, lineno(h, h.index(old))))


def cmd_i18n(a, h):
    b = i18n_blocks(h)
    if a.es is None and a.en is None and a.pt is None:
        for lang in LANGS:
            m, g = key_match(h, a.key, b[lang])
            print("%s: %s" % (lang, m.group(g) if m else "(no existe)"))
        return
    # Se aplica de atrás hacia delante para no invalidar los offsets.
    for lang in ("pt", "en", "es"):
        val = getattr(a, lang)
        if val is None:
            continue
        s, e = b[lang]
        m, g = key_match(h, a.key, (s, e))
        if m:
            h = h[: m.start(g)] + js_str(val, '"' if g == 1 else "'") + h[m.end(g):]
        elif a.create:
            h = h[: s + 1] + '\n  %s:"%s",' % (a.key, js_str(val)) + h[s + 1:]
        else:
            raise SystemExit("La clave '%s' no existe en T.%s (usa --create para añadirla)." % (a.key, lang))
    save(a.file, h)
    print("✔ i18n '%s' actualizado" % a.key)


def blob_context(h, m):
    pre = h[max(0, m.start() - 300): m.start()]
    tag = pre[pre.rfind("<"):] if "<" in pre else ""
    key = re.search(r"(\w+)\s*:\s*\"$", pre)
    hint = re.search(r'(?:class|alt|id)="([^"]{0,60})"', tag)
    return (key and "IMG." + key.group(1)) or (hint and hint.group(0)) or elide(pre[-80:]).replace("\n", " ")


def cmd_blobs(a, h):
    for n, m in enumerate(BLOB_RE.finditer(h)):
        print("%2d  L%-5d %-11s %5d KB  %s" % (n, lineno(h, m.start()), m.group(1), len(m.group(2)) * 3 // 4096, blob_context(h, m)))
    v = VIDEO_RE.search(h)
    if v:
        print(" V  L%-5d video/mp4   %5d KB  <script id=\"bbVideoData\"> (usa set-video)" % (
            lineno(h, v.start()), len(re.sub(r"\s", "", v.group(2))) * 3 // 4096))


def cmd_set_blob(a, h):
    blobs = list(BLOB_RE.finditer(h))
    if not 0 <= a.index < len(blobs):
        raise SystemExit("Índice fuera de rango (0–%d). Usa `blobs`." % (len(blobs) - 1))
    m = blobs[a.index]
    mime = mimetypes.guess_type(a.image)[0] or m.group(1)
    if not mime.startswith("image/"):
        raise SystemExit("%s no parece una imagen" % a.image)
    data = base64.b64encode(Path(a.image).read_bytes()).decode()
    save(a.file, h[: m.start()] + "data:%s;base64,%s" % (mime, data) + h[m.end():])
    print("✔ blob %d → %s (%d KB)" % (a.index, mime, len(data) * 3 // 4096))


def cmd_set_video(a, h):
    v = VIDEO_RE.search(h)
    if not v:
        raise SystemExit('No hay <script id="bbVideoData"> en el HTML.')
    raw = Path(a.video).read_bytes()
    if raw[4:8] != b"ftyp":
        raise SystemExit("%s no parece un .mp4" % a.video)
    b64 = base64.b64encode(raw).decode()
    save(a.file, h[: v.start(2)] + "\n" + b64 + "\n" + h[v.end(2):])
    print("✔ vídeo sustituido (%.1f MB)" % (len(raw) / 1e6))


class _Balance(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.problems = [], []

    def handle_starttag(self, tag, attrs):
        if tag not in VOID:
            self.stack.append((tag, self.getpos()[0]))

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                for t, ln in self.stack[i + 1:]:
                    if t not in ("p", "li", "option", "tr", "td", "th", "dt", "dd"):  # cierre implícito válido
                        self.problems.append("<%s> abierto en L%d sin cerrar antes de </%s> (L%d)" % (t, ln, tag, self.getpos()[0]))
                del self.stack[i:]
                return
        self.problems.append("</%s> sin apertura en L%d" % (tag, self.getpos()[0]))


def cmd_check(a, h):
    errors, warnings = [], []
    with tempfile.TemporaryDirectory() as td:
        try:
            m = prepare.build(a.file, Path(td) / "index.html", Path(td) / "build.json", Path(td) / "video.mp4")
            print("✔ Contrato de deploy OK → HTML publicado %.2f MB%s" % (
                m["output_mb"], ", vídeo %.2f MB" % m["video_mb"] if m["video_mb"] else ""))
        except prepare.ContractError as e:
            errors.append("Contrato de deploy: %s" % e)
    try:
        b = i18n_blocks(h)
        keys = {lang: i18n_keys(h, b[lang]) for lang in LANGS}
        allk = set().union(*keys.values())
        for lang in LANGS:
            miss = allk - keys[lang]
            if miss:
                errors.append("Claves ausentes en T.%s: %s" % (lang, ", ".join(sorted(miss))))
        used = set(re.findall(r'data-i18n(?:-[\w-]+)?="([^"]+)"', h))
        missing = sorted(k for k in used if k not in keys["es"] and "$" not in k)
        if missing:
            warnings.append("data-i18n sin clave en T: %s" % ", ".join(missing[:20]))
    except SystemExit as e:
        errors.append(str(e))
    counts = {lang: h.count('class="bb-%s"' % lang) for lang in LANGS}
    if len(set(counts.values())) != 1:
        errors.append("Pares trilingües descuadrados: %s" % ", ".join("%d bb-%s" % (counts[l], l) for l in LANGS))
    body = re.sub(r"<(script|style)\b[\s\S]*?</\1>", lambda m: "\n" * m.group(0).count("\n"), h)
    p = _Balance()
    p.feed(body)
    if p.problems:
        warnings.append("Etiquetas descuadradas (%d): %s" % (len(p.problems), "; ".join(p.problems[:5])))
    for w in warnings:
        print("⚠ " + w)
    for e in errors:
        print("✖ " + e)
    if errors:
        sys.exit(1)
    print("✔ check OK" + (" (con avisos)" if warnings else ""))


def cmd_bump(a, h):
    src = Path(a.file)
    m = re.search(r"_v(\d+)", src.stem)
    if not m:
        raise SystemExit("El nombre %s no tiene _vNN; renómbralo a mano." % src.name)
    ver = "_v%0*d" % (len(m.group(1)), int(m.group(1)) + 1)
    stem = src.stem[: m.start()] + ver
    if a.label is not None:
        stem += ("_" + a.label) if a.label else ""
    else:
        stem += src.stem[m.end():]
    dst = src.with_name(stem + src.suffix)
    if dst.exists():
        raise SystemExit("%s ya existe" % dst.name)
    tracked = subprocess.run(["git", "ls-files", "--error-unmatch", str(src)], cwd=src.parent,
                             capture_output=True).returncode == 0
    if tracked:
        subprocess.run(["git", "mv", str(src), str(dst)], cwd=src.parent, check=True)
    else:
        src.rename(dst)
    print("✔ %s → %s" % (src.name, dst.name))


def main(argv=None):
    ap = argparse.ArgumentParser(description="Inspecciona y edita el HTML de BimboBricks IQ.")
    ap.add_argument("--file", help="HTML a usar (por defecto, el único de html/)")
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("outline")
    p = sp.add_parser("find")
    p.add_argument("pattern")
    p.add_argument("-C", "--context", type=int, default=160)
    p.add_argument("--regex", action="store_true")
    p.add_argument("-i", "--ignore-case", action="store_true")
    p.add_argument("--limit", type=int, default=20)
    p = sp.add_parser("show")
    p.add_argument("id")
    p.add_argument("--max", type=int, default=6000)
    p = sp.add_parser("replace")
    p.add_argument("--old")
    p.add_argument("--new")
    p.add_argument("--old-file")
    p.add_argument("--new-file")
    p.add_argument("--count", type=int, default=1)
    p.add_argument("--dry-run", action="store_true")
    p = sp.add_parser("i18n")
    p.add_argument("key")
    p.add_argument("--es")
    p.add_argument("--en")
    p.add_argument("--pt")
    p.add_argument("--create", action="store_true")
    sp.add_parser("blobs")
    p = sp.add_parser("set-blob")
    p.add_argument("index", type=int)
    p.add_argument("image")
    p = sp.add_parser("set-video")
    p.add_argument("video")
    sp.add_parser("check")
    p = sp.add_parser("bump")
    p.add_argument("--label", help="sufijo tras _vNN (por defecto conserva el actual; '' lo quita)")
    a = ap.parse_args(argv)
    try:
        a.file = str(Path(a.file) if a.file else prepare.find_source())
    except prepare.ContractError as e:
        raise SystemExit(str(e))
    h = load(a.file)
    {"outline": cmd_outline, "find": cmd_find, "show": cmd_show, "replace": cmd_replace, "i18n": cmd_i18n,
     "blobs": cmd_blobs, "set-blob": cmd_set_blob, "set-video": cmd_set_video, "check": cmd_check,
     "bump": cmd_bump}[a.cmd](a, h)


if __name__ == "__main__":
    main()
