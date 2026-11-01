import re
from pathlib import Path

import pytest

from wikiskill.html import (
    HtmlError,
    NestedFootnoteError,
    UnknownFootnoteError,
    load_template,
    write_html,
)
from wikiskill.reader import read_article, read_article_file
from wikiskill.types import load_default_registry

REGISTRY = load_default_registry()
FIXTURES = Path(__file__).parent / "fixtures"
SAMPLE = FIXTURES / "sample_article.md"
SAMPLE_HTML = FIXTURES / "sample_article.html"
UPDATED = "2026年11月2日 (月) 12:00 (JST)"


def _src(body: str = "", front: str = "", *, type_id: str = "concept") -> str:
    """小さな原稿を組む。``front`` は設定欄の ``title``・``type`` より後ろの TOML。"""
    return f'+++\ntitle = "テスト記事"\ntype = "{type_id}"\n{front}+++\n{body}'


def _render(source: str) -> str:
    article = read_article(source)
    return write_html(article, REGISTRY[article.settings.type_id], updated=UPDATED)


def _article_part(html: str) -> str:
    """記事の中身（``class="art"`` の中）だけを取り出す。"""
    start = html.index('<div class="art">')
    end = html.index('<div class="ftc">')
    return html[start:end]


_WEB = '[refs.w]\nkind = "web"\ntitle = "題"\nurl = "https://e.com/a"\n'
_WEB2 = '[refs.x]\nkind = "web"\ntitle = "別"\n'


# --- 全体 -----------------------------------------------------------------------


def test_見本の全文の期待値と一致する() -> None:
    article = read_article_file(SAMPLE)
    out = write_html(article, REGISTRY[article.settings.type_id], updated=UPDATED)

    assert out == SAMPLE_HTML.read_text(encoding="utf-8")


def test_外部の資源を読まない一枚のhtmlで日本語と文字コードを宣言する() -> None:
    out = _render(_src("本文。\n"))

    assert out.startswith("<!DOCTYPE html>")
    assert '<html lang="ja">' in out
    assert '<meta charset="utf-8">' in out
    assert "<link" not in out
    assert "<script src" not in out
    assert "<img" not in out
    assert "@import" not in out


def test_記事の類型と定義が食い違えば例外() -> None:
    article = read_article(_src(type_id="meme"))

    with pytest.raises(HtmlError, match="meme"):
        write_html(article, REGISTRY["concept"], updated=UPDATED)


def test_本物と取り違えない細工を残す() -> None:
    out = _render(_src("本文。\n"))

    assert "出典: フリー百科事典『ウィキペディア（Wikipedia）』風のページ" in out
    assert "WIKIPEDIA風" in out
    assert "Wikipedia そのものではなく" in out
    assert "<title>テスト記事 - Wikipedia風ページ</title>" in out


def test_最終更新の日時は渡した文字列を逃がして入れる() -> None:
    article = read_article(_src("本文。\n"))
    out = write_html(article, REGISTRY["concept"], updated="2026年<11月>")

    assert "最終更新日時は 2026年&lt;11月&gt; です" in out


def test_差し込み口は残らない() -> None:
    out = _render(_src("本文。\n"))

    assert re.search(r"\{\{[A-Z_]+\}\}", out) is None


def test_雛形の差し込み口はすべて知られている() -> None:
    names = set(re.findall(r"\{\{([A-Z_]+)\}\}", load_template()))

    assert names == {
        "PAGE_TITLE",
        "TOC",
        "INFOBOX",
        "LEAD",
        "SECTIONS",
        "FOOTNOTES",
        "RELATED",
        "EXTERNAL_LINKS",
        "CATEGORIES",
        "UPDATED",
    }


def test_押しても動かない部品はリンクにしない() -> None:
    out = _render(_src("本文。\n"))
    hrefs = re.findall(r'href="([^"]*)"', out)

    assert hrefs  # 目次の「ページ先頭」がある
    assert all(h.startswith(("#", "https://")) for h in hrefs)
    assert "onclick" not in out
    assert 'href="#"' not in out


# --- 本文 -----------------------------------------------------------------------


def test_導入部と太字と箇条書き() -> None:
    body = (
        "'''テスト記事'''は、[[甲]]と[[乙|おつ]]の例。\n二文目。\n\n"
        "二段落目。\n\n## 概要\n\n- 一\n- 二\n"
    )
    out = _article_part(_render(_src(body)))

    assert (
        "<p><b>テスト記事</b>は、"
        '<a href="https://ja.wikipedia.org/wiki/%E7%94%B2" title="甲">甲</a>'
        'と<a href="https://ja.wikipedia.org/wiki/%E4%B9%99" title="乙">おつ</a>の例。二文目。</p>'
    ) in out
    assert "<p>二段落目。</p>" in out
    assert "<ul>\n<li>一</li>\n<li>二</li>\n</ul>" in out


def test_内部リンクは本家へ張りスペースは下線にする() -> None:
    out = _article_part(_render(_src("[[A B]]と[[記事#節]]と[[Q&A]]。\n")))

    assert 'href="https://ja.wikipedia.org/wiki/A_B"' in out
    assert 'href="https://ja.wikipedia.org/wiki/%E8%A8%98%E4%BA%8B#%E7%AF%80"' in out
    assert 'href="https://ja.wikipedia.org/wiki/Q%26A"' in out


def test_赤リンクは作らない() -> None:
    out = _render(_src("[[甲]]。\n"))

    assert 'class="new' not in out


def test_記法に当たる文字は逃がす() -> None:
    body = '1 < 2 & 3 > 2 と "引用" と {{x}} と <script>。\n\n## <見出し> & "題"\n\n本文。\n'
    out = _render(_src(body))

    assert (
        "1 &lt; 2 &amp; 3 &gt; 2 と &quot;引用&quot; と "
        "&#123;&#123;x&#125;&#125; と &lt;script&gt;。"
    ) in out
    assert '<h2 id="section-1">&lt;見出し&gt; &amp; &quot;題&quot;</h2>' in out
    assert "<script>" not in _article_part(out)


def test_記事名も逃がしてタイトルと見出しに入れる() -> None:
    article = read_article('+++\ntitle = "A<B>&C"\ntype = "concept"\n+++\n本文。\n')
    out = write_html(article, REGISTRY["concept"], updated=UPDATED)

    assert "<title>A&lt;B&gt;&amp;C - Wikipedia風ページ</title>" in out
    assert '<h1 class="firstHeading" id="firstHeading">A&lt;B&gt;&amp;C</h1>' in out


# --- 見出しと目次 ------------------------------------------------------------------


_TOC_BODY = (
    "導入。\n\n## 概要\n\n本文。\n\n## 親\n\n"
    "### 子\n\n子の本文。\n\n#### 孫\n\n孫の本文。\n\n### 次の子\n\n本文。\n"
)


def test_見出しには安全なidを付ける() -> None:
    out = _article_part(_render(_src(_TOC_BODY)))

    assert '<h2 id="section-1">概要</h2>' in out
    assert '<h2 id="section-2">親</h2>' in out
    assert '<h3 id="section-2-1">子</h3>' in out
    assert '<h4 id="section-2-1-1">孫</h4>' in out
    assert '<h3 id="section-2-2">次の子</h3>' in out


def test_同じ見出しが二つあってもidは重ならない() -> None:
    out = _render(_src("## 同じ\n\n甲。\n\n## 同じ\n\n乙。\n"))
    ids = re.findall(r' id="([^"]+)"', out)

    assert len(ids) == len(set(ids))
    assert '<h2 id="section-1">同じ</h2>' in out
    assert '<h2 id="section-2">同じ</h2>' in out


def test_目次は節の見出しから番号つきで作り左の列と浮き窓の両方に入れる() -> None:
    out = _render(_src(_TOC_BODY))

    assert out.count('<a href="#section-2-1"><span class="tocnumber">2.1</span>') == 2
    assert out.count('<a href="#section-2-1-1"><span class="tocnumber">2.1.1</span>') == 2
    assert out.count('<span class="toctext">孫</span>') == 2
    # 子は親の li の中の入れ子の ul に入る。
    assert re.search(
        r'<li data-id="section-2"><a href="#section-2">.*?</a>\n<ul>\n<li data-id="section-2-1">',
        out,
    )


def test_目次には脚注と関連項目と外部リンクの見出しも入る() -> None:
    front = (
        'related = ["関連"]\n'
        + _WEB
        + '[[external_links]]\ntitle = "公式"\nurl = "https://e.com/"\n'
    )
    out = _render(_src("## 概要\n\n本文[^w]。\n", front))
    toc = out[out.index('data-toc="left"') : out.index('<main class="main">')]
    texts = re.findall(r'<span class="toctext">([^<]*)</span>', toc)

    assert texts == ["概要", "脚注", "出典", "関連項目", "外部リンク"]


# --- Infobox ----------------------------------------------------------------------


def test_Infoboxは類型の定義の順に日本語の項目名のまま並べる() -> None:
    front = '[infobox]\n"出版社" = "架空出版"\n"作者" = "甲"\n"ジャンル" = "グルメ漫画"\n'
    out = _render(_src("本文。\n", front, type_id="manga"))
    labels = re.findall(r'<th scope="row">([^<]*)</th>', out)

    assert labels == ["ジャンル", "作者", "出版社"]
    assert '<table class="infobox">' in out
    assert "<caption>テスト記事</caption>" in out
    assert '<tr><th scope="row">作者</th><td>甲</td></tr>' in out


def test_定義にない項目は定義の項目の後ろに書いた順で並べる() -> None:
    front = '[infobox]\n"連載期間" = "2020年"\n"作者" = "甲"\n"備考X" = "乙"\n"ジャンル" = "丙"\n'
    out = _render(_src("本文。\n", front, type_id="manga"))
    labels = re.findall(r'<th scope="row">([^<]*)</th>', out)

    assert labels == ["ジャンル", "作者", "連載期間", "備考X"]


def test_Infoboxを持たない型には出さない() -> None:
    out = _render(_src("本文。\n", '[infobox]\n"種類" = "値"\n', type_id="concept"))

    assert 'class="infobox"' not in out
    assert "種類" not in out


def test_値のある項目が一つもなければInfoboxを出さない() -> None:
    assert 'class="infobox"' not in _render(_src("本文。\n", type_id="manga"))
    empty = _render(_src("本文。\n", '[infobox]\n"作者" = "  "\n', type_id="manga"))
    assert 'class="infobox"' not in empty


def test_title_fieldの項目は表の見出しにして行にはしない() -> None:
    # 漫画の title_field は「タイトル」。書いていれば表の見出しになり、書かなければ記事名になる。
    front = '[infobox]\n"タイトル" = "別題"\n"作者" = "甲"\n'
    with_title = _render(_src("本文。\n", front, type_id="manga"))
    without = _render(_src("本文。\n", '[infobox]\n"作者" = "甲"\n', type_id="manga"))

    assert "<caption>別題</caption>" in with_title
    assert ">タイトル</th>" not in with_title
    assert "<caption>テスト記事</caption>" in without


def test_Infoboxの値は内部リンクと改行を使えて逃がす() -> None:
    front = '[infobox]\n"作者" = "[[甲|こう]]<br />乙 & <丙>"\n'
    out = _render(_src("本文。\n", front, type_id="manga"))

    assert (
        '<td><a href="https://ja.wikipedia.org/wiki/%E7%94%B2" title="甲">こう</a>'
        "<br>乙 &amp; &lt;丙&gt;</td>"
    ) in out


def test_Infoboxの値の壊れた記法は文字のまま出す() -> None:
    front = '[infobox]\n"作者" = "[[閉じていない"\n'
    out = _render(_src("本文。\n", front, type_id="manga"))

    assert "<td>[[閉じていない</td>" in out


def test_Infoboxは導入部の前に置く() -> None:
    front = '[infobox]\n"作者" = "甲"\n'
    out = _render(_src("導入部。\n", front, type_id="manga"))

    assert out.index('class="infobox"') < out.index("<p>導入部。</p>")


# --- 脚注 -------------------------------------------------------------------------


def test_脚注の印は本文に現れる順に番号を付けリンクにする() -> None:
    out = _render(_src("甲[^x]。乙[^w]。\n", _WEB + _WEB2))

    assert (
        '甲<sup id="cite_ref-1-1" class="reference"><a href="#cite_note-1">[1]</a></sup>。'
        '乙<sup id="cite_ref-2-1" class="reference"><a href="#cite_note-2">[2]</a></sup>。'
    ) in out
    # 一覧も本文の順（設定欄の順ではない）。
    items = re.findall(r'<li id="cite_note-(\d+)">', out)
    assert items == ["1", "2"]
    assert out.index("「別」") < out.index("「<a ")


def test_同じ出典の再利用は同じ番号で戻りリンクが増える() -> None:
    out = _render(_src("甲[^w]。乙[^w]。丙[^x]。丁[^w]。\n", _WEB + _WEB2))

    assert out.count('<a href="#cite_note-1">[1]</a>') == 3
    assert 'id="cite_ref-1-1"' in out
    assert 'id="cite_ref-1-3"' in out
    assert (
        '<li id="cite_note-1"><span class="mw-cite-backlink">↑ '
        '<a href="#cite_ref-1-1">a</a><a href="#cite_ref-1-2">b</a><a href="#cite_ref-1-3">c</a>'
        "</span> "
    ) in out
    # 一度きりの出典は「↑」だけ。
    assert (
        '<li id="cite_note-2"><span class="mw-cite-backlink"><a href="#cite_ref-2-1">↑</a></span> '
    ) in out


def test_脚注欄は出典だけなら出典の小節だけを作る() -> None:
    out = _render(_src("甲[^w]。\n", _WEB))

    assert '<h2 id="section-1">脚注</h2>' in out
    assert '<h3 id="section-1-1">出典</h3>' in out
    assert "注釈</h3>" not in out
    assert '<div class="reflist">\n<ol class="references">' in out


def test_使われない出典は書き出さない() -> None:
    out = _render(_src("甲[^w]。\n", _WEB + _WEB2))

    assert "「別」" not in out
    assert out.count('<li id="cite_note-') == 1


def test_出典がなければ脚注の節を作らない() -> None:
    out = _render(_src("本文。\n"))

    assert "脚注" not in _article_part(out)
    assert "references" not in _article_part(out)


_NOTE = '[notes.a]\ntext = "甲の注釈。"\n[notes.b]\ntext = "乙の注釈[[リンク]]。"\n'


def test_注釈の印は注の形でリンクにし注釈の小節に並べる() -> None:
    out = _render(_src("甲[^n:a]乙[^w]。\n", _NOTE + _WEB))

    assert (
        '<sup id="cite_ref-note-1-1" class="reference"><a href="#cite_note-note-1">[注 1]</a></sup>'
    ) in out
    assert '<h3 id="section-1-1">注釈</h3>' in out
    assert '<h3 id="section-1-2">出典</h3>' in out
    assert (
        '<li id="cite_note-note-1"><span class="mw-cite-backlink">'
        '<a href="#cite_ref-note-1-1">↑</a></span> '
        '<span class="reference-text">甲の注釈。</span></li>'
    ) in out
    # 注釈の番号は出典の番号とは別に数える。
    assert '<a href="#cite_note-1">[1]</a>' in out


def test_注釈だけなら注釈の小節だけを作る() -> None:
    out = _render(_src("甲[^n:b]。\n", _NOTE))

    assert "注釈</h3>" in out
    assert "出典</h3>" not in out


def test_同じ注釈の再利用も戻りリンクにまとめる() -> None:
    out = _render(_src("甲[^n:a]乙[^n:a]。\n", _NOTE))

    assert out.count('<a href="#cite_note-note-1">[注 1]</a>') == 2
    assert '↑ <a href="#cite_ref-note-1-1">a</a><a href="#cite_ref-note-1-2">b</a>' in out


_NESTED = (
    _WEB + _WEB2 + '[notes.a]\ntext = "注釈本文[^x]。"\n[notes.b]\ntext = "再利用[^x]と[^w]。"\n'
)


def test_注釈の中の出典は注釈を最初に使った場所の順に番号を付ける() -> None:
    # 本文では注釈 a（出典 x を含む）→ 出典 w の順。x が 1 番、w が 2 番になる。
    out = _render(_src("甲[^n:a]乙[^w]。\n", _NESTED))

    assert (
        '<span class="reference-text">注釈本文'
        '<sup id="cite_ref-1-1" class="reference"><a href="#cite_note-1">[1]</a></sup>。</span>'
    ) in out
    assert (
        '乙<sup id="cite_ref-2-1" class="reference"><a href="#cite_note-2">[2]</a></sup>'
    ) in _article_part(out)
    # 注釈の中の印にも戻りリンクがある。
    assert (
        '<li id="cite_note-1"><span class="mw-cite-backlink"><a href="#cite_ref-1-1">↑</a>' in out
    )


def test_注釈は一度しか書き出さないので注釈の中の印は一回分だけ数える() -> None:
    out = _render(_src("甲[^n:a]乙[^n:a]。\n", _NESTED))

    assert out.count('id="cite_ref-1-') == 1


def test_出典の書誌は題名のリンクと媒体と日付と閲覧日で書く() -> None:
    front = (
        '[refs.w]\nkind = "web"\ntitle = "題"\nurl = "https://e.com/a"\nauthor = "著者"\n'
        'work = "サイト"\npublisher = "発行"\ndate = "2020-04"\naccess_date = "2026-11-01"\n'
    )
    out = _render(_src("本文[^w]。\n", front))

    assert (
        '<span class="reference-text">著者「<a class="external" rel="nofollow" '
        'href="https://e.com/a">題</a>」サイト、発行、2020年4月、2026年11月1日閲覧。</span>'
    ) in out


def test_書籍と新聞の書誌() -> None:
    front = (
        '[refs.b]\nkind = "book"\ntitle = "書名"\nauthor = "著者"\npublisher = "例文社"\n'
        'date = "2020-09-01"\nisbn = "978-4-00-000000-0"\npages = "3-20"\n'
        '[refs.n]\nkind = "news"\ntitle = "見出し"\nwork = "架空新聞"\ndate = "2020-04-01"\n'
        'author = "記者"\npublisher = "発行元"\npages = "5"\nnote = "補足。"\n'
    )
    out = _render(_src("甲[^b]乙[^n]。\n", front))

    assert "著者『書名』例文社、2020年9月1日、3-20頁、ISBN 978-4-00-000000-0。</span>" in out
    assert "記者「見出し」『架空新聞』発行元、2020年4月1日、5面。補足。</span>" in out


def test_出典のurlがない題名はリンクにしない() -> None:
    out = _render(_src("本文[^x]。\n", _WEB2))

    assert '<span class="reference-text">「別」。</span>' in out


def test_出典のurlがhttpでなければリンクにしない() -> None:
    front = '[refs.w]\nkind = "web"\ntitle = "題"\nurl = "javascript:alert(1)"\n'
    out = _render(_src("本文[^w]。\n", front))

    assert "javascript" not in out
    assert "「題」" in out


def test_出典の記号は逃がす() -> None:
    front = '[refs.w]\nkind = "web"\ntitle = "甲<乙>&丙"\nurl = "https://e.com/a b?x=1&y={2}"\n'
    out = _render(_src("本文[^w]。\n", front))

    assert 'href="https://e.com/a%20b?x=1&amp;y=%7B2%7D">甲&lt;乙&gt;&amp;丙</a>' in out


def test_未定義の出典と注釈は例外() -> None:
    with pytest.raises(UnknownFootnoteError, match="zzz"):
        _render(_src("本文[^zzz]。\n"))
    with pytest.raises(UnknownFootnoteError, match="zzz"):
        _render(_src("本文[^n:zzz]。\n"))


def test_注釈の中の注釈は例外() -> None:
    front = '[notes.a]\ntext = "甲[^n:b]"\n[notes.b]\ntext = "乙"\n'

    with pytest.raises(NestedFootnoteError):
        _render(_src("本文[^n:a]。\n", front))


# --- 末尾 -------------------------------------------------------------------------


def test_末尾は関連項目と外部リンクとカテゴリとフッタ() -> None:
    front = (
        'categories = ["甲の分類", "乙の分類"]\n'
        'related = ["関連甲", "関連乙"]\n'
        '[[external_links]]\ntitle = "公式サイト"\nurl = "https://example.com/"\n'
        '[[external_links]]\ntitle = "別<サイト>"\nurl = "https://example.org/a b"\n'
    )
    out = _article_part(_render(_src("本文。\n", front)))

    assert '<h2 id="section-1">関連項目</h2>' in out
    assert (
        '<li><a href="https://ja.wikipedia.org/wiki/%E9%96%A2%E9%80%A3%E7%94%B2" '
        'title="関連甲">関連甲</a></li>'
    ) in out
    assert '<h2 id="section-2">外部リンク</h2>' in out
    assert (
        '<li><a class="external" rel="nofollow" href="https://example.com/">公式サイト</a></li>'
    ) in out
    assert 'href="https://example.org/a%20b">別&lt;サイト&gt;</a>' in out
    assert '<div class="catlinks">' in out
    assert (
        '<li><a href="https://ja.wikipedia.org/wiki/Category:%E7%94%B2%E3%81%AE%E5%88%86%E9%A1%9E" '
        'title="Category:甲の分類">甲の分類</a></li>'
    ) in out
    assert out.index("関連項目") < out.index("外部リンク") < out.index('class="catlinks"')


def test_値のない末尾の部分は節も欄も作らない() -> None:
    out = _article_part(_render(_src("本文。\n")))

    assert "関連項目" not in out
    assert "外部リンク" not in out
    assert "catlinks" not in out


# --- 雛形 -------------------------------------------------------------------------


def test_雛形に知らない差し込み口があれば例外() -> None:
    article = read_article(_src("本文。\n"))

    with pytest.raises(HtmlError, match="NOPE"):
        write_html(article, REGISTRY["concept"], updated=UPDATED, template="{{NOPE}}")


def test_差し込み口だけの行は値が空なら行ごと消える() -> None:
    article = read_article(_src("本文。\n"))
    template = "<p>{{PAGE_TITLE}}</p>\n{{INFOBOX}}\n  {{LEAD}}\n{{CATEGORIES}}\nおわり\n"

    out = write_html(article, REGISTRY["concept"], updated=UPDATED, template=template)

    assert out == "<p>テスト記事</p>\n<p>本文。</p>\nおわり\n"


def test_値の中の波括弧は差し込み口として置き換わらない() -> None:
    article = read_article(_src("{{LEAD}} と {{PAGE_TITLE}}。\n"))
    template = "{{LEAD}}\n"

    out = write_html(article, REGISTRY["concept"], updated=UPDATED, template=template)

    assert out == "<p>&#123;&#123;LEAD&#125;&#125; と &#123;&#123;PAGE_TITLE&#125;&#125;。</p>\n"
