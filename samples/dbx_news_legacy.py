"""Inserta/actualiza el bloque 'Databricks al día' en la sección Noticias/Newsletter.
Uso: python3 dbx_news.py items.json entrada.html salida.html
items.json: {"updated_es": "...", "updated_en": "...", "items": [{"date_es","date_en","tag_es","tag_en","title_es","title_en","sum_es","sum_en","url","source"}]}
Idempotente: si el bloque ya existe, lo reemplaza.
"""
import json, re, sys, html as H
items_path, src, dst = sys.argv[1:4]
data = json.load(open(items_path, encoding='utf-8'))
h = open(src, encoding='utf-8').read()
e = H.escape

def card(it):
    return (f'<a class="bb-dn" href="{e(it["url"])}" target="_blank" rel="noopener noreferrer">'
            f'<span class="bb-dn-tag"><span class="bb-es">{e(it["tag_es"])} · {e(it["date_es"])}</span><span class="bb-en">{e(it["tag_en"])} · {e(it["date_en"])}</span></span>'
            f'<strong><span class="bb-es">{e(it["title_es"])}</span><span class="bb-en">{e(it["title_en"])}</span></strong>'
            f'<p><span class="bb-es">{e(it["sum_es"])}</span><span class="bb-en">{e(it["sum_en"])}</span></p>'
            f'<span class="bb-dn-src"><span class="bb-es">Fuente: {e(it["source"])} · Leer →</span><span class="bb-en">Source: {e(it["source"])} · Read →</span></span></a>')

block = ('<section id="bb-dbx-news" aria-labelledby="bb-dn-h">'
         '<h3 id="bb-dn-h"><span class="bb-es">⚡ Databricks al día</span><span class="bb-en">⚡ Databricks today</span></h3>'
         f'<p class="bb-dn-sub"><span class="bb-es">Lo último de Databricks que importa para tus datos. {e(data["updated_es"])}</span>'
         f'<span class="bb-en">The latest from Databricks that matters for your data. {e(data["updated_en"])}</span></p>'
         '<div class="bb-dn-grid">' + ''.join(card(i) for i in data['items']) + '</div></section>')

if 'id="bb-dbx-news"' in h:
    h = re.sub(r'<section id="bb-dbx-news"[\s\S]*?</section>', lambda m: block, h, count=1)
else:
    i = h.index('<form class="bb-nl" id="bbNl"')
    h = h[:i] + block + '\n    ' + h[i:]
    css = '''
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
'''
    j = h.index('</style>', h.index('id="bb-theme">'))
    h = h[:j] + css + h[j:]

open(dst, 'w', encoding='utf-8').write(h)
print('ok', len(data['items']), 'items', round(len(h) / 1e6, 2), 'MB')
