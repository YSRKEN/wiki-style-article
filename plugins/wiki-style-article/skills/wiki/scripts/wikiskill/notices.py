"""記事の冒頭に貼る警告の枠を、記事の中の印と設定欄の ``notices`` から決める。

HTML とウィキテキストの書き出しは、どちらもこのモジュールで枠を決める。

- ``要出典``・``要出典範囲``・``信頼性要検証`` の印が一つでもあれば ``出典の明記``
- ``独自研究範囲`` の印があれば ``独自研究``
- 設定欄の ``notices`` に書いた枠を足す（重ねない）

並びは :data:`~wikiskill.model.NOTICE_KINDS` の順（出典の明記・独自研究・観点）。
"""

from __future__ import annotations

from wikiskill.checks.walk import flatten, iter_inline_groups
from wikiskill.model import NOTICE_KINDS, Article, FixMark, FixRange, NoticeKind

__all__ = ["article_notices"]


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
    found: set[NoticeKind] = set(article.settings.notices)
    for parts, _line in iter_inline_groups(article):
        for part in flatten(parts):
            if isinstance(part, FixMark) or (
                isinstance(part, FixRange) and part.kind == "要出典範囲"
            ):
                found.add("出典の明記")
            elif isinstance(part, FixRange):
                found.add("独自研究")
    return tuple(kind for kind in NOTICE_KINDS if kind in found)
