"""記事の冒頭に貼る警告の枠を、記事の中の印と設定欄の ``notices``・``notice_rule`` から決める。

HTML とウィキテキストの書き出しは、どちらもこのモジュールで枠を決める。

- ``要出典``・``要出典範囲``・``信頼性要検証`` の印から ``出典の明記``
- ``独自研究範囲`` の印から ``独自研究``
- 印から決まる枠は ``notice_rule`` に従う。``多いときだけ``（既定）は、その種類の印の数が、
  脚注の印と印を合わせた数の 2 割以上のときだけ。``付ける`` は印が一つでもあれば、
  ``付けない`` は付けない。本物でも、要出典が数か所あるだけの記事に枠までは貼らないため
  （2026-11-02、作者の決定）
- 設定欄の ``notices`` に書いた枠は、出し方によらず足す（重ねない）。噂込みの版の ``観点`` も
  ここに入る

並びは :data:`~wikiskill.model.NOTICE_KINDS` の順（出典の明記・独自研究・観点）。
"""

from __future__ import annotations

from wikiskill.checks.walk import flatten, iter_inline_groups
from wikiskill.model import NOTICE_KINDS, Article, FixMark, FixRange, NoticeKind, RefMark

__all__ = ["MANY_MARKS_PERCENT", "article_notices"]

MANY_MARKS_PERCENT = 20
"""``多いときだけ`` で枠を付ける、印の割合の下限（百分率）。小数の誤差を避けて整数で比べる。"""


def article_notices(article: Article) -> tuple[NoticeKind, ...]:
    """記事に貼る警告の枠を決める。

    Parameters
    ----------
    article : Article
        読み取った記事。導入部・節・注釈の本文の印を見る（太字と範囲の印の中も）。

    Returns
    -------
    tuple[NoticeKind, ...]
        貼る枠。出典の明記・独自研究・観点の順で、重ならない。無ければ空。
    """
    marks: dict[NoticeKind, int] = {"出典の明記": 0, "独自研究": 0}
    refs = 0
    for parts, _line in iter_inline_groups(article):
        for part in flatten(parts):
            if isinstance(part, RefMark):
                refs += 1
            elif isinstance(part, FixMark) or (
                isinstance(part, FixRange) and part.kind == "要出典範囲"
            ):
                marks["出典の明記"] += 1
            elif isinstance(part, FixRange):
                marks["独自研究"] += 1
    found: set[NoticeKind] = set(article.settings.notices)
    rule = article.settings.notice_rule
    for kind, count in marks.items():
        if count == 0 or rule == "付けない":
            continue
        if rule == "付ける" or count * 100 >= MANY_MARKS_PERCENT * (refs + count):
            found.add(kind)
    return tuple(kind for kind in NOTICE_KINDS if kind in found)
