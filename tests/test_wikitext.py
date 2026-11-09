import re
from pathlib import Path
from textwrap import dedent

import pytest

from wikiskill import wikitext
from wikiskill.reader import read_article, read_article_file
from wikiskill.types import load_default_registry, parse_registry
from wikiskill.variants import normal_view, rumor_view
from wikiskill.wikitext import (
    NestedNoteError,
    UnknownReferenceError,
    WikitextError,
    WikitextStyle,
    unknown_infobox_labels,
    write_wikitext,
)

REGISTRY = load_default_registry()
CASTLE = parse_registry(
    dedent(
        """\
        [[type]]
        id = "castle"
        name = "城"

        [[type.infobox]]
        template = "Infobox 城"

        [type.infobox.fields]
        "画像" = "img"
        "城主" = "lord"

        [type.infobox.image_fields]
        "画像" = "file"
        """
    )
)
FIXTURES = Path(__file__).parent / "fixtures"
SAMPLE = FIXTURES / "sample_article.md"
SAMPLE_WIKIPEDIA = FIXTURES / "sample_article.wikipedia.wikitext"


def _src(body: str = "", front: str = "", *, type_id: str = "concept") -> str:
    """小さな原稿を組む。``front`` は設定欄の ``title``・``type`` より後ろの TOML。"""
    return f'+++\ntitle = "テスト記事"\ntype = "{type_id}"\n{front}+++\n{body}'


def _render(source: str, style: WikitextStyle = "wikipedia") -> str:
    article = read_article(source)
    return write_wikitext(article, REGISTRY[article.settings.type_id], style=style)


# --- 全体の組み立て -------------------------------------------------------------


def test_既定は本家の形で書き出す() -> None:
    source = _src("本文。\n", '[refs.a]\nkind = "web"\ntitle = "題"\nurl = "https://e.com/"\n')
    article = read_article(source.replace("本文。", "本文[^a]。"))
    concept = REGISTRY["concept"]

    assert write_wikitext(article, concept) == write_wikitext(article, concept, style="wikipedia")
    assert "{{Cite web" in write_wikitext(article, concept)
    assert "{{Cite web" not in write_wikitext(article, concept, style="plain")


def test_書き方は二つだけ() -> None:
    assert wikitext.WIKITEXT_STYLES == ("wikipedia", "plain")


def test_記事の類型と定義が食い違えば例外() -> None:
    article = read_article(_src(type_id="meme"))

    with pytest.raises(WikitextError, match="meme"):
        write_wikitext(article, REGISTRY["concept"])


@pytest.mark.parametrize("style", ["wikipedia", "plain"])
def test_導入部と節と箇条書き(style: WikitextStyle) -> None:
    body = (
        "'''テスト記事'''（てすと）は、[[甲]]と[[乙|おつ]]の例。\n"
        "二文目。\n\n"
        "二段落目。\n\n"
        "## 概要\n\n本文。\n\n"
        "## 親\n\n"
        "### 子\n\n- 一\n- 二\n\n"
        "#### 孫\n\n孫の本文。\n"
    )
    expected = (
        "'''テスト記事'''（てすと）は、[[甲]]と[[乙|おつ]]の例。二文目。\n\n"
        "二段落目。\n\n"
        "== 概要 ==\n本文。\n\n"
        "== 親 ==\n\n"
        "=== 子 ===\n* 一\n* 二\n\n"
        "==== 孫 ====\n孫の本文。\n"
    )

    assert _render(_src(body), style) == expected


@pytest.mark.parametrize("style", ["wikipedia", "plain"])
def test_末尾は関連項目と外部リンクとデフォルトソートとカテゴリの順(style: WikitextStyle) -> None:
    front = (
        'reading = "よみ"\n'
        'defaultsort = "てすと きじ"\n'
        'categories = ["甲の分類", "乙の分類"]\n'
        'related = ["関連甲", "関連乙"]\n'
        '[[external_links]]\ntitle = "公式サイト"\nurl = "https://example.com/"\n'
        '[[external_links]]\ntitle = "別のサイト"\nurl = "https://example.org/a b"\n'
    )
    expected = (
        "本文。\n\n"
        "== 関連項目 ==\n* [[関連甲]]\n* [[関連乙]]\n\n"
        "== 外部リンク ==\n"
        "* [https://example.com/ 公式サイト]\n"
        "* [https://example.org/a%20b 別のサイト]\n\n"
        "{{DEFAULTSORT:てすと きじ}}\n"
        "[[Category:甲の分類]]\n[[Category:乙の分類]]\n"
    )

    assert _render(_src("本文。\n", front), style) == expected


@pytest.mark.parametrize("style", ["wikipedia", "plain"])
def test_空の項目は節も行も書かない(style: WikitextStyle) -> None:
    out = _render(_src("本文。\n"), style)

    assert out == "本文。\n"


@pytest.mark.parametrize("style", ["wikipedia", "plain"])
def test_読み仮名はデフォルトソートに流用しない(style: WikitextStyle) -> None:
    out = _render(_src("本文。\n", 'reading = "ほげ"\ncategories = ["分類"]\n'), style)

    assert "DEFAULTSORT" not in out
    assert out.endswith("[[Category:分類]]\n")


# --- 文中の部品 -----------------------------------------------------------------


@pytest.mark.parametrize("style", ["wikipedia", "plain"])
def test_記事名は自己リンクにせず太字のまま書く(style: WikitextStyle) -> None:
    out = _render(_src("'''テスト記事'''は、題材。\n"), style)

    assert out == "'''テスト記事'''は、題材。\n"
    assert "[[テスト記事" not in out


@pytest.mark.parametrize("style", ["wikipedia", "plain"])
def test_太字の中の内部リンクと脚注の印(style: WikitextStyle) -> None:
    front = '[refs.a]\nkind = "web"\ntitle = "題"\n'
    out = _render(_src("'''[[甲]]と乙[^a]'''は丙。\n", front), style)

    assert out.startswith("'''[[甲]]と乙<ref>")
    assert "</ref>'''は丙。" in out


@pytest.mark.parametrize("style", ["wikipedia", "plain"])
def test_記法に当たる文字は逃がす(style: WikitextStyle) -> None:
    body = (
        "#タグで始まる行。\n\n* 星で始まる行。\n\n= 等号の行 =\n\n"
        "1 < 2 と {{x}} と [https://e.com/ y]。\n\n- #項目\n"
    )
    out = _render(_src(body), style)

    assert out == (
        "<nowiki/>#タグで始まる行。\n\n"
        "<nowiki/>* 星で始まる行。\n\n"
        "<nowiki/>= 等号の行 =\n\n"
        "1 &lt; 2 と &#123;&#123;x&#125;&#125; と &#91;https://e.com/ y]。\n\n"
        "* <nowiki/>#項目\n"
    )


# --- 出典（本家の形） -----------------------------------------------------------


def test_本家の形のweb出典() -> None:
    front = (
        '[refs.w]\nkind = "web"\ntitle = "題"\nurl = "https://e.com/a"\nauthor = "著者"\n'
        'work = "サイト"\npublisher = "発行"\ndate = "2020-04-01"\naccess_date = "2026-11-01"\n'
        'pages = "3"\n'
    )
    out = _render(_src("本文[^w]。\n", front))

    assert out == (
        "本文<ref>{{Cite web |和書 |url=https://e.com/a |title=題 |author=著者 |website=サイト "
        "|publisher=発行 |date=2020-04-01 |page=3 |access-date=2026-11-01}}</ref>。\n\n"
        "== 脚注 ==\n=== 出典 ===\n{{Reflist}}\n"
    )


def test_本家の形のbook出典() -> None:
    front = (
        '[refs.b]\nkind = "book"\ntitle = "書名"\nauthor = "著者"\npublisher = "例文社"\n'
        'date = "2020-09-01"\nisbn = "978-4-00-000000-0"\npages = "3-20"\n'
    )
    out = _render(_src("本文[^b]。\n", front))

    assert (
        "本文<ref>{{Cite book |和書 |title=書名 |author=著者 |publisher=例文社 |date=2020-09-01 "
        "|pages=3-20 |isbn=978-4-00-000000-0}}</ref>。\n"
    ) in out


def test_本家の形のnews出典() -> None:
    front = (
        '[refs.n]\nkind = "news"\ntitle = "見出し"\nwork = "架空新聞"\ndate = "2020-04-01"\n'
        'author = "記者"\n'
    )
    out = _render(_src("本文[^n]。\n", front))

    assert (
        "本文<ref>{{Cite news |和書 |title=見出し |author=記者 |newspaper=架空新聞 "
        "|date=2020-04-01}}</ref>。\n"
    ) in out


@pytest.mark.parametrize(
    ("pages", "param"),
    [("12", "page"), ("3-20", "pages"), ("28,36", "pages"), ("3、5", "pages")],
)
def test_ページは範囲や列記ならpagesを使う(pages: str, param: str) -> None:
    front = f'[refs.b]\nkind = "book"\ntitle = "書名"\npages = "{pages}"\n'
    out = _render(_src("本文[^b]。\n", front))

    assert f" |{param}={pages}}}}}</ref>" in out


def test_出典の備考は出典テンプレートの後ろに添える() -> None:
    front = '[refs.w]\nkind = "web"\ntitle = "題"\nnote = "2020年版による。"\n'
    out = _render(_src("本文[^w]。\n", front))

    assert "<ref>{{Cite web |和書 |title=題}}2020年版による。</ref>" in out


def test_出典の題の縦棒はエンティティにする() -> None:
    front = '[refs.w]\nkind = "web"\ntitle = "甲|乙"\n'
    out = _render(_src("本文[^w]。\n", front))

    assert "|title=甲&#124;乙}}" in out


def test_同じ出典の二回目からは名前だけの脚注にする() -> None:
    front = '[refs.w]\nkind = "web"\ntitle = "題"\n[refs.x]\nkind = "web"\ntitle = "別"\n'
    out = _render(_src("甲[^w]。乙[^w]。丙[^x]。丁[^w][^x]。\n", front))

    assert out.splitlines()[0] == (
        '甲<ref name="w">{{Cite web |和書 |title=題}}</ref>。乙<ref name="w" />。'
        '丙<ref name="x">{{Cite web |和書 |title=別}}</ref>。丁<ref name="w" /><ref name="x" />。'
    )


def test_数字だけのキーはコロンを付けた名前にする() -> None:
    front = '[refs.1]\nkind = "web"\ntitle = "題"\n'
    out = _render(_src("甲[^1]。乙[^1]。\n", front))

    assert out.splitlines()[0] == (
        '甲<ref name=":1">{{Cite web |和書 |title=題}}</ref>。乙<ref name=":1" />。'
    )


def test_名前は一度きりの出典には付けない() -> None:
    front = '[refs.w]\nkind = "web"\ntitle = "題"\n'
    out = _render(_src("甲[^w]。\n", front))

    assert out.splitlines()[0] == "甲<ref>{{Cite web |和書 |title=題}}</ref>。"


# --- 出典（素の記法） -----------------------------------------------------------


def test_素の記法のweb出典は地の文で書く() -> None:
    front = (
        '[refs.w]\nkind = "web"\ntitle = "題"\nurl = "https://e.com/a"\nauthor = "著者"\n'
        'work = "サイト"\npublisher = "発行"\ndate = "2020-04"\naccess_date = "2026-11-01"\n'
    )
    out = _render(_src("本文[^w]。\n", front), "plain")

    assert out == (
        "本文<ref>著者「[https://e.com/a 題]」サイト、発行、2020年4月、2026年11月1日閲覧。"
        "</ref>。\n\n"
        "== 脚注 ==\n=== 出典 ===\n<references />\n"
    )


def test_素の記法のweb出典は項目が少なくても崩れない() -> None:
    front = (
        '[refs.w]\nkind = "web"\ntitle = "題"\nurl = "https://e.com/a"\n'
        '[refs.x]\nkind = "web"\ntitle = "別"\n'
    )
    out = _render(_src("甲[^w]乙[^x]。\n", front), "plain")

    assert out.splitlines()[0] == "甲<ref>「[https://e.com/a 題]」。</ref>乙<ref>「別」。</ref>。"


def test_素の記法のbook出典() -> None:
    front = (
        '[refs.b]\nkind = "book"\ntitle = "書名"\nauthor = "著者"\npublisher = "例文社"\n'
        'date = "2020-09-01"\nisbn = "978-4-00-000000-0"\npages = "3-20"\n'
    )
    out = _render(_src("本文[^b]。\n", front), "plain")

    assert out.splitlines()[0] == (
        "本文<ref>著者『書名』例文社、2020年9月1日、3-20頁、ISBN 978-4-00-000000-0。</ref>。"
    )


def test_素の記法のbook出典のurlは書名に付ける() -> None:
    front = '[refs.b]\nkind = "book"\ntitle = "書名"\nurl = "https://e.com/b"\n'
    out = _render(_src("本文[^b]。\n", front), "plain")

    assert out.splitlines()[0] == "本文<ref>『[https://e.com/b 書名]』。</ref>。"


def test_素の記法のnews出典() -> None:
    front = (
        '[refs.n]\nkind = "news"\ntitle = "見出し"\nwork = "架空新聞"\ndate = "2020-04-01"\n'
        'author = "記者"\npublisher = "発行元"\npages = "5"\n'
    )
    out = _render(_src("本文[^n]。\n", front), "plain")

    assert out.splitlines()[0] == (
        "本文<ref>記者「見出し」『架空新聞』発行元、2020年4月1日、5面。</ref>。"
    )


def test_素の記法では日付が日本語の形でなければそのまま書く() -> None:
    front = '[refs.w]\nkind = "web"\ntitle = "題"\ndate = "2020年春"\naccess_date = "2026"\n'
    out = _render(_src("本文[^w]。\n", front), "plain")

    assert out.splitlines()[0] == "本文<ref>「題」2020年春、2026年閲覧。</ref>。"


def test_素の記法の出典の備考は文末に添える() -> None:
    front = '[refs.w]\nkind = "web"\ntitle = "題"\nnote = "補足。"\n'
    out = _render(_src("本文[^w]。\n", front), "plain")

    assert out.splitlines()[0] == "本文<ref>「題」。補足。</ref>。"


def test_素の記法の出典の記号は逃がす() -> None:
    front = '[refs.w]\nkind = "web"\ntitle = "甲]|乙"\nurl = "https://e.com/a b"\n'
    out = _render(_src("本文[^w]。\n", front), "plain")

    assert out.splitlines()[0] == "本文<ref>「[https://e.com/a%20b 甲&#93;&#124;乙]」。</ref>。"


def test_素の記法の再利用も名前だけの脚注にする() -> None:
    front = '[refs.w]\nkind = "web"\ntitle = "題"\n'
    out = _render(_src("甲[^w]。乙[^w]。\n", front), "plain")

    assert out.splitlines()[0] == '甲<ref name="w">「題」。</ref>。乙<ref name="w" />。'


# --- 注釈 -----------------------------------------------------------------------

_NOTE_FRONT = (
    '[refs.w]\nkind = "web"\ntitle = "題"\n'
    '[notes.a]\ntext = "甲の注釈。"\n'
    '[notes.b]\ntext = "乙の注釈[[リンク]]。"\n'
)


def test_注釈と出典があれば脚注の下に二つの小節を作る() -> None:
    out = _render(_src("甲[^n:a]乙[^w]。\n", _NOTE_FRONT))

    assert out == (
        '甲<ref group="注釈">甲の注釈。</ref>乙<ref>{{Cite web |和書 |title=題}}</ref>。\n\n'
        '== 脚注 ==\n=== 注釈 ===\n{{Reflist|group="注釈"}}\n=== 出典 ===\n{{Reflist}}\n'
    )


def test_素の記法の注釈と出典() -> None:
    out = _render(_src("甲[^n:a]乙[^w]。\n", _NOTE_FRONT), "plain")

    assert out == (
        '甲<ref group="注釈">甲の注釈。</ref>乙<ref>「題」。</ref>。\n\n'
        '== 脚注 ==\n=== 注釈 ===\n<references group="注釈" />\n=== 出典 ===\n<references />\n'
    )


def test_注釈だけなら注釈の小節だけを作る() -> None:
    out = _render(_src("甲[^n:b]。\n", _NOTE_FRONT))

    assert out == (
        '甲<ref group="注釈">乙の注釈[[リンク]]。</ref>。\n\n'
        '== 脚注 ==\n=== 注釈 ===\n{{Reflist|group="注釈"}}\n'
    )


def test_同じ注釈の二回目からは名前だけの脚注にする() -> None:
    out = _render(_src("甲[^n:a]乙[^n:a]。\n", _NOTE_FRONT))

    assert out.splitlines()[0] == (
        '甲<ref group="注釈" name="a">甲の注釈。</ref>乙<ref group="注釈" name="a" />。'
    )


_NESTED_FRONT = (
    '[refs.w]\nkind = "web"\ntitle = "題"\n[notes.a]\ntext = "注釈本文[^w]。"\n'
    '[notes.b]\ntext = "再利用[^w]。"\n'
)


def test_出典を含む注釈は本家の形ではEfnで書く() -> None:
    out = _render(_src("甲[^n:a]乙[^w]丙[^n:b]。\n", _NESTED_FRONT))

    assert out.splitlines()[0] == (
        '甲{{Efn|1=注釈本文<ref name="w">{{Cite web |和書 |title=題}}</ref>。}}'
        '乙<ref name="w" />'
        '丙{{Efn|1=再利用<ref name="w" />。}}。'
    )


def test_出典を含む注釈は素の記法ではtagで入れ子にする() -> None:
    out = _render(_src("甲[^n:a]乙[^w]丙[^n:b]。\n", _NESTED_FRONT), "plain")

    assert out.splitlines()[0] == (
        '甲{{#tag:ref|注釈本文{{#tag:ref|「題」。|name="w"}}。|group="注釈"}}'
        '乙<ref name="w" />'
        '丙{{#tag:ref|再利用{{#tag:ref||name="w"}}。|group="注釈"}}。'
    )


def test_入れ子の注釈の縦棒はエンティティにする() -> None:
    front = '[refs.w]\nkind = "web"\ntitle = "題"\n[notes.a]\ntext = "甲|乙[^w]"\n'
    native = _render(_src("本文[^n:a]。\n", front))
    plain = _render(_src("本文[^n:a]。\n", front), "plain")

    assert "{{Efn|1=甲&#124;乙<ref>" in native
    assert '{{#tag:ref|甲&#124;乙{{#tag:ref|「題」。}}|group="注釈"}}' in plain


@pytest.mark.parametrize("style", ["wikipedia", "plain"])
def test_注釈の中の注釈は例外(style: WikitextStyle) -> None:
    front = '[notes.a]\ntext = "外[^n:b]"\n[notes.b]\ntext = "内"\n'

    with pytest.raises(NestedNoteError, match="a"):
        _render(_src("本文[^n:a]。\n", front), style)


@pytest.mark.parametrize("style", ["wikipedia", "plain"])
def test_設定欄にない出典の印は例外(style: WikitextStyle) -> None:
    with pytest.raises(UnknownReferenceError, match="zzz"):
        _render(_src("本文[^zzz]。\n"), style)


@pytest.mark.parametrize("style", ["wikipedia", "plain"])
def test_設定欄にない注釈の印は例外(style: WikitextStyle) -> None:
    with pytest.raises(UnknownReferenceError, match="zzz"):
        _render(_src("本文[^n:zzz]。\n"), style)


def test_使われない出典は書き出さず脚注の節も作らない() -> None:
    front = '[refs.w]\nkind = "web"\ntitle = "題"\n'

    assert _render(_src("本文。\n", front)) == "本文。\n"


# --- Infobox（本家の形） --------------------------------------------------------


def test_Infoboxは定義の引数名に写し定義の順に並べる() -> None:
    front = '[infobox]\n"職業" = "[[小説家]]"\n"生年月日" = "1950年4月1日"\n"名前" = "山田 太郎"\n'
    out = _render(_src("本文。\n", front, type_id="person-living"))

    assert out == (
        "{{Infobox 人物\n"
        "| 氏名 = 山田 太郎\n"
        "| 生年月日 = 1950年4月1日\n"
        "| 職業 = [[小説家]]\n"
        "}}\n"
        "本文。\n"
    )


def test_空の値の項目は引数に出さない() -> None:
    front = '[infobox]\n"名前" = "山田 太郎"\n"画像" = ""\n'
    out = _render(_src("本文。\n", front, type_id="person-living"))

    assert out == "{{Infobox 人物\n| 氏名 = 山田 太郎\n}}\n本文。\n"


def test_記事名が既定値の項目は書かれていなければ記事名を入れる() -> None:
    front = '[infobox]\n"監督" = "山田 太郎"\n'
    out = _render(_src("本文。\n", front, type_id="film"))

    assert out == "{{Infobox Film\n| 作品名 = テスト記事\n| 監督 = 山田 太郎\n}}\n本文。\n"


def test_記事名が既定値の項目は書かれていればその値を使う() -> None:
    front = '[infobox]\n"作品名" = "別の題"\n'
    out = _render(_src("本文。\n", front, type_id="film"))

    assert out.startswith("{{Infobox Film\n| 作品名 = 別の題\n}}\n")


def test_Infoboxの項目が一つもなければテンプレートを書かない() -> None:
    assert _render(_src("本文。\n", type_id="manga")) == "本文。\n"


def test_複数部品の型は全部品を重ねて書く() -> None:
    front = '[infobox]\n"作者" = "月見里 ほたる"\n"ジャンル" = "グルメ漫画"\n'
    out = _render(_src("本文。\n", front, type_id="manga"))

    assert out == (
        "{{Infobox animanga/Header\n"
        "| タイトル = テスト記事\n"
        "| ジャンル = グルメ漫画\n"
        "}}\n"
        "{{Infobox animanga/Manga\n"
        "| 作者 = 月見里 ほたる\n"
        "}}\n"
        "{{Infobox animanga/Footer}}\n"
        "本文。\n"
    )


def test_導入部に置く型は導入部の最初の段落の前に書く() -> None:
    front = '[infobox]\n"種類" = "法律"\n"効力" = "現行"\n'
    out = _render(_src("'''テスト法'''は、法律。\n\n## 概要\n\n本文。\n", front, type_id="law"))

    assert out == (
        "{{日本の法令\n"
        "| 題名 = テスト記事\n"
        "| 種類 = 法律\n"
        "| 効力 = 現行\n"
        "}}\n"
        "'''テスト法'''は、法律。\n\n"
        "== 概要 ==\n本文。\n"
    )


def test_Infoboxの値の縦棒はリンクとテンプレートの外だけエンティティにする() -> None:
    front = '[infobox]\n"名前" = "甲|乙 [[丙|丁]] {{x|y}}"\n'
    out = _render(_src("本文。\n", front, type_id="person-living"))

    assert "| 氏名 = 甲&#124;乙 [[丙|丁]] {{x|y}}\n" in out


def test_定義にない項目は削らずコメントで残す() -> None:
    front = (
        '[infobox]\n"名前" = "山田 太郎"\n"連載期間" = "2020年4月 - 2023年3月"\n"補足" = "a--b"\n'
    )
    out = _render(_src("本文。\n", front, type_id="person-living"))

    assert out == (
        "{{Infobox 人物\n"
        "| 氏名 = 山田 太郎\n"
        "}}\n"
        "<!-- Infobox に書き出せなかった項目:\n"
        "連載期間 = 2020年4月 - 2023年3月\n"
        "補足 = a- -b\n"
        "-->\n"
        "本文。\n"
    )


def test_Infoboxを持たない型の項目もコメントで残す() -> None:
    front = '[infobox]\n"ジャンル" = "語"\n'
    expected = "<!-- Infobox に書き出せなかった項目:\nジャンル = 語\n-->\n本文。\n"

    assert _render(_src("本文。\n", front)) == expected
    assert _render(_src("本文。\n", front), "plain") == expected


def test_定義にない項目名を調べられる() -> None:
    front = '[infobox]\n"名前" = "山田"\n"連載期間" = "x"\n"趣味" = "y"\n'
    article = read_article(_src("本文。\n", front, type_id="person-living"))

    assert unknown_infobox_labels(article, REGISTRY["person-living"]) == ("連載期間", "趣味")
    assert unknown_infobox_labels(article, REGISTRY["concept"]) == ("名前", "連載期間", "趣味")


def test_Infoboxの画像の項目は書式nameならファイル名だけを書く() -> None:
    front = (
        '[infobox]\n"選挙名" = "2004年アメリカ合衆国大統領選挙"\n'
        '"地図" = "![選挙区の地図](images/map/electoral.png)"\n'
    )
    out = _render(_src("本文。\n", front, type_id="election"))

    assert out == (
        "{{Infobox Election\n"
        "| 選挙名 = 2004年アメリカ合衆国大統領選挙\n"
        "| map_image = electoral.png\n"
        "}}\n"
        "本文。\n"
    )


def test_Infoboxの画像の項目は書式fileならファイルの記法で書く() -> None:
    front = '[infobox]\n"画像" = "![天守](images/shiro.png)"\n'
    article = read_article(_src("本文。\n", front, type_id="castle"))

    out = write_wikitext(article, CASTLE["castle"])

    assert out == "{{Infobox 城\n| img = [[ファイル:shiro.png|thumb|天守]]\n}}\n本文。\n"


def test_書式fileでキャプションが空ならthumbだけ付ける() -> None:
    front = '[infobox]\n"画像" = "![](images/shiro.png)"\n'
    article = read_article(_src("本文。\n", front, type_id="castle"))

    out = write_wikitext(article, CASTLE["castle"])

    assert "| img = [[ファイル:shiro.png|thumb]]\n" in out


def test_画像の項目でも形の違う値は手を加えず書く() -> None:
    front = '[infobox]\n"画像" = "天守の写真"\n'
    article = read_article(_src("本文。\n", front, type_id="castle"))

    out = write_wikitext(article, CASTLE["castle"])

    assert "| img = 天守の写真\n" in out


# --- Infobox（本家のテンプレートをそのまま使う） -------------------------------


def test__template_があれば項目名をそのまま引数名にして書いた順に並べる() -> None:
    front = '[infobox]\n_template = "Infobox 人物"\n"職業" = "[[小説家]]"\n"趣味" = "散歩"\n'
    out = _render(_src("本文。\n", front, type_id="person-living"))

    assert out == "{{Infobox 人物\n| 職業 = [[小説家]]\n| 趣味 = 散歩\n}}\n本文。\n"


def test__template_でも値の画像はファイルの記法にする() -> None:
    front = '[infobox]\n_template = "Infobox 城"\n"img" = "![天守](images/shiro.png)"\n'
    out = _render(_src("本文。\n", front, type_id="castle"))

    assert out == "{{Infobox 城\n| img = [[ファイル:shiro.png|thumb|天守]]\n}}\n本文。\n"


def test__image_fields_に並べた引数はファイル名だけを渡す() -> None:
    front = (
        '[infobox]\n_template = "Infobox 人物"\n_image_fields = ["画像"]\n'
        '"画像" = "![甲野乙女](images/顔.png)"\n'
    )
    out = _render(_src("本文。\n", front, type_id="person-living"))

    assert out == "{{Infobox 人物\n| 画像 = 顔.png\n}}\n本文。\n"


def test__template_そのものは引数にしない() -> None:
    front = '[infobox]\n_template = "Infobox 人物"\n"職業" = "作家"\n'
    out = _render(_src("本文。\n", front, type_id="person-living"))

    assert out == "{{Infobox 人物\n| 職業 = 作家\n}}\n本文。\n"
    assert "_template" not in out


def test__template_のときは定義にない項目名も引数にする() -> None:
    front = '[infobox]\n_template = "Infobox 人物"\n"趣味" = "散歩"\n'
    article = read_article(_src("本文。\n", front, type_id="person-living"))

    assert unknown_infobox_labels(article, REGISTRY["person-living"]) == ()
    assert "| 趣味 = 散歩\n" in write_wikitext(article, REGISTRY["person-living"])


def test__template_があっても素の記法を指定すれば表で書く() -> None:
    front = '[infobox]\n_template = "Infobox 人物"\n"職業" = "作家"\n'
    out = _render(_src("本文。\n", front, type_id="person-living"), "plain")

    assert out.startswith('{| class="infobox"')


# --- Infobox（素の記法） --------------------------------------------------------


def test_素の記法のInfoboxは表で日本語の項目名のまま書く() -> None:
    front = '[infobox]\n"職業" = "[[小説家]]"\n"名前" = "山田 太郎"\n"趣味" = "散歩"\n'
    out = _render(_src("本文。\n", front, type_id="person-living"), "plain")

    assert out == (
        '{| class="infobox" cellpadding="4" style="float: right; clear: right; width: 22em; '
        "margin: 0 0 1em 1em; border: 1px solid #a2a9b1; border-collapse: collapse; "
        'background-color: #f8f9fa; font-size: 90%;"\n'
        '|-\n! colspan="2" style="background-color: #ccf; text-align: center;" | テスト記事\n'
        '|-\n! scope="row" style="text-align: left; vertical-align: top;" | 職業\n| [[小説家]]\n'
        '|-\n! scope="row" style="text-align: left; vertical-align: top;" | 名前\n| 山田 太郎\n'
        '|-\n! scope="row" style="text-align: left; vertical-align: top;" | 趣味\n| 散歩\n'
        "|}\n"
        "本文。\n"
    )


def test_素の記法でも画像の項目は定義の書式で書く() -> None:
    front = (
        '[infobox]\n"選挙名" = "2004年アメリカ合衆国大統領選挙"\n'
        '"地図" = "![選挙区の地図](images/electoral.png)"\n'
    )
    out = _render(_src("本文。\n", front, type_id="election"), "plain")

    assert "| 地図\n| electoral.png\n" in out


def test_素の記法のInfoboxは複数部品の型でも一つの表にする() -> None:
    front = '[infobox]\n"作者" = "月見里"\n"ジャンル" = "グルメ"\n'
    out = _render(_src("本文。\n", front, type_id="manga"), "plain")

    assert out.count("{|") == 1
    assert out.index("| 月見里") < out.index("| グルメ")
    assert "{{" not in out


def test_素の記法のInfoboxの値の縦棒は逃がす() -> None:
    front = '[infobox]\n"名前" = "甲|乙 || 丙 [[丁|戊]]"\n'
    out = _render(_src("本文。\n", front, type_id="person-living"), "plain")

    assert "| 甲&#124;乙 &#124;&#124; 丙 [[丁|戊]]\n" in out


def test_素の記法のInfoboxは項目がなければ書かない() -> None:
    assert _render(_src("本文。\n", type_id="manga"), "plain") == "本文。\n"


# --- 見本の原稿 -----------------------------------------------------------------


def test_見本の原稿を本家の形で書き出す() -> None:
    article = read_article_file(SAMPLE)

    expected = SAMPLE_WIKIPEDIA.read_text(encoding="utf-8")

    assert write_wikitext(article, REGISTRY["manga"]) == expected


def test_見本の原稿を素の記法で書き出すとテンプレートを使わない() -> None:
    article = read_article_file(SAMPLE)
    out = write_wikitext(article, REGISTRY["manga"], style="plain")

    assert out.startswith('{| class="infobox"')
    assert '<references group="注釈" />' in out
    assert "<references />" in out
    # 使うのは DEFAULTSORT（マジックワード）と、入れ子の出典のための #tag（本体の関数）だけ。
    assert re.findall(r"\{\{(#?\w+)", out) == ["#tag", "#tag", "DEFAULTSORT"]


# --- 印と警告の枠 -----------------------------------------------------------------

_MARK_DATE = "2026年11月"


def _render_marked(
    source: str, style: WikitextStyle = "wikipedia", mark_date: str | None = _MARK_DATE
) -> str:
    article = read_article(source)
    return write_wikitext(
        article, REGISTRY[article.settings.type_id], style=style, mark_date=mark_date
    )


def _body_line(out: str) -> str:
    """冒頭の枠の行を除いた、本文の最初の行。"""
    return out.splitlines()[1]


@pytest.mark.parametrize("kind", ["要出典", "信頼性要検証"])
def test_本家の形の点の印は日付つきのテンプレート(kind: str) -> None:
    out = _render_marked(_src(f"甲[!{kind}]。\n"))

    assert _body_line(out) == f"甲{{{{{kind}|date=2026年11月}}}}。"


def test_本家の形の点の印は日付が無ければ引数を付けない() -> None:
    out = _render_marked(_src("甲[!要出典]。\n"), mark_date=None)

    assert _body_line(out) == "甲{{要出典}}。"


@pytest.mark.parametrize("kind", ["要出典範囲", "独自研究範囲"])
def test_本家の形の範囲の印は1イコールで範囲の文を渡す(kind: str) -> None:
    out = _render_marked(_src(f"前。[!{kind}|a=b|c]。\n"))

    assert _body_line(out) == f"前。{{{{{kind}|1=a=b&#124;c|date=2026年11月}}}}。"


def test_本家の形の範囲の印の中の内部リンクと出典() -> None:
    front = '[refs.w]\nkind = "web"\ntitle = "題"\n'
    out = _render_marked(_src("[!要出典範囲|[[甲|こう]]は乙[^w]]。\n", front), mark_date=None)

    assert _body_line(out) == (
        "{{要出典範囲|1=[[甲|こう]]は乙<ref>{{Cite web |和書 |title=題}}</ref>}}。"
    )


def test_本家の形の注釈と太字の中の印() -> None:
    front = '[notes.a]\ntext = "注[!信頼性要検証]"\n'
    out = _render_marked(_src("'''甲[!要出典]'''[^n:a]。\n", front), mark_date=None)

    assert _body_line(out) == ("'''甲{{要出典}}'''<ref group=\"注釈\">注{{信頼性要検証}}</ref>。")


def test_素の記法の印はテンプレートを使わず文字で書く() -> None:
    body = "甲[!要出典]。乙[!信頼性要検証]。[!要出典範囲|丙]。[!独自研究範囲|丁]。\n"
    out = _render_marked(_src(body), "plain")

    assert _body_line(out) == ("甲[要出典]。乙[信頼性要検証]。丙[要出典]。丁[独自研究?]。")
    assert "{{" not in out


def test_本家の形の枠が一つなら単独のテンプレートを一番上に置く() -> None:
    front = '[infobox]\n"作者" = "甲"\n'
    out = _render_marked(_src("導入部[!要出典]。\n", front, type_id="manga"))

    assert out.splitlines()[0] == "{{出典の明記|date=2026年11月}}"
    assert out.splitlines()[1].startswith("{{Infobox")


def test_本家の形の枠が二つ以上なら複数の問題にまとめる() -> None:
    source = _src("[!独自研究範囲|甲][!要出典]。\n", 'notices = ["観点"]\n')
    out = _render_marked(source)

    assert out.splitlines()[0] == (
        "{{複数の問題|出典の明記=2026年11月|独自研究=2026年11月|観点=2026年11月}}"
    )


def test_本家の形の枠は日付が無ければ引数を付けない() -> None:
    out = _render_marked(_src("甲[!要出典]。\n"), mark_date=None)

    assert out.splitlines()[0] == "{{出典の明記}}"


def test_本家の形の複数の枠は日付が無ければ単独のテンプレートを並べる() -> None:
    # 複数の問題は値の空な引数を出さない（{{#if:}} で見る）ので、日付が無いときは並べる。
    out = _render_marked(_src("[!独自研究範囲|甲][!要出典]。\n"), mark_date=None)

    assert out.splitlines()[:2] == ["{{出典の明記}}", "{{独自研究}}"]


def test_素の記法の枠は斜体の一行() -> None:
    source = _src("[!独自研究範囲|甲][!要出典]。\n", 'notices = ["観点"]\n')
    out = _render_marked(source, "plain")

    assert out.splitlines()[0] == (
        "''この記事には次の問題があります: 出典の明記、独自研究、観点（2026年11月）''"
    )
    assert out.splitlines()[1] == "甲[独自研究?][要出典]。"


def test_素の記法の枠は日付が無ければ日付を書かない() -> None:
    out = _render_marked(_src("甲[!要出典]。\n"), "plain", mark_date=None)

    assert out.splitlines()[0] == "''この記事には次の問題があります: 出典の明記''"


@pytest.mark.parametrize("style", ["wikipedia", "plain"])
def test_印も枠も無ければ枠を書かない(style: WikitextStyle) -> None:
    out = _render_marked(_src("甲。\n"), style)

    assert out == "甲。\n"


# --- 噂のある原稿 -------------------------------------------------------------------

_RUMOR_SOURCE = _src(
    "'''テスト記事'''は架空の概念である[^a]。[!噂|裏の意味があるという[^b][!信頼性要検証]。]"
    "\n\n## 概要\n\n概要。\n\n## 騒動 [!噂]\n\n炎上したという[^b][!信頼性要検証]。\n",
    '[refs.a]\nkind = "web"\ntitle = "確かな出典"\n'
    '[refs.b]\nkind = "web"\ntitle = "噂の出典"\nweak = true\n',
)


def test_噂のある原稿は分けずに渡せない() -> None:
    with pytest.raises(WikitextError, match="normal_view"):
        _render(_RUMOR_SOURCE)


@pytest.mark.parametrize("style", ["wikipedia", "plain"])
def test_通常の版は噂も噂の出典も観点の枠も書かない(style: WikitextStyle) -> None:
    article = read_article(_RUMOR_SOURCE)

    out = write_wikitext(
        normal_view(article), REGISTRY["concept"], style=style, mark_date="2026年11月"
    )

    assert "裏の意味" not in out
    assert "騒動" not in out
    assert "噂の出典" not in out
    assert "観点" not in out
    assert "確かな出典" in out


def test_噂込みの版は噂を中身にほどき観点の枠を貼る() -> None:
    article = read_article(_RUMOR_SOURCE)

    out = write_wikitext(rumor_view(article), REGISTRY["concept"], mark_date="2026年11月")

    assert out.startswith("{{複数の問題|出典の明記=2026年11月|観点=2026年11月}}\n")
    assert "架空の概念である<ref>" in out
    assert '裏の意味があるという<ref name="b">' in out
    assert '== 騒動 ==\n炎上したという<ref name="b" />' in out
    assert "[!噂" not in out
