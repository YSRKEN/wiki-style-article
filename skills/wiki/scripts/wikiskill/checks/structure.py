"""記事の構造（節・導入部・リンク）の規則。"""

from __future__ import annotations

import re
from collections.abc import Iterator

from wikiskill.checks.finding import Finding, Level
from wikiskill.checks.walk import flatten, iter_links, iter_sections
from wikiskill.model import Article, Bold, Paragraph

_TRIVIA_CONTAINS = re.compile(r"トリビア|豆知識|余談|雑学|小ネタ|蛇足|裏話")
_TRIVIA_EXACT = re.compile(r"その他|エピソード|逸話|備考")


def check_structure(article: Article) -> Iterator[Finding]:
    """空の節・導入部の太字・自己リンク・雑多な内容の節名を検査する。"""
    for section in iter_sections(article):
        if not section.blocks and not section.children:
            yield Finding(
                Level.ERROR,
                "EMPTY-SECTION",
                f"節「{section.title}」に中身がない（本文を書くか、節ごと消す）",
                section.line,
            )
        title = section.title.strip()
        if _TRIVIA_CONTAINS.search(title) or _TRIVIA_EXACT.fullmatch(title):
            yield Finding(
                Level.WARNING,
                "TRIVIA-SECTION",
                f"節「{section.title}」は雑多な内容を並べる節になっていないか確かめる"
                "（脈絡のある文にして、本文の該当する節へ織り込む）",
                section.line,
            )

    if article.lead:
        first = article.lead[0]
        has_bold = isinstance(first, Paragraph) and any(
            isinstance(part, Bold) for part in flatten(first.content)
        )
        if not has_bold:
            yield Finding(
                Level.WARNING,
                "LEAD-NO-BOLD",
                "導入部の最初の段落に太字がない（第一文の記事名を '''…''' で太字にする）",
                first.line,
            )

    title = article.settings.title.strip()
    for link, line in iter_links(article):
        if link.target == title:
            yield Finding(
                Level.ERROR,
                "SELF-LINK",
                f"記事自身へのリンク [[{link.target}]] がある（自己リンクは作らない）",
                line,
            )
