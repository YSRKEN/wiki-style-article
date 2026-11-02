"""読み取った記事を検査して、誤り（エラー）と注意（警告）の一覧を返す。

- エラー: 誤検出しにくい作法の違反。直すまで原稿を渡さない
- 警告: 誤検出しうる作法。一覧で示し、AI が読み直して直すか残すかを決める

規則の一覧と、エラーか警告かの振り分けの理由は ``docs/checks.md``。

使い方::

    from wikiskill import read_article_file
    from wikiskill.checks import check_article

    for finding in check_article(read_article_file("原稿.md")):
        print(finding)
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from wikiskill.checks.finding import Finding, Level
from wikiskill.checks.infobox import check_infobox
from wikiskill.checks.notation import check_notation
from wikiskill.checks.references import check_references
from wikiskill.checks.structure import check_structure
from wikiskill.checks.wording import check_wording
from wikiskill.model import Article
from wikiskill.types import TypeRegistry
from wikiskill.variants import has_rumor, normal_view, rumor_view

__all__ = ["Finding", "Level", "check_article", "check_article_variants"]

_CONTEXT = re.compile(r"（….*…）$")
"""指摘の文面の末尾に添える前後の文字（``（…前後の文字…）``）。"""


def check_article(article: Article, registry: TypeRegistry | None = None) -> tuple[Finding, ...]:
    """記事を検査して、見つかったものを行番号の順に返す。

    Parameters
    ----------
    article : Article
        :func:`wikiskill.read_article` で読み取った記事。
    registry : TypeRegistry | None
        類型の定義。渡すと、原稿の ``type`` と Infobox を定義と突き合わせる規則
        （``TYPE-UNKNOWN``・``INFOBOX-MISSING``・``INFOBOX-UNKNOWN-FIELD``）も検査する。
        通常は :func:`wikiskill.load_default_registry` の結果を渡す。省くとそれらの規則は
        検査せず、定義に依らない規則だけを検査する。

    Returns
    -------
    tuple[Finding, ...]
        行番号の昇順。同じ行ではエラーが先、そのあと規則の ID の順。
    """
    findings = [
        *check_references(article),
        *check_structure(article),
        *check_notation(article),
        *check_wording(article),
    ]
    if registry is not None:
        findings.extend(check_infobox(article, registry))
    return _sorted(findings)


def check_article_variants(
    article: Article, registry: TypeRegistry | None = None
) -> tuple[Finding, ...]:
    """噂のある原稿は、通常の版と噂込みの版の両方を検査して、指摘を合わせて返す。

    噂（``[!噂|…]`` か ``[!噂]`` の節）が無い原稿は :func:`check_article` と同じ。噂があれば、
    :func:`wikiskill.variants.normal_view` と :func:`wikiskill.variants.rumor_view` の結果を
    それぞれ検査し、同じ指摘（重さ・規則・行と、末尾の前後の文字の添え書きを除いた文面が同じ
    もの）は一つにまとめる（通常の版の指摘を残す）。

    Parameters
    ----------
    article : Article
        :func:`wikiskill.read_article` で読み取った記事。噂の部品を含んでよい。
    registry : TypeRegistry | None
        類型の定義。:func:`check_article` と同じ。

    Returns
    -------
    tuple[Finding, ...]
        :func:`check_article` と同じ並び。
    """
    if not has_rumor(article):
        return check_article(article, registry)
    merged: dict[tuple[Level, str, int, str], Finding] = {}
    for finding in (
        *check_article(normal_view(article), registry),
        *check_article(rumor_view(article), registry),
    ):
        # 前後の文字の添え書きは版で変わるので、それを除いて同じ指摘かを見る。先に出た方を残す。
        message = _CONTEXT.sub("", finding.message)
        merged.setdefault((finding.level, finding.rule, finding.line, message), finding)
    return _sorted(merged.values())


def _sorted(findings: Iterable[Finding]) -> tuple[Finding, ...]:
    """行番号の昇順、同じ行ではエラーが先、そのあと規則の ID の順に並べる。"""
    return tuple(sorted(findings, key=lambda f: (f.line, f.level is not Level.ERROR, f.rule)))
