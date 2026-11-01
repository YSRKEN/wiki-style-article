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

from wikiskill.checks.finding import Finding, Level
from wikiskill.checks.infobox import check_infobox
from wikiskill.checks.notation import check_notation
from wikiskill.checks.references import check_references
from wikiskill.checks.structure import check_structure
from wikiskill.checks.wording import check_wording
from wikiskill.model import Article
from wikiskill.types import TypeRegistry

__all__ = ["Finding", "Level", "check_article"]


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
    findings.sort(key=lambda f: (f.line, f.level is not Level.ERROR, f.rule))
    return tuple(findings)
