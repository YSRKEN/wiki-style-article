import pytest

from wikiskill.errors import MarkupError
from wikiskill.inline import parse_inline
from wikiskill.model import (
    FIX_MARK_KINDS,
    FIX_RANGE_KINDS,
    Bold,
    FixMark,
    FixMarkKind,
    FixRange,
    FixRangeKind,
    InternalLink,
    NoteMark,
    RefMark,
    Text,
)


def test_ふつうの文字はそのまま一つの文字列になる() -> None:
    assert parse_inline("これは本文です。") == (Text("これは本文です。"),)


def test_空文字列は部品なし() -> None:
    assert parse_inline("") == ()


def test_太字は子の部品を持つ() -> None:
    assert parse_inline("'''ひだまり市'''は架空の都市。") == (
        Bold((Text("ひだまり市"),)),
        Text("は架空の都市。"),
    )


def test_脚注の印は出典のキーを持つ() -> None:
    assert parse_inline("開館した[^a-1]。") == (
        Text("開館した"),
        RefMark("a-1"),
        Text("。"),
    )


def test_脚注の印は並べてよい() -> None:
    assert parse_inline("開館した[^a][^b]。") == (
        Text("開館した"),
        RefMark("a"),
        RefMark("b"),
        Text("。"),
    )


def test_注釈の印は_n_コロンで始まる() -> None:
    assert parse_inline("読みは諸説ある[^n:yomi]。") == (
        Text("読みは諸説ある"),
        NoteMark("yomi"),
        Text("。"),
    )


def test_内部リンクは表示を省ける() -> None:
    assert parse_inline("[[東雲町]]の北") == (InternalLink("東雲町", None), Text("の北"))


def test_内部リンクは表示を付けられる() -> None:
    assert parse_inline("[[東雲町|町]]の北") == (InternalLink("東雲町", "町"), Text("の北"))


def test_内部リンクの表示は表示名を返す() -> None:
    assert InternalLink("東雲町", None).display == "東雲町"
    assert InternalLink("東雲町", "町").display == "町"


def test_太字の中に内部リンクと脚注を入れられる() -> None:
    assert parse_inline("'''[[星屑ラーメン]][^a]'''") == (
        Bold((InternalLink("星屑ラーメン", None), RefMark("a"))),
    )


def test_ほかの記法の文字はそのまま本文() -> None:
    text = "角括弧[1]や二重の引用''斜体''、#タグ、]]は本文のまま。"
    assert parse_inline(text) == (Text(text),)


def test_印が指すキーが設定欄にあるかは見ない() -> None:
    assert parse_inline("[^nowhere]") == (RefMark("nowhere"),)


@pytest.mark.parametrize(
    ("text", "keyword"),
    [
        ("[[閉じていない", "[["),
        ("文[^a", "[^"),
        ("'''閉じていない太字", "'''"),
        ("[[]]", "空"),
        ("[[|表示]]", "空"),
        ("[[記事|]]", "空"),
        ("[[記事|a|b]]", "|"),
        ("[[外[[内]]]]", "入れ子"),
        ("[^]", "空"),
        ("[^n:]", "空"),
        ("[^日本語]", "キー"),
        ("[^a b]", "キー"),
        ("[^n:a b]", "キー"),
        ("''''''", "空"),
        # 印
        ("文[!未知の印]", "未知の印"),
        ("[!]", "未知の印"),
        ("文[!要出典", "[!"),
        ("文[!要出典|範囲]", "|"),
        ("[!要出典範囲]", "|"),
        ("[!独自研究範囲]", "|"),
        ("[!要出典範囲|]", "空"),
        ("[!要出典範囲|  ]", "空"),
        ("[!要出典範囲|範囲[[閉じない]", "[!"),
        ("[!要出典範囲|'''太字'''の文]", "太字"),
        ("[!要出典範囲|文[!要出典]]", "入れ子"),
        ("'''太字[!要出典範囲|文]'''", "太字"),
    ],
)
def test_壊れた記法は行番号つきのエラー(text: str, keyword: str) -> None:
    with pytest.raises(MarkupError) as info:
        parse_inline(text, 7)
    assert info.value.line == 7
    assert keyword in info.value.message
    assert str(info.value).startswith("7 行目: ")


def test_行番号は文字位置から引ける() -> None:
    # 先頭 5 文字が 3 行目、そのあとが 4 行目という対応。
    def line_of(offset: int) -> int:
        return 3 if offset < 5 else 4

    with pytest.raises(MarkupError) as info:
        parse_inline("12345[[閉じない", line_of)
    assert info.value.line == 4


# --- 印 ---------------------------------------------------------------------


@pytest.mark.parametrize("kind", FIX_MARK_KINDS)
def test_点の印は文の直後に付ける(kind: FixMarkKind) -> None:
    assert parse_inline(f"開館したという[!{kind}]。") == (
        Text("開館したという"),
        FixMark(kind),
        Text("。"),
    )


def test_点の印は出典の印のあとに並べられる() -> None:
    assert parse_inline("開館した[^a][!信頼性要検証]。") == (
        Text("開館した"),
        RefMark("a"),
        FixMark("信頼性要検証"),
        Text("。"),
    )


@pytest.mark.parametrize("kind", FIX_RANGE_KINDS)
def test_範囲の印は範囲の文を包む(kind: FixRangeKind) -> None:
    assert parse_inline(f"前置き。[!{kind}|一説には閉館が近い]。") == (
        Text("前置き。"),
        FixRange(kind, (Text("一説には閉館が近い"),)),
        Text("。"),
    )


def test_範囲の文には内部リンクと出典と注釈の印を書ける() -> None:
    assert parse_inline("[!要出典範囲|[[東雲町|町]]の北にある[^a][^n:b]]だという。") == (
        FixRange(
            "要出典範囲",
            (
                InternalLink("東雲町", "町"),
                Text("の北にある"),
                RefMark("a"),
                NoteMark("b"),
            ),
        ),
        Text("だという。"),
    )


def test_範囲の終わりは入れ子を数えて決める() -> None:
    # 内部リンクの ] や | で範囲が閉じない。
    assert parse_inline("[!独自研究範囲|[[記事|表示]]と[[別]]]。") == (
        FixRange(
            "独自研究範囲",
            (InternalLink("記事", "表示"), Text("と"), InternalLink("別", None)),
        ),
        Text("。"),
    )


def test_範囲の文の中の等号や縦線はそのまま文字() -> None:
    assert parse_inline("[!要出典範囲|a=b|c]") == (FixRange("要出典範囲", (Text("a=b|c"),)),)


def test_太字の中にも点の印を置ける() -> None:
    assert parse_inline("'''名物[!要出典]'''") == (Bold((Text("名物"), FixMark("要出典"))),)


def test_印の読み取りのエラーは印の行を指す() -> None:
    def line_of(offset: int) -> int:
        return 3 if offset < 5 else 4

    with pytest.raises(MarkupError) as info:
        parse_inline("12345[!要出典範囲|文'''太字'''", line_of)
    assert info.value.line == 4
