"""Operaciones de escritura de scripts/html_tool.py sobre una copia del HTML real."""
import shutil

import pytest

import html_tool
from conftest import ROOT

MP4 = b"\x00\x00\x00\x18ftypmp42" + b"\x01" * 64
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 300


@pytest.fixture
def html(tmp_path):
    files = list((ROOT / "html").glob("*.html"))
    if len(files) != 1:
        pytest.skip("html/ no tiene exactamente un HTML")
    dst = tmp_path / "bimbobricks-iq_v12_cta-academy.html"
    shutil.copy(files[0], dst)
    return dst


def run(html, *args):
    html_tool.main(["--file", str(html)] + list(args))
    return html.read_text(encoding="utf-8")


def test_replace_unique_and_refuses_ambiguous(html):
    n = html.read_text(encoding="utf-8").count("Hasta el 7 de octubre")
    h = run(html, "replace", "--old", "Hasta el 7 de octubre", "--new", "Hasta el 14 de octubre", "--count", str(n))
    assert "Hasta el 14 de octubre" in h and "Hasta el 7 de octubre" not in h
    with pytest.raises(SystemExit, match="coincidencia"):
        run(html, "replace", "--old", "BimboBricks", "--new", "X")


def test_i18n_double_and_single_quotes(html):
    h = run(html, "i18n", "heroSub", "--es", 'Nuevo "texto"', "--en", "New text")
    assert 'heroSub:"Nuevo \\"texto\\""' in h and 'heroSub:"New text"' in h
    h = run(html, "i18n", "t5", "--es", "Haz tu <span class=\"accent\">test</span> de Juan's", "--en", "Take it")
    assert "t5:'Haz tu <span class=\"accent\">test</span> de Juan\\'s'" in h
    with pytest.raises(SystemExit, match="no existe"):
        run(html, "i18n", "claveNueva", "--es", "a", "--en", "b")
    h = run(html, "i18n", "claveNueva", "--es", "a", "--en", "b", "--create")
    assert 'claveNueva:"a"' in h and 'claveNueva:"b"' in h
    run(html, "check")  # paridad ES/EN intacta


def test_set_blob_and_video(html, tmp_path):
    img, vid = tmp_path / "x.png", tmp_path / "v.mp4"
    img.write_bytes(PNG)
    vid.write_bytes(MP4)
    before = html.stat().st_size
    run(html, "set-blob", "0", str(img))
    h = run(html, "set-video", str(vid))
    assert html.stat().st_size < before
    run(html, "check")
    assert html_tool.VIDEO_RE.search(h).group(2).strip() == html_tool.base64.b64encode(MP4).decode()


def test_bump(html):
    html_tool.main(["--file", str(html), "bump"])
    assert (html.parent / "bimbobricks-iq_v13_cta-academy.html").exists() and not html.exists()
    html_tool.main(["--file", str(html.parent / "bimbobricks-iq_v13_cta-academy.html"), "bump", "--label", "ola2"])
    assert (html.parent / "bimbobricks-iq_v14_ola2.html").exists()
