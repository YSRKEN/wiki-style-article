"""画像の規則（道・種類・実物・大きさ・キャプション）。"""

from __future__ import annotations

from collections.abc import Iterator

from wikiskill.checks.finding import Finding, Level
from wikiskill.checks.walk import iter_figures
from wikiskill.images import find_issue
from wikiskill.model import Article


def check_images(article: Article) -> Iterator[Finding]:
    """画像の道・種類・実物の有無・大きさと、キャプションの有無を検査する。"""
    base_dir = article.base_dir
    for figure in iter_figures(article):
        if not figure.caption.strip():
            yield Finding(
                Level.WARNING,
                "IMAGE-CAPTION",
                "画像のキャプションが空（何の画像かを一文で書く）",
                figure.line,
            )
        issue = find_issue(figure.source, base_dir)
        if issue is not None:
            yield Finding(Level.ERROR, issue[0], issue[1], figure.line)
