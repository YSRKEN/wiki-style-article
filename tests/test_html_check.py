from pathlib import Path

import pytest

from wikiskill.html import write_html
from wikiskill.html_check import HtmlFinding, check_html
from wikiskill.reader import read_article, read_article_file
from wikiskill.types import load_default_registry

REGISTRY = load_default_registry()
FIXTURES = Path(__file__).parent / "fixtures"
UPDATED = "2026年11月2日 (月) 12:00 (JST)"


def _sample() -> str:
    article = read_article_file(FIXTURES / "sample_article.md")
    return write_html(article, REGISTRY[article.settings.type_id], updated=UPDATED)


def _rules(html: str) -> list[str]:
    return [f.rule for f in check_html(html)]


def _page(body: str) -> str:
    """検査の試験用の小さなページ。"""
    head = "<head><title>t</title></head>"
    return f'<!DOCTYPE html>\n<html lang="ja">{head}<body>{body}</body></html>\n'


# --- 書き出した HTML は通る -----------------------------------------------------


def test_見本の書き出しは全部通る() -> None:
    assert check_html(_sample()) == ()


def test_注釈と再利用と注釈の中の出典がある書き出しも通る() -> None:
    source = (
        '+++\ntitle = "試験"\ntype = "concept"\n'
        '[refs.w]\nkind = "web"\ntitle = "題"\nurl = "https://e.com/"\n'
        '[refs.x]\nkind = "book"\ntitle = "書"\n'
        '[notes.a]\ntext = "注釈[^x]"\n'
        "+++\n導入[^n:a][^w]。\n\n## 節\n\n本文[^w][^n:a][^x]。\n\n"
        "### 小節\n\n#### 孫\n\n末。[^w]\n"
    )
    article = read_article(source)

    assert check_html(write_html(article, REGISTRY["concept"], updated=UPDATED)) == ()


def test_結果は規則のidと文面() -> None:
    findings = check_html(_page("{{LEAD}}"))

    assert findings
    assert isinstance(findings[0], HtmlFinding)
    assert findings[0].rule == "HTML-PLACEHOLDER"
    assert "LEAD" in findings[0].message


# --- 差し込み口 -----------------------------------------------------------------


def test_差し込み口が残っていれば見つける() -> None:
    html = _sample().replace("<title>", "<title>{{PAGE_TITLE}}", 1)

    findings = check_html(html)

    assert [f.rule for f in findings] == ["HTML-PLACEHOLDER"]
    assert "{{PAGE_TITLE}}" in findings[0].message


def test_本文に書かれた波括弧は差し込み口と間違えない() -> None:
    source = '+++\ntitle = "試験"\ntype = "concept"\n+++\n{{LEAD}} と書く例。\n'
    article = read_article(source)

    assert check_html(write_html(article, REGISTRY["concept"], updated=UPDATED)) == ()


# --- タグの開き閉じ -------------------------------------------------------------


def test_閉じ忘れを見つける() -> None:
    html = _sample().replace("</main>", "", 1)

    findings = [f for f in check_html(html) if f.rule == "HTML-TAG"]

    assert findings
    assert any("main" in f.message for f in findings)


def test_余分な閉じタグを見つける() -> None:
    html = _sample().replace("</main>", "</main></div>", 1)

    assert "HTML-TAG" in _rules(html)


def test_入れ子の食い違いを見つける() -> None:
    assert "HTML-TAG" in _rules(_page("<p><b>甲</p></b>"))


def test_空要素は閉じなくてよい() -> None:
    assert _rules(_page('<p>甲<br>乙<br />丙<meta charset="utf-8"></p>')) == []


def test_scriptの中の山括弧はタグと見なさない() -> None:
    assert _rules(_page("<script>if (1 < 2) { x = '<b>'; }</script><p>甲</p>")) == []


# --- リンク先 -------------------------------------------------------------------


def test_目次のリンク先がなければ見つける() -> None:
    html = _sample().replace('<h2 id="section-1">', '<h2 id="x-1">', 1)

    findings = [f for f in check_html(html) if f.rule == "HTML-ANCHOR-MISSING"]

    assert findings
    assert "#section-1" in findings[0].message


def test_リンク先の指定が空の井桁は見逃す() -> None:
    assert _rules(_page('<a href="#">甲</a>')) == []


def test_リンク先はパーセントエンコードを戻して照らす() -> None:
    assert _rules(_page('<a href="#%E7%94%B2">甲</a><h2 id="甲">甲</h2>')) == []


def test_idの重なりを見つける() -> None:
    assert _rules(_page('<p id="a">甲</p><p id="a">乙</p>')) == ["HTML-ID-DUPLICATE"]


# --- 脚注 -----------------------------------------------------------------------


def test_無い脚注への参照を見つける() -> None:
    html = _sample().replace('<li id="cite_note-1">', '<li id="cite_note-9">', 1)

    rules = _rules(html)

    assert "HTML-FOOTNOTE-MISSING" in rules
    assert "HTML-FOOTNOTE-UNREFERENCED" in rules


def test_参照されない脚注を見つける() -> None:
    html = _page('<ol class="references"><li id="cite_note-1">甲</li></ol>')

    findings = check_html(html)

    assert [f.rule for f in findings] == ["HTML-FOOTNOTE-UNREFERENCED"]
    assert "cite_note-1" in findings[0].message


def test_プレーンな文字のままの脚注番号を見つける() -> None:
    html = _sample().replace(
        '<sup id="cite_ref-1-1" class="reference"><a href="#cite_note-1">[1]</a></sup>',
        "[1]",
        1,
    )

    rules = _rules(html)

    assert "HTML-FOOTNOTE-PLAIN" in rules


def test_プレーンな注釈番号も見つける() -> None:
    assert _rules(_page("<p>本文[注 2]。</p>")) == ["HTML-FOOTNOTE-PLAIN"]


def test_リンクの中の番号はプレーンな文字と見なさない() -> None:
    html = _page(
        '<sup><a href="#cite_note-1">[1]</a></sup>'
        '<ol class="references"><li id="cite_note-1"><a href="#top">↑</a> 甲</li></ol>'
        '<div id="top"></div>'
    )

    assert _rules(html) == []


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ('href="#cite_note-1">[1]</a>', 'href="#cite_note-1">[7]</a>'),
        ('href="#cite_note-note-1">[注 1]</a>', 'href="#cite_note-note-1">[注 3]</a>'),
    ],
)
def test_番号とリンク先の数字の食い違いを見つける(old: str, new: str) -> None:
    html = _sample()
    assert old in html

    assert "HTML-FOOTNOTE-NUMBER" in _rules(html.replace(old, new, 1))


def test_一覧の並びと脚注のidの数字の食い違いを見つける() -> None:
    html = _page(
        '<sup><a href="#cite_note-2">[2]</a></sup>'
        '<ol class="references"><li id="cite_note-2">甲</li></ol>'
    )

    assert "HTML-FOOTNOTE-NUMBER" in _rules(html)


# --- 外部の資源 -----------------------------------------------------------------


@pytest.mark.parametrize(
    "tag",
    [
        '<link rel="stylesheet" href="https://e.com/a.css">',
        '<script src="https://e.com/a.js"></script>',
        '<img src="https://e.com/a.png">',
        "<style>@import url(https://e.com/a.css);</style>",
        "<style>p{background:url(//e.com/a.png)}</style>",
    ],
)
def test_外部の資源を読む部品を見つける(tag: str) -> None:
    assert "HTML-EXTERNAL-RESOURCE" in _rules(_page(tag))


def test_データuriの画像は外部の資源ではない() -> None:
    html = _page('<style>p{background:url("data:image/svg+xml,%3Csvg%3E")}</style><p>甲</p>')

    assert _rules(html) == []


@pytest.mark.parametrize("type_id", [t.id for t in REGISTRY])
def test_すべての類型で書き出しは検査を通る(type_id: str) -> None:
    fields = "".join(f'"{f.label}" = "値"\n' for f in REGISTRY[type_id].fields)
    infobox = f"[infobox]\n{fields}" if fields else ""
    source = f'+++\ntitle = "試験"\ntype = "{type_id}"\n{infobox}+++\n導入。\n\n## 節\n\n本文。\n'
    article = read_article(source)

    html = write_html(article, REGISTRY[type_id], updated=UPDATED)

    assert check_html(html) == ()
    assert ('class="infobox"' in html) == bool(fields)
