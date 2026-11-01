"""言葉の選び（評価語・婉曲・古くなる表現など）の規則の試験。

どれも警告。引用やせりふ（「」）と作品名（『』・リンク・太字）の中は見逃す。
"""

import pytest

from helpers import Level, only, run


@pytest.mark.parametrize(
    ("rule", "text"),
    [
        ("WORD-PUFFERY", "彼は重要な役割を果たした。"),
        ("WORD-PUFFERY", "非常に人気のある作品である。"),
        ("WORD-PUFFERY", "伝説的な作品として評価される。"),
        ("WORD-PUFFERY", "この漫画は傑作である。"),
        ("WORD-PUFFERY", "国内でも屈指の発行部数を誇る。"),
        ("WORD-HEDGE", "作者は天才だと言われている。"),
        ("WORD-HEDGE", "この説は広く考えられている。"),
        ("WORD-HEDGE", "モデルがあったと思われる。"),
        ("WORD-HEDGE", "続編が作られるだろう。"),
        ("WORD-HEDGE", "実在した店で知られている。"),
        ("WORD-HEDGE", "実は続編があるらしい。"),
        ("WORD-HEDGE", "という指摘もある。"),
        ("WORD-AVOID", "もちろん、続編も作られた。"),
        ("WORD-AVOID", "いわゆるグルメ漫画である。"),
        ("WORD-AVOID", "言うまでもなく名作である。"),
        ("WORD-STALE", "最近になって再評価された。"),
        ("WORD-STALE", "近年は映像化が増えた。"),
        ("WORD-STALE", "現在、連載中である。"),
        ("WORD-STALE", "今のところ続編はない。"),
        ("WORD-STALE", "現代では珍しい形式である。"),
        ("WORD-JAPAN-CENTRIC", "我が国で初めて連載された。"),
        ("WORD-JAPAN-CENTRIC", "邦人の読者が多い。"),
        ("KANA-OPEN", "雑誌を購入し、又は借りた。"),
        ("KANA-OPEN", "或いは別の巻である。"),
        ("KANA-OPEN", "全く殆ど売れなかった。"),
        ("KANA-OPEN", "全3巻、但し最終巻は未刊。"),
    ],
)
def test_言葉の規則は引っかかる(rule: str, text: str) -> None:
    findings = only(run(text), rule)
    assert findings, text
    assert {finding.level for finding in findings} == {Level.WARNING}
    assert findings[0].line == 5


@pytest.mark.parametrize(
    ("rule", "text"),
    [
        # 引用・せりふの中は見逃す
        ("WORD-PUFFERY", "批評家は「極めて重要な作品」と評した。"),
        ("WORD-HEDGE", "主人公は「そう言われている」と語る。"),
        # 作品名の中は見逃す
        ("WORD-PUFFERY", "『非常に美しい世界』が刊行された。"),
        ("WORD-PUFFERY", "[[伝説的な漫画家一覧]]を参照。"),
        ("WORD-STALE", "'''最近の若者'''は漫画である。"),
        # 語が別の語の一部のときは引っかからない
        ("WORD-PUFFERY", "重要文化財に指定された。"),
        ("WORD-HEDGE", "素晴らしい出来だった。"),
        ("WORD-HEDGE", "子供らしい絵柄である。"),
        ("WORD-HEDGE", "彼女らしい選択だった。"),
        ("WORD-STALE", "2026年11月現在、連載中である。"),
        ("WORD-STALE", "現在の福岡県にあたる。"),
        ("WORD-STALE", "動詞の現在形で書く。"),
        ("WORD-STALE", "最近傍法という手法がある。"),
        ("WORD-JAPAN-CENTRIC", "日本国内の読者が多い。"),
        ("KANA-OPEN", "あるいは別の巻である。"),
        ("KANA-OPEN", "および第2巻。"),
        ("KANA-OPEN", "尚美という名の人物が登場する。"),
    ],
)
def test_言葉の規則の誤検出しやすい例は引っかからない(rule: str, text: str) -> None:
    assert only(run(text), rule) == [], text


def test_見出しとinfoboxと注釈の言葉も見る() -> None:
    settings = '[infobox]\n"評価" = "極めて高い"\n[notes.n]\ntext = "最近の話。"'
    findings = run("導入[^n:n]。\n\n## 傑作の誕生\n\n本文。", settings)
    assert {(f.rule, f.line) for f in findings} >= {
        ("WORD-PUFFERY", 5),  # infobox
        ("WORD-STALE", 7),  # 注釈
        ("WORD-PUFFERY", 11),  # 見出し
    }


def test_同じ語が何度出ても同じ行なら一件() -> None:
    assert len(only(run("非常に、非常に、非常に大きい。"), "WORD-PUFFERY")) == 1
