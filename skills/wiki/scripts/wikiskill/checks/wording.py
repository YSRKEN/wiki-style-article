"""言葉の選び（評価語・婉曲・古くなる表現・仮名の開き）の規則。

どれも警告。語の出現は文脈次第で正当なことがあるため、一覧で示して AI が読み直し、
具体的な事実や出典付きの記述に直すか、残すかを決める。引用やせりふ（``「」``）と
作品名（``『』``・内部リンク・太字）の中は見逃す。根拠は次のとおり（``docs/checks.md``）。

- 大言壮語をしない（WORD-PUFFERY）
- 言葉を濁さない（WORD-HEDGE）
- 避けたい言葉（草案。WORD-AVOID）
- すぐに古くなる表現は使わない（WORD-STALE）
- 日本中心にならないように（試行中。WORD-JAPAN-CENTRIC）
- 表記ガイドの仮名書き（KANA-OPEN）
"""

from __future__ import annotations

from collections.abc import Iterator

from wikiskill.checks.finding import Finding, Level
from wikiskill.checks.patterns import Pattern, Skip, pattern, scan, word_pattern
from wikiskill.checks.text import iter_units
from wikiskill.model import Article

_W = Level.WARNING

_PUFFERY = (
    "重要な",
    "重大な",
    "最も影響力",
    "議論の余地",
    "明白な",
    "伝説的",
    "美しい",
    "話題となった",
    "究極の",
    "非常に",
    "極めて",
    "絶大",
    "屈指",
    "有数",
    "国民的",
    "とてつもな",
    "必読",
    "有名な",
    "傑作",
    "名作",
    "名曲",
    "偉大な",
    "素晴らしい",
    "圧倒的",
    "随一",
)

_HEDGE = (
    "と言われている",
    "と言われる",
    "と言う人もいる",
    "と考えられている",
    "と考えられる",
    "と見なされている",
    "とみなされている",
    "と信じられている",
    "と思われる",
    "と見られる",
    "と言える",
    "と言えよう",
    "という声",
    "という話もある",
    "という可能性",
    "という指摘",
    "という批判",
    "と見る向き",
    "広く考えられ",
    "知られている",
    "知られる",
    "ようである",
    "が窺える",
    "とのこと",
    "だろう",
    "であろう",
    "かもしれない",
    "なぜか",
    "言わずと知れた",
    "伝えられるところでは",
)

_AVOID = (
    "もちろん",
    "当然",
    "明白である",
    "言うまでもなく",
    "いわゆる",
    "俗に",
    "いい意味で",
    "よい意味で",
    "を誇る",
    "話によると",
    "伝説によると",
    "根本的に",
    "基本的に",
)

_STALE = ("近年", "現代では", "今のところ", "近い将来", "現時点", "今日では", "昨今")

_JAPAN_CENTRIC = ("我が国", "本邦", "邦人", "我々", "世界的に", "世界的な")

_KANA_OPEN = {
    "或いは": "あるいは",
    "及び": "および",
    "且つ": "かつ",
    "更に": "さらに",
    "即ち": "すなわち",
    "但し": "ただし",
    "又は": "または",
    "若しくは": "もしくは",
    "故に": "ゆえに",
    "所謂": "いわゆる",
    "其の": "その",
    "何故": "なぜ",
    "殆ど": "ほとんど",
    "沢山": "たくさん",
    "有り難う": "ありがとう",
    "下さい": "ください",
    "貴方": "あなた",
}

PATTERNS: tuple[Pattern, ...] = (
    word_pattern(
        "WORD-PUFFERY",
        _W,
        _PUFFERY,
        "評価語がある。形容詞で盛らず、受賞・順位・回数などの事実で示す",
    ),
    word_pattern(
        "WORD-HEDGE",
        _W,
        _HEDGE,
        "言葉を濁した言い方がある。誰の意見かを書いて出典を付けるか、具体的な事実に置き換える",
    ),
    pattern(
        "WORD-HEDGE",
        _W,
        r"[たるくうつぬむぶぐすいだ]らしい",
        "言葉を濁した言い方がある。誰の意見かを書いて出典を付けるか、具体的な事実に置き換える",
        Skip.QUOTES,
    ),
    word_pattern(
        "WORD-AVOID",
        _W,
        _AVOID,
        "避けたい言葉がある（読者の知識の決めつけ、中身のない断り書き、自慢の含み）。"
        "事実を並べる形に直す",
    ),
    word_pattern(
        "WORD-STALE",
        _W,
        _STALE,
        "すぐに古くなる表現がある。「2026年11月現在」のように時点を年月で書く",
    ),
    pattern(
        "WORD-STALE",
        _W,
        r"最近(?![傍接])",
        "すぐに古くなる表現がある。「2026年11月現在」のように時点を年月で書く",
        Skip.QUOTES,
    ),
    pattern(
        "WORD-STALE",
        _W,
        r"(?<![年月日時末度])現在(?![のの形地])",
        "すぐに古くなる表現がある。「2026年11月現在」のように時点を年月で書く",
        Skip.QUOTES,
    ),
    word_pattern(
        "WORD-JAPAN-CENTRIC",
        _W,
        _JAPAN_CENTRIC,
        "日本の読者だけを前提にした言い方がある。「日本」「日本では」と書き、地域や数字を具体的にする",
    ),
    *(
        word_pattern(
            "KANA-OPEN",
            _W,
            [word],
            f"仮名で書く語が漢字になっている（{word} → {kana}）。動詞・名詞の用法なら残す",
        )
        for word, kana in _KANA_OPEN.items()
    ),
)
"""言葉の選びの規則の一覧。"""


def check_wording(article: Article) -> Iterator[Finding]:
    """本文・見出し・Infobox の値・注釈の本文の言葉の選びを検査する。"""
    yield from scan(iter_units(article), PATTERNS)
