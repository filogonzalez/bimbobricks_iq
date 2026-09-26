import base64

import pytest

import prepare
from conftest import ROOT

MP4 = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 64

MINI = """<html><head><style id="bb-theme">body{}</style></head><body>
<form class="reg card" id="regForm"></form>
<section id="bb-dbx-news"><h3>viejo</h3></section>
<form class="bb-nl" id="bbNl" novalidate></form>
<script type="application/octet-stream" id="bbVideoData">
%s
</script>
<script>const CONFIG = { videoMain: (window.__bbVideoUrl || ""), registrationEndpoint: "", x: 1 };</script>
<script>(function(){ var NL_ENDPOINT=""; })();</script>
</body></html>""" % base64.b64encode(MP4).decode()


def run(tmp_path, html):
    src = tmp_path / "in.html"
    src.write_text(html, encoding="utf-8")
    out = tmp_path / "out" / "index.html"
    m = prepare.build(src, out, tmp_path / "out" / "build.json", tmp_path / "build" / "video.mp4")
    return out.read_text(encoding="utf-8"), m


def test_mini_contract(tmp_path):
    h, m = run(tmp_path, MINI)
    assert 'registrationEndpoint: "/api/register"' in h
    assert 'NL_ENDPOINT="/api/newsletter"' in h
    assert "bbVideoData" not in h and '__bbVideoUrl="/media/video.mp4?v=' in h
    assert h.count(prepare.NEWS_START) == 1 and "<h3>viejo</h3>" in h
    assert "#bb-dbx-news{" in h  # CSS añadido porque el HTML no lo tenía
    assert (tmp_path / "build" / "video.mp4").read_bytes() == MP4
    assert m["video_mb"] is not None


def test_is_idempotent_on_already_wired_endpoints(tmp_path):
    h, _ = run(tmp_path, MINI.replace('registrationEndpoint: ""', 'registrationEndpoint: "https://old"'))
    assert 'registrationEndpoint: "/api/register"' in h


@pytest.mark.parametrize("broken,msg", [
    (lambda h: h.replace('registrationEndpoint: "",', ""), "registrationEndpoint"),
    (lambda h: h.replace('var NL_ENDPOINT="";', ""), "NL_ENDPOINT"),
    (lambda h: h.replace('id="regForm"', 'id="otro"'), "regForm"),
    (lambda h: h.replace(base64.b64encode(MP4).decode(), "no-es-base64!"), "base64"),
])
def test_contract_errors(tmp_path, broken, msg):
    with pytest.raises(prepare.ContractError, match=msg):
        run(tmp_path, broken(MINI))


def test_inserts_news_when_missing(tmp_path):
    h, _ = run(tmp_path, MINI.replace('<section id="bb-dbx-news"><h3>viejo</h3></section>', ""))
    i = h.index(prepare.NEWS_START)
    assert i < h.index('<form class="bb-nl" id="bbNl"')
    assert "Muy pronto" in h


def test_find_source_requires_single_html(tmp_path):
    (tmp_path / "a.html").write_text("x")
    (tmp_path / "b.html").write_text("x")
    with pytest.raises(prepare.ContractError, match="exactamente UN"):
        prepare.find_source(tmp_path)


def test_real_html(tmp_path):
    files = list((ROOT / "html").glob("*.html"))
    if len(files) != 1:
        pytest.skip("html/ no tiene exactamente un HTML")
    out = tmp_path / "index.html"
    m = prepare.build(files[0], out, tmp_path / "build.json", tmp_path / "video.mp4")
    assert m["output_mb"] < 9.5
    assert (tmp_path / "video.mp4").read_bytes()[4:8] == b"ftyp"
