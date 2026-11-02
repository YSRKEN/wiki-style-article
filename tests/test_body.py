import pytest

from wikiskill.body import parse_body
from wikiskill.errors import MarkupError
from wikiskill.model import (
    Block,
    Bold,
    BulletList,
    InternalLink,
    Paragraph,
    RefMark,
    RumorRange,
    Section,
    Text,
)


def parse(text: str, first_line: int = 1) -> tuple[tuple[Block, ...], tuple[Section, ...]]:
    return parse_body(text.split("\n"), first_line)


def para(text: str) -> Paragraph:
    return Paragraph((Text(text),))


def test_見出しがなければ全部が導入部() -> None:
    lead, sections = parse("一つ目。\n\n二つ目。")
    assert lead == (para("一つ目。"), para("二つ目。"))
    assert sections == ()


def test_空の本文は何もない() -> None:
    assert parse("") == ((), ())
    assert parse("\n\n  \n") == ((), ())


def test_段落の中の改行は空白なしでつなぐ() -> None:
    lead, _ = parse("日本語の\n文が続く。\n  字下げも  \nつなぐ。")
    assert lead == (para("日本語の文が続く。字下げもつなぐ。"),)


def test_段落の中に文中の記法を使える() -> None:
    lead, _ = parse("'''星屑'''は[[漫画]]である[^a]。")
    assert lead == (
        Paragraph(
            (
                Bold((Text("星屑"),)),
                Text("は"),
                InternalLink("漫画", None),
                Text("である"),
                RefMark("a"),
                Text("。"),
            )
        ),
    )


def test_導入部のあとに節が続く() -> None:
    lead, sections = parse("導入。\n\n## 概要\n\n概要の本文。\n\n## 歴史\n\n歴史の本文。")
    assert lead == (para("導入。"),)
    assert sections == (
        Section(2, "概要", (para("概要の本文。"),), ()),
        Section(2, "歴史", (para("歴史の本文。"),), ()),
    )


def test_見出しの階層が木になる() -> None:
    text = """## 歴史
歴史の前文。
### 初期
初期の本文。
#### 詳細
詳細の本文。
### 後期
後期の本文。
## 評価
評価の本文。"""
    _, sections = parse(text)
    assert sections == (
        Section(
            2,
            "歴史",
            (para("歴史の前文。"),),
            (
                Section(
                    3,
                    "初期",
                    (para("初期の本文。"),),
                    (Section(4, "詳細", (para("詳細の本文。"),), ()),),
                ),
                Section(3, "後期", (para("後期の本文。"),), ()),
            ),
        ),
        Section(2, "評価", (para("評価の本文。"),), ()),
    )


def test_本文のない節も作れる() -> None:
    _, sections = parse("## 空の節\n## 次の節\n本文。")
    assert sections == (
        Section(2, "空の節", (), ()),
        Section(2, "次の節", (para("本文。"),), ()),
    )


def test_箇条書きは連なりを一つにまとめる() -> None:
    lead, _ = parse("- 一つ目\n- 二つ目[^a]\n- 三つ目")
    assert lead == (
        BulletList(
            (
                (Text("一つ目"),),
                (Text("二つ目"), RefMark("a")),
                (Text("三つ目"),),
            )
        ),
    )


def test_箇条書きは字下げした続きの行を項目につなぐ() -> None:
    lead, _ = parse("- 長い項目の\n  続き\n- 次")
    assert lead == (BulletList(((Text("長い項目の続き"),), (Text("次"),))),)


def test_段落と箇条書きは空行なしでも切れる() -> None:
    lead, _ = parse("前置き。\n- 項目\n\n後置き。")
    assert lead == (para("前置き。"), BulletList(((Text("項目"),),)), para("後置き。"))


def test_見出しは空行なしでも見出しになる() -> None:
    lead, sections = parse("導入。\n## 節\n本文。")
    assert lead == (para("導入。"),)
    assert sections == (Section(2, "節", (para("本文。"),), ()),)


def test_ハッシュで始まっても空白がなければ本文() -> None:
    lead, _ = parse("#タグ付きの文\n\n##も本文")
    assert lead == (para("#タグ付きの文"), para("##も本文"))


def test_見出しの前後の空白は取る() -> None:
    _, sections = parse("##   節の名前   \n")
    assert sections == (Section(2, "節の名前", (), ()),)


@pytest.mark.parametrize(
    ("text", "line", "keyword"),
    [
        ("導入。\n\n# 大見出し", 3, "#"),
        ("##### 深すぎる", 1, "#"),
        ("##", 1, "空"),
        ("### 飛んだ", 1, "階層"),
        ("## 親\n#### 孫", 2, "階層"),
        ("- 親\n  - 子", 2, "入れ子"),
        ("- 項目\n空行なしの段落", 2, "空行"),
        ("文[[閉じない\nまだ続く。", 1, "[["),
    ],
)
def test_壊れた本文は行番号つきのエラー(text: str, line: int, keyword: str) -> None:
    with pytest.raises(MarkupError) as info:
        parse(text)
    assert info.value.line == line
    assert keyword in info.value.message


def test_行番号は本文の開始行から数える() -> None:
    with pytest.raises(MarkupError) as info:
        parse("導入。\n\n# 大見出し", first_line=10)
    assert info.value.line == 12


def test_記法が複数行にまたがるエラーは記法の始まりの行を指す() -> None:
    with pytest.raises(MarkupError) as info:
        parse("一行目。\n\n二行目の[[閉じない\n三行目。", first_line=5)
    assert info.value.line == 7


def test_箇条書きの項目の中の記法のエラーも行番号を持つ() -> None:
    with pytest.raises(MarkupError) as info:
        parse("- 良い\n- 悪い[^", first_line=20)
    assert info.value.line == 21


def test_全角空白の字下げは本文に残して検査に回す() -> None:
    lead, _ = parse("\u3000字下げした段落。\n\u3000二行目。")
    assert lead == (para("\u3000字下げした段落。\u3000二行目。"),)


def test_全角空白だけの行は空行として扱う() -> None:
    lead, _ = parse("一つ目。\n\u3000\n二つ目。")
    assert lead == (para("一つ目。"), para("二つ目。"))


# --- 噂の節 -----------------------------------------------------------------------


def test_見出しの末尾の噂の印で節ごと噂になる() -> None:
    _, sections = parse("## 騒動 [!噂]\n本文。\n### 経緯\n経緯。\n## 評価\n評価。")
    assert sections == (
        Section(
            2,
            "騒動",
            (para("本文。"),),
            (Section(3, "経緯", (para("経緯。"),), ()),),
            rumor=True,
        ),
        Section(2, "評価", (para("評価。"),), ()),
    )
    assert sections[0].children[0].rumor is False
    assert sections[1].rumor is False


def test_子の節だけを噂にもできる() -> None:
    _, sections = parse("## 歴史\n### 噂の時代 [!噂]\n本文。")
    assert sections[0].rumor is False
    assert sections[0].children[0] == Section(3, "噂の時代", (para("本文。"),), (), rumor=True)


@pytest.mark.parametrize(
    "text",
    ["## [!噂] 騒動", "## 騒[!噂]動", "## 騒動 [!噂] [!噂]", "## 騒動 [!噂|x]"],
)
def test_見出しの途中の噂の印はエラー(text: str) -> None:
    with pytest.raises(MarkupError) as info:
        parse(f"導入。\n\n{text}")
    assert info.value.line == 3
    assert "見出し" in info.value.message


def test_噂の印だけの見出しは空の見出しのエラー() -> None:
    with pytest.raises(MarkupError, match="空"):
        parse("## [!噂]")


def test_噂の範囲は段落の中で読む() -> None:
    lead, _ = parse("[!噂|一行目\nと二行目]")
    assert lead == (Paragraph((RumorRange((Text("一行目と二行目"),)),)),)
