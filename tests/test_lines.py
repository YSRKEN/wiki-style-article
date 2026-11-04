"""読み取り結果が持つ行番号（原稿ファイル全体での 1 始まり）の試験。

行番号は等しさの比較から外してあるので、既存の比較の試験には影響しない。
"""

from pathlib import Path

from wikiskill.body import parse_body
from wikiskill.model import Bold, BulletList, Figure, InfoboxField, Paragraph, Section, Text
from wikiskill.reader import read_article, read_article_file

SAMPLE = Path(__file__).parent / "fixtures" / "sample_article.md"


def test_行番号は等しさの比較に影響しない() -> None:
    assert Paragraph((Text("a"),), line=3) == Paragraph((Text("a"),), line=9)
    assert Paragraph((Text("a"),)) == Paragraph((Text("a"),), line=9)
    assert InfoboxField("a", "b", line=2) == InfoboxField("a", "b")
    assert Section(2, "概要", (), (), line=5) == Section(2, "概要", (), ())


def test_段落と見出しと箇条書きの行番号() -> None:
    lead, sections = parse_body(
        ["導入の一行目", "導入の二行目", "", "## 概要", "", "本文。", "", "- 甲", "- 乙", "  続き"],
        first_line=10,
    )
    assert isinstance(lead[0], Paragraph)
    assert lead[0].line == 10
    section = sections[0]
    assert section.line == 13
    paragraph, bullets = section.blocks
    assert isinstance(paragraph, Paragraph)
    assert paragraph.line == 15
    assert isinstance(bullets, BulletList)
    assert bullets.line == 17
    assert bullets.item_lines == (17, 18)


def test_子の節にも行番号が付く() -> None:
    _, sections = parse_body(["## 親", "", "### 子", "", "#### 孫"], first_line=1)
    parent = sections[0]
    child = parent.children[0]
    assert (parent.line, child.line, child.children[0].line) == (1, 3, 5)


def test_見本の本文の行番号() -> None:
    article = read_article_file(SAMPLE)

    lead = article.lead[0]
    assert isinstance(lead, Paragraph)
    assert lead.line == 47
    assert isinstance(lead.content[0], Bold)

    overview, stalls, chronology = article.sections
    assert (overview.line, stalls.line, chronology.line) == (51, 58, 75)
    assert overview.blocks[0].line == 53
    figure = overview.blocks[1]
    assert isinstance(figure, Figure)
    assert figure.line == 56
    menu = stalls.children[0].children[0]
    assert menu.line == 65
    assert isinstance(menu.blocks[0], BulletList)
    assert menu.blocks[0].item_lines == (67, 68, 69)
    assert isinstance(chronology.blocks[0], BulletList)
    assert chronology.blocks[0].item_lines == (77, 78)


def test_見本の設定欄の行番号() -> None:
    settings = read_article_file(SAMPLE).settings

    assert [field.line for field in settings.infobox] == [10, 11, 12, 13]
    assert [ref.line for ref in settings.references] == [15, 22, 31]
    assert [note.line for note in settings.notes] == [38, 41]
    assert [link.line for link in settings.external_links] == [43]


def test_出典の項目ごとの行番号() -> None:
    ref = read_article_file(SAMPLE).settings.references[0]

    assert ref.line_of("url") == 18
    assert ref.line_of("access_date") == 20
    assert ref.line_of("title") == 17
    # 書かれていない項目は、表の見出しの行を返す。
    assert ref.line_of("date") == 15


def test_読み取りで行番号が付くのは_read_article_でも同じ() -> None:
    article = read_article('+++\ntitle = "あ"\ntype = "person"\n+++\n本文。\n')
    lead = article.lead[0]
    assert isinstance(lead, Paragraph)
    assert lead.line == 5
