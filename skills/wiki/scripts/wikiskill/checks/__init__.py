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
from wikiskill.checks.notation import check_notation
from wikiskill.checks.references import check_references
from wikiskill.model import Article

__all__ = ["Finding", "Level", "check_article"]


def check_article(article: Article) -> tuple[Finding, ...]:
    """記事を検査して、見つかったものを行番号の順に返す。

    Parameters
    ----------
    article : Article
        :func:`wikiskill.read_article` で読み取った記事。

    Returns
    -------
    tuple[Finding, ...]
        行番号の昇順。同じ行ではエラーが先、そのあと規則の ID の順。
    """
    findings = [*check_references(article), *check_notation(article)]
    findings.sort(key=lambda f: (f.line, f.level is not Level.ERROR, f.rule))
    return tuple(findings)
