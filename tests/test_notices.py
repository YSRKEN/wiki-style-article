import pytest

from wikiskill.model import NoticeKind
from wikiskill.notices import article_notices
from wikiskill.reader import read_article


def _notices(body: str, front: str = "") -> tuple[NoticeKind, ...]:
    source = f'+++\ntitle = "題"\ntype = "concept"\n{front}+++\n{body}\n'
    return article_notices(read_article(source))


def test_印も設定も無ければ枠は無い() -> None:
    assert _notices("本文。") == ()


@pytest.mark.parametrize("mark", ["[!要出典]", "[!信頼性要検証]", "[!要出典範囲|甲]"])
def test_出典の印があれば出典の明記(mark: str) -> None:
    assert _notices(f"甲{mark}。") == ("出典の明記",)


def test_独自研究範囲の印があれば独自研究() -> None:
    assert _notices("[!独自研究範囲|甲]。") == ("独自研究",)


def test_太字と節と箇条書きの中の印も数える() -> None:
    assert _notices("'''甲[!要出典]'''。") == ("出典の明記",)
    assert _notices("導入。\n\n## 節\n\n- [!独自研究範囲|甲]") == ("独自研究",)


def test_注釈の中の印も数える() -> None:
    front = '[notes.a]\ntext = "[!独自研究範囲|注の文]"\n'
    assert _notices("甲[^n:a]。", front) == ("独自研究",)


def test_設定欄の枠を足し重ねず決まった順に並べる() -> None:
    front = 'notices = ["観点", "出典の明記"]\n'
    assert _notices("[!独自研究範囲|甲][!要出典]。", front) == ("出典の明記", "独自研究", "観点")


def test_同じ設定を二度書いても一つ() -> None:
    assert _notices("甲。", 'notices = ["観点", "観点"]\n') == ("観点",)


# --- 枠の出し方（notice_rule）--------------------------------------------------


def _body(refs: int, marks: int, mark: str = "[!要出典]") -> str:
    """脚注の印 ``refs`` 個と、印 ``marks`` 個を、それぞれ別の文に付けた本文。"""
    return "".join(["甲[^a]。"] * refs + [f"乙{mark}。"] * marks)


@pytest.mark.parametrize(
    ("refs", "marks", "expected"),
    [
        (20, 2, ()),  # 2 ÷ 22 は約 9%
        (20, 4, ()),  # 4 ÷ 24 は約 17%
        (20, 5, ("出典の明記",)),  # 5 ÷ 25 はちょうど 2 割
        (4, 1, ("出典の明記",)),
        (0, 1, ("出典の明記",)),
    ],
)
def test_既定は印が_2_割以上のときだけ枠を付ける(
    refs: int, marks: int, expected: tuple[NoticeKind, ...]
) -> None:
    assert _notices(_body(refs, marks)) == expected


def test_独自研究の枠も_2_割の線で決める() -> None:
    assert _notices(_body(9, 1, "[!独自研究範囲|丙]")) == ()
    assert _notices(_body(4, 1, "[!独自研究範囲|丙]")) == ("独自研究",)


def test_付けるなら印が一つでも枠を付ける() -> None:
    assert _notices(_body(20, 1), 'notice_rule = "付ける"\n') == ("出典の明記",)


def test_付けないなら印が多くても枠を付けない() -> None:
    assert _notices(_body(0, 3), 'notice_rule = "付けない"\n') == ()


def test_設定欄に書いた枠は出し方によらず付ける() -> None:
    front = 'notice_rule = "付けない"\nnotices = ["観点"]\n'
    assert _notices(_body(0, 3), front) == ("観点",)


def test_出し方に知らない値を書けばエラー() -> None:
    from wikiskill.errors import SourceError

    with pytest.raises(SourceError, match="notice_rule"):
        _notices("甲。", 'notice_rule = "たまに"\n')


def test_噂込みの版は付けないでも観点の枠を付ける() -> None:
    from wikiskill.variants import normal_view, rumor_view

    source = (
        '+++\ntitle = "題"\ntype = "concept"\nnotice_rule = "付けない"\n+++\n'
        "甲[!要出典]。[!噂|乙と言われている。]\n"
    )
    article = read_article(source)

    assert article_notices(normal_view(article)) == ()
    assert article_notices(rumor_view(article)) == ("観点",)
