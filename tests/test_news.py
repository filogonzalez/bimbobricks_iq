import json
import shutil

import pytest

import publish_news
from conftest import ROOT

SAMPLE = ROOT / "samples" / "items.example.json"


def test_publish_from_inbox(tmp_path):
    inbox, media = tmp_path / "inbox", tmp_path / "media"
    inbox.mkdir()
    shutil.copy(SAMPLE, inbox / "items.json")
    data = publish_news.publish(inbox, media)
    block = (media / "news" / "news_block.html").read_text(encoding="utf-8")
    assert block.startswith('<section id="bb-dbx-news"') and block.endswith("</section>")
    assert block.count('class="bb-dn"') == len(data["items"])
    assert not list(inbox.iterdir())
    assert len(list((media / "news" / "archive").iterdir())) == 1


def test_escapes_html(tmp_path):
    data = json.loads(SAMPLE.read_text(encoding="utf-8"))
    data["items"][0]["title_es"] = "<script>alert(1)</script>"
    (tmp_path / "in").mkdir()
    (tmp_path / "in" / "x.json").write_text(json.dumps(data), encoding="utf-8")
    publish_news.publish(tmp_path / "in", tmp_path / "media")
    block = (tmp_path / "media" / "news" / "news_block.html").read_text(encoding="utf-8")
    assert "<script>" not in block and "&lt;script&gt;" in block


@pytest.mark.parametrize("payload", ['{"items": []}', "not json", '{"updated_es":"a","updated_en":"b","items":[{"url":"http://x"}]}'])
def test_rejects_invalid(tmp_path, payload):
    (tmp_path / "in").mkdir()
    (tmp_path / "in" / "bad.json").write_text(payload, encoding="utf-8")
    with pytest.raises(SystemExit, match="rechazado"):
        publish_news.publish(tmp_path / "in", tmp_path / "media")
    rej = list((tmp_path / "media" / "news" / "rejected").iterdir())
    assert len(rej) == 2  # copia + .error.txt
    assert not (tmp_path / "media" / "news" / "news_block.html").exists()


def test_empty_inbox(tmp_path):
    (tmp_path / "in").mkdir()
    assert publish_news.publish(tmp_path / "in", tmp_path / "media") is None
