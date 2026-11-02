import re
from pathlib import Path

import pytest

from wikiskill.html_check import check_html
from wikiskill.html_writer import HtmlError, load_template, write_html, write_html_both
from wikiskill.reader import read_article, read_article_file
from wikiskill.types import load_default_registry

REGISTRY = load_default_registry()
FIXTURES = Path(__file__).parent / "fixtures"
UPDATED = "2026年11月2日 (月) 12:00 (JST)"

_SOURCE = """+++
title = "試験"
type = "concept"
categories = ["架空の概念"]
related = ["別の記事"]

[refs.a]
kind = "web"
title = "確かな出典"
url = "https://example.com/a"
access_date = "2026-11-01"

[refs.b]
kind = "web"
title = "噂の出典"
url = "https://example.com/b"
access_date = "2026-11-01"
weak = true

[notes.x]
text = "噂の注釈[^b][!信頼性要検証]。"

[[external_links]]
title = "公式"
url = "https://example.com/"
+++
'''試験'''は[!噂|裏の意味があるという[^b][!信頼性要検証][^n:x]が、]架空の概念である[^a]。

## 概要

試験の概要[^a]。

## 騒動 [!噂]

炎上したという[^b][!信頼性要検証]。

### 余波

余波があった[!要出典]。
"""


def _both(source: str = _SOURCE) -> str:
    article = read_article(source)
    return write_html_both(article, REGISTRY[article.settings.type_id], UPDATED)


def _version(html: str, name: str) -> str:
    """本文の中の、一つの版の中身だけを取り出す。"""
    start = html.index(f'<div class="variant" data-variant="{name}"')
    end = html.index("<!-- /variant -->", start)
    return html[start:end]


def test_二つの版を入れた書き出しは_HTML_の検査を全部通る() -> None:
    assert check_html(_both()) == ()


def test_噂の無い原稿でも検査を通る() -> None:
    article = read_article_file(FIXTURES / "sample_article.md")

    html = write_html_both(article, REGISTRY[article.settings.type_id], UPDATED)

    assert check_html(html) == ()
    # Infobox も版ごとに入る
    assert _version(html, "normal").count('<table class="infobox"') == 1
    assert _version(html, "rumor").count('<table class="infobox"') == 1


def test_噂のある原稿は_write_html_に分けずに渡せない() -> None:
    article = read_article(_SOURCE)

    with pytest.raises(HtmlError, match="write_html_both"):
        write_html(article, REGISTRY["concept"], UPDATED)


def test_類型の食い違いは例外() -> None:
    article = read_article(_SOURCE)

    with pytest.raises(HtmlError, match="type"):
        write_html_both(article, REGISTRY["manga"], UPDATED)


# --- 二つの版 -----------------------------------------------------------------------


def test_通常の版は噂を含まず噂込みの版は噂を含む() -> None:
    html = _both()
    normal = _version(html, "normal")
    rumor = _version(html, "rumor")

    assert "裏の意味" not in normal
    assert "炎上" not in normal
    assert "噂の出典" not in normal
    assert "架空の概念である" in normal
    assert "裏の意味があるという" in rumor
    assert "炎上したという" in rumor
    assert "噂の出典" in rumor


def test_開いたときは通常の版が見え噂込みの版は隠れる() -> None:
    html = _both()

    assert '<div class="variant" data-variant="normal">' in html
    assert '<div class="variant" data-variant="rumor" hidden>' in html


def test_どちらの版にも本文の部分が全部入る() -> None:
    html = _both()

    for name in ("normal", "rumor"):
        part = _version(html, name)
        assert "catlinks" in part
        assert "関連項目" in part
        assert "外部リンク" in part
        assert 'class="reflist"' in part


def test_観点の枠は噂込みの版にだけ貼る() -> None:
    html = _both()
    pov = "中立的な観点を欠くおそれ"

    assert pov not in _version(html, "normal")
    assert pov in _version(html, "rumor")


def test_脚注の番号は版ごとに振る() -> None:
    html = _both()
    normal = _version(html, "normal")
    rumor = _version(html, "rumor")

    # 通常の版では a が [1]。噂込みの版では先に出る b が [1]、a が [2]。
    assert '<a href="#cite_note-1">[1]</a>' in normal
    assert "cite_note-2" not in normal
    assert "確かな出典" in normal
    assert '<a href="#rumor-cite_note-1">[1]</a>' in rumor
    assert '<a href="#rumor-cite_note-2">[2]</a>' in rumor
    assert '<a href="#rumor-cite_note-note-1">[注 1]</a>' in rumor


def test_噂込みの版の_id_には接頭辞を付ける() -> None:
    html = _both()
    rumor = _version(html, "rumor")
    ids = re.findall(r'id="([^"]+)"', rumor)
    hrefs = re.findall(r'href="#([^"]+)"', rumor)

    assert ids
    assert all(value.startswith("rumor-") for value in ids)
    assert all(value.startswith("rumor-") for value in hrefs)
    assert 'id="rumor-section-2"' in rumor
    assert 'id="rumor-section-2-1"' in rumor
    assert 'id="rumor-cite_ref-1-1"' in rumor


def test_通常の版の_id_は今までと同じ形() -> None:
    normal = _version(_both(), "normal")

    assert 'id="section-1"' in normal
    assert 'id="cite_note-1"' in normal
    assert "rumor-" not in normal


# --- 目次 ---------------------------------------------------------------------------


def test_目次は左の列と浮き窓の両方に二つの版を入れる() -> None:
    html = _both()

    assert html.count('<li data-id="section-1" data-variant="normal">') == 2
    assert html.count('<li data-id="rumor-section-2" data-variant="rumor" hidden>') == 2
    assert html.count('href="#rumor-section-2-1"') == 2
    # 子の項目には版の印を付けない（親の項目ごと隠れる）
    assert '<li data-id="rumor-section-2-1">' in html


def test_通常の版の目次に噂の節は無い() -> None:
    html = _both()
    links = re.findall(
        r'<a href="#([^"]+)"><span class="tocnumber">[^<]*</span>'
        r'<span class="toctext">([^<]+)</span>',
        html,
    )

    # 「騒動」と「余波」は噂込みの版の目次（左の列と浮き窓）にだけある
    assert [target for target, text in links if text in ("騒動", "余波")] == [
        "rumor-section-2",
        "rumor-section-2-1",
        "rumor-section-2",
        "rumor-section-2-1",
    ]
    assert ("section-1", "概要") in links


# --- 切り替えのボタン ---------------------------------------------------------------


def test_記事名のすぐ下に二つのボタンを置き通常の記事が押されている() -> None:
    html = _both()
    heading = html.index('<h1 class="firstHeading"')
    switch = html.index('<div class="variant-switch">')
    toolbar = html.index('<div class="toolbar"')

    assert heading < switch < toolbar
    assert (
        '<button type="button" data-show="normal" aria-pressed="true">通常の記事</button>' in html
    )
    assert (
        '<button type="button" data-show="rumor" aria-pressed="false">噂込みの記事</button>' in html
    )


def test_ボタンの近くに噂込みの版の断り書きを置く() -> None:
    html = _both()
    switch = html[html.index('<div class="variant-switch">') :]

    assert "噂込みの記事には、確かめられていない噂や利用者の見方が含まれます。" in switch[:600]


def test_切り替えはインラインのスクリプトとCSSで書く() -> None:
    html = _both()

    assert "data-show" in html
    assert ".variant-switch" in html
    assert "addEventListener('click'" in html
    assert "<script src" not in html
    assert "onclick" not in html


def test_噂の無い書き出しには切り替えの部品を入れない() -> None:
    article = read_article_file(FIXTURES / "sample_article.md")

    html = write_html(article, REGISTRY[article.settings.type_id], UPDATED)

    assert "variant" not in html
    assert "data-show" not in html


def test_雛形の切り替えの差し込み口は単独の行にある() -> None:
    lines = load_template().split("\n")

    for name in (
        "VARIANT_STYLE",
        "VARIANT_SWITCH",
        "VARIANT_OPEN",
        "VARIANT_CLOSE",
        "RUMOR_VARIANT",
        "VARIANT_SCRIPT",
    ):
        assert any(line.strip() == f"{{{{{name}}}}}" for line in lines), name
