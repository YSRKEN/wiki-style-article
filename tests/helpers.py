"""検査の試験で使う、短い原稿から記事を作る補助。"""

from __future__ import annotations

from wikiskill.checks import Finding, Level, check_article
from wikiskill.model import Article
from wikiskill.reader import read_article


def make_article(body: str = "本文。", settings: str = "", *, title: str = "試験") -> Article:
    """題名と類型だけ付けた原稿に、追加の設定欄と本文を足して読み取る。

    設定欄の行は 2 行目が ``title``、3 行目が ``type``、4 行目から ``settings``。
    本文の先頭の行は ``5 + settings の行数`` 行目。
    """
    config = f'title = "{title}"\ntype = "person"\n'
    if settings:
        config += settings.strip("\n") + "\n"
    return read_article(f"+++\n{config}+++\n{body}\n")


def run(body: str = "本文。", settings: str = "", *, title: str = "試験") -> tuple[Finding, ...]:
    """原稿を検査して、見つかったものを返す。"""
    return check_article(make_article(body, settings, title=title))


def rules(findings: tuple[Finding, ...]) -> list[str]:
    """見つかったものの規則 ID の並び。"""
    return [finding.rule for finding in findings]


def only(findings: tuple[Finding, ...], rule: str) -> list[Finding]:
    """指定した規則のものだけ。"""
    return [finding for finding in findings if finding.rule == rule]


__all__ = ["Finding", "Level", "make_article", "only", "rules", "run"]
