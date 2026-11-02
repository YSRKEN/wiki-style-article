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
