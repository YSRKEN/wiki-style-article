"""補助的なテンプレートの記法（座標・Navbox・スタブ・仮リンク・言語名・節スタブ）の試験。"""

from __future__ import annotations

import pytest

from helpers import Level
from wikiskill import coordinates
from wikiskill.checks import check_article
from wikiskill.errors import MarkupError, SettingsError
from wikiskill.html_inline import interlanguage_link, language_name, section_stub_html
from wikiskill.html_writer import coord_html, write_html
from wikiskill.model import (
    Coordinate,
    InterlanguageLink,
    LanguageName,
    Navbox,
    Paragraph,
    SectionStub,
    Text,
)
from wikiskill.reader import read_article
from wikiskill.types import load_default_registry
from wikiskill.wikitext import WikitextStyle, write_wikitext

REGISTRY = load_default_registry()
UPDATED = "2026年11月2日 (月) 12:00 (JST)"
TOKYO = Coordinate(lat=35.681236, lon=139.767125, type="city")
TOKYO_URL = (
    "https://geohack.toolforge.org/geohack.php"
    "?language=ja&params=35.681236_N_139.767125_E_type:city"
)


def _src(body: str = "本文。", front: str = "", *, type_id: str = "place") -> str:
    """設定欄の title・type より後ろ、+++ より前に front を置く。"""
    return f'+++\ntitle = "テスト記事"\ntype = "{type_id}"\n{front}+++\n{body}\n'


def _html(source: str) -> str:
    article = read_article(source)
    return write_html(article, REGISTRY[article.settings.type_id], UPDATED)


def _wikitext(source: str, style: WikitextStyle = "wikipedia") -> str:
    article = read_article(source)
    return write_wikitext(article, REGISTRY[article.settings.type_id], style=style)


# --- 座標の書き方 ---------------------------------------------------------


@pytest.mark.parametrize(
    ("lat", "lon", "expected"),
    [
        (35.681236, 139.767125, "北緯35度40分52秒 東経139度46分02秒"),
        (-33.8688, -70.6693, "南緯33度52分08秒 西経70度40分09秒"),
        (35.999999999, 139.999999999, "北緯36度0分00秒 東経140度0分00秒"),
        (0.0, 0.0, "北緯0度0分00秒 東経0度0分00秒"),
    ],
)
def test_度分秒は本家の形で書く(lat: float, lon: float, expected: str) -> None:
    assert coordinates.text(Coordinate(lat=lat, lon=lon)) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [(35.0, "35"), (139.767125, "139.767125"), (-0.0, "0")],
)
def test_十進は余分な零を付けない(value: float, expected: str) -> None:
    assert coordinates.decimal(value) == expected


def test_geohack_の_url_は本家の形() -> None:
    assert coordinates.geohack_url(TOKYO) == TOKYO_URL


def test_geohack_は記事名を_pagename_に渡す() -> None:
    assert coordinates.geohack_url(TOKYO, "東京") == (TOKYO_URL + "&pagename=%E6%9D%B1%E4%BA%AC")


def test_geohack_は南半球を_S_と_W_で書く() -> None:
    coord = Coordinate(lat=-33.8688, lon=-70.6693, type="city")
    assert "params=33.8688_S_70.6693_W_type:city" in coordinates.geohack_url(coord)


def test_geohack_は_type_が無ければ省く() -> None:
    coord = Coordinate(lat=35.0, lon=139.0)
    assert coordinates.geohack_url(coord).endswith("params=35_N_139_E")


def test_html_の座標は地図へのリンクにする() -> None:
    url = TOKYO_URL.replace("&", "&amp;")
    assert coord_html(TOKYO) == (
        f'<div class="coordinates">座標: <a href="{url}" class="external">'
        "北緯35度40分52秒 東経139度46分02秒</a></div>"
    )


def test_html_の座標は記事名を_pagename_に渡す() -> None:
    assert "&amp;pagename=%E6%9D%B1%E4%BA%AC" in coord_html(TOKYO, "東京")


# --- 設定欄の読み取り -----------------------------------------------------


def test_座標の既定は_title() -> None:
    article = read_article(_src(front="[coord]\nlat = 35.681236\nlon = 139.767125\n"))
    assert article.settings.coord == Coordinate(lat=35.681236, lon=139.767125)


def test_座標の_type_と_display_を読む() -> None:
    article = read_article(
        _src(front=('[coord]\nlat = 35.0\nlon = 139.0\ntype = "city"\ndisplay = "inline"\n'))
    )
    assert article.settings.coord == Coordinate(lat=35.0, lon=139.0, type="city", display="inline")


@pytest.mark.parametrize(
    ("front", "message"),
    [
        ("[coord]\nlat = 35.0\n", "lon がない"),
        ("[coord]\nlat = 91.0\nlon = 139.0\n", "-90 から 90"),
        ("[coord]\nlat = 35.0\nlon = 139.0\nzoom = 3\n", "未知の項目"),
        ('[coord]\nlat = 35.0\nlon = 139.0\ndisplay = "wide"\n', "display"),
    ],
)
def test_座標の書き方が違えば例外(front: str, message: str) -> None:
    with pytest.raises(SettingsError, match=message):
        read_article(_src(front=front))


def test_navbox_は書いた順に読む() -> None:
    front = (
        '[[navbox]]\ntitle = "日本の都市"\nname = "Cities"\n'
        'items = ["東京", "大阪"]\n\n'
        '[[navbox]]\ntitle = "東京都の区"\nitems = ["千代田区"]\n'
    )
    article = read_article(_src(front=front))
    assert article.settings.navboxes == (
        Navbox(title="日本の都市", name="Cities", items=("東京", "大阪")),
        Navbox(title="東京都の区", items=("千代田区",)),
    )


@pytest.mark.parametrize(
    ("front", "message"),
    [
        ('[[navbox]]\nitems = ["東京"]\n', "title がない"),
        ('navbox = "x"\n', "の形で書く"),
    ],
)
def test_navbox_の書き方が違えば例外(front: str, message: str) -> None:
    with pytest.raises(SettingsError, match=message):
        read_article(_src(front=front))


def test_記事スタブはテンプレート名のまま読む() -> None:
    article = read_article(_src(front='stub = "Japan-geo-stub"\n'))
    assert article.settings.stub == "Japan-geo-stub"


@pytest.mark.parametrize(
    ("front", "message"),
    [
        ('stub = "  "\n', "stub が空"),
        ('stub = "Bad|Name"\n', "stub に使えない文字"),
    ],
)
def test_記事スタブの書き方が違えば例外(front: str, message: str) -> None:
    with pytest.raises(SettingsError, match=message):
        read_article(_src(front=front))


# --- 本文の印 -------------------------------------------------------------


def test_節スタブは節の部品になる() -> None:
    article = read_article(_src("## 地理\n本文。\n\n[!節スタブ]\n"))
    assert article.sections[0].blocks[-1] == SectionStub()


def test_節スタブを文中に書くと例外() -> None:
    with pytest.raises(MarkupError, match="行に単独で置く"):
        read_article(_src("文中の[!節スタブ]は書けない。\n"))


def _lead_paragraph(source: str) -> Paragraph:
    """最初の段落を取り出す（lead は行の並びなので型を絞る）。"""
    block = read_article(_src(source)).lead[0]
    assert isinstance(block, Paragraph)
    return block


def test_仮リンクを読む() -> None:
    paragraph = _lead_paragraph("東京は[!仮リンク|en|Tokyo|東京]である。\n")
    assert paragraph.content == (
        Text("東京は"),
        InterlanguageLink(lang="en", target="Tokyo", label="東京"),
        Text("である。"),
    )


def test_仮リンクは表示を省くと本家の記事名を使う() -> None:
    paragraph = _lead_paragraph("[!仮リンク|en|Tokyo]という。\n")
    assert paragraph.content[0] == InterlanguageLink(lang="en", target="Tokyo", label="Tokyo")


def test_言語名を読む() -> None:
    paragraph = _lead_paragraph("[!言語|en]で書く。\n")
    assert paragraph.content[0] == LanguageName(lang="en")


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ("[!仮リンク|en]\n", "項目が足りない"),
        ("[!仮リンク|en|Tokyo|Tokyo|ほか]\n", "三つまで"),
        ("[!仮リンク|english|Tokyo]\n", "BCP 47"),
        ("[!仮リンク|en||Tokyo]\n", "本家の記事名が空"),
        ("[!仮リンク|en|Tokyo|]\n", "表示が空"),
        ("[!言語|en|x]\n", "一つまで"),
        ("[!未知|en]\n", "未知の印"),
    ],
)
def test_補助の記法の誤りは例外(body: str, message: str) -> None:
    with pytest.raises(MarkupError, match=message):
        read_article(_src(body))


# --- HTML の部品 ----------------------------------------------------------


def test_html_の仮リンクは赤字の内部リンクと英語の外部リンクにする() -> None:
    link = InterlanguageLink(lang="en", target="Tokyo", label="東京")
    assert interlanguage_link(link) == (
        '<a href="https://ja.wikipedia.org/wiki/%E6%9D%B1%E4%BA%AC"'
        ' title="東京" class="new">東京</a>'
        '<span class="interlanguage-note">（'
        '<a href="https://en.wikipedia.org/wiki/Tokyo" class="external" lang="en">'
        "英語</a>）</span>"
    )


def test_html_の言語名は日本語で書く() -> None:
    assert language_name("en") == "英語"
    assert language_name("zh-Hans") == "中国語"


def test_html_の言語名は知らない札をそのまま出す() -> None:
    assert language_name("xx") == "xx"


def test_html_の節スタブ() -> None:
    assert section_stub_html() == ('<div class="section-stub">この節は書きかけです。</div>')


# --- 最後まで通した形 -----------------------------------------------------

DEMO = _src(
    "東京（とうきょう）は、日本の首都である。"
    "英語では[!仮リンク|en|Tokyo|Tokyo]と呼ばれる。\n\n"
    "## 地理\n関東平野の南部に位置する。\n\n[!節スタブ]\n\n"
    "## 交通\n鉄道網が発達している。\n",
    'categories = ["東京都の地理"]\nstub = "Japan-geo-stub"\n\n'
    '[coord]\nlat = 35.681236\nlon = 139.767125\ntype = "city"\n\n'
    '[[navbox]]\ntitle = "日本の都市"\nname = "Cities"\n'
    'items = ["東京", "大阪"]\n\n'
    '[[navbox]]\ntitle = "東京都の区"\nitems = ["千代田区"]\n',
)


def test_補助の記法は検査の誤りにならない() -> None:
    findings = check_article(read_article(DEMO))
    assert [finding.rule for finding in findings if finding.level is Level.ERROR] == []


def test_html_は補助の部品をこの順に置く() -> None:
    html = _html(DEMO)
    order = [
        'class="coordinates"',
        "<h2",
        'class="section-stub"',
        'class="navbox"',
        'class="stub"',
        'class="catlinks"',
    ]
    positions = [html.index(token) for token in order]
    assert positions == sorted(positions)


def test_html_の座標には記事名を渡す() -> None:
    assert "&amp;pagename=%E3%83%86%E3%82%B9%E3%83%88%E8%A8%98%E4%BA%8B" in _html(DEMO)


def test_html_の仮リンクは赤字のリンクにする() -> None:
    html = _html(DEMO)
    assert (
        '<a href="https://ja.wikipedia.org/wiki/Tokyo" title="Tokyo" class="new">Tokyo</a>'
    ) in html
    assert (
        '<a href="https://en.wikipedia.org/wiki/Tokyo" class="external" lang="en">英語</a>'
    ) in html


def test_wikitext_は座標を先頭に置く() -> None:
    assert _wikitext(DEMO).splitlines()[0] == (
        "{{Coord|35.681236|139.767125|type:city|display=title}}"
    )


def test_wikitext_の節スタブは節の中に置く() -> None:
    text = _wikitext(DEMO)
    assert text.index("== 地理 ==") < text.index("{{節スタブ}}") < text.index("== 交通 ==")


def test_wikitext_の_navbox_とスタブはカテゴリの前に置く() -> None:
    text = _wikitext(DEMO)
    assert "{{Navbox|name=Cities|title=日本の都市|list1=東京|list2=大阪}}" in text
    navbox = text.index("{{Navbox|name=Cities")
    stub = text.index("{{Japan-geo-stub}}")
    category = text.index("[[Category:東京都の地理]]")
    assert navbox < stub < category


def test_wikitext_の仮リンクと言語名() -> None:
    source = _src("英語では[!仮リンク|en|Tokyo|Tokyo]と[!言語|en]で書く。\n")
    text = _wikitext(source)
    assert "{{仮リンク|Tokyo|en|Tokyo}}" in text
    assert "{{ISO639言語名|en}}" in text


def test_plain_の_wikitext_は素の文にする() -> None:
    text = _wikitext(DEMO, "plain")
    assert text.splitlines()[0] == "座標: 北緯35度40分52秒 東経139度46分02秒"
    assert "'''日本の都市'''" in text
    assert "* 東京" in text
    assert "''この節は書きかけです。''" in text
    assert "''この記事は書きかけです。''" in text
    assert "{{" not in text
