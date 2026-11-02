"""正規表現で文字を探す規則の共通の仕組み。

規則は :class:`Pattern` の表として書き、 :func:`scan` が全ての文字に当てて :class:`Finding` にする。
同じ行の同じ規則で同じ文字が何度出ても、指摘は一件にまとめる。
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from enum import Enum, auto

from wikiskill.checks.finding import Finding, Level
from wikiskill.checks.text import TextUnit, snippet


class Skip(Enum):
    """どの範囲の中の一致を見逃すか。"""

    NOTHING = auto()
    """見逃さない。題名の中でも直すべき規則に使う。"""

    TITLES = auto()
    """記事名・作品名（内部リンクの表示・太字・``『』``）の中を見逃す。"""

    QUOTES = auto()
    """記事名・作品名に加えて、``「」`` の中（引用・せりふ）も見逃す。"""


@dataclass(frozen=True)
class Pattern:
    """一つの規則。

    Attributes
    ----------
    rule : str
        規則の ID。
    level : Level
        エラーか警告か。
    regex : re.Pattern[str]
        探す文字。
    message : str
        指摘の文面。見つけた文字は ``「…」`` で後ろに添える。
    skip : Skip
        見逃す範囲。
    """

    rule: str
    level: Level
    regex: re.Pattern[str]
    message: str
    skip: Skip = Skip.TITLES


def pattern(
    rule: str,
    level: Level,
    regex: str,
    message: str,
    skip: Skip = Skip.TITLES,
) -> Pattern:
    """正規表現の文字列から :class:`Pattern` を作る。"""
    return Pattern(rule, level, re.compile(regex), message, skip)


def word_pattern(
    rule: str,
    level: Level,
    words: Iterable[str],
    message: str,
    skip: Skip = Skip.QUOTES,
) -> Pattern:
    """語の一覧から、どれかに当たる :class:`Pattern` を作る（長い語を先に試す）。"""
    ordered = sorted(set(words), key=len, reverse=True)
    return pattern(rule, level, "|".join(re.escape(word) for word in ordered), message, skip)


def _skipped(unit: TextUnit, position: int, skip: Skip) -> bool:
    if skip is Skip.NOTHING:
        return False
    if unit.in_titles(position):
        return True
    return skip is Skip.QUOTES and unit.in_quotes(position)


def scan(units: Iterable[TextUnit], patterns: Iterable[Pattern]) -> Iterator[Finding]:
    """すべての文字にすべての規則を当てて、見つけたものを返す。"""
    patterns = tuple(patterns)
    seen: set[tuple[str, int, str]] = set()
    for unit in units:
        searchable = unit.searchable
        for item in patterns:
            for found in item.regex.finditer(searchable):
                if _skipped(unit, found.start(), item.skip):
                    continue
                key = (item.rule, unit.line, found.group())
                if key in seen:
                    continue
                seen.add(key)
                context = snippet(unit, found.start(), found.end())
                yield Finding(
                    item.level,
                    item.rule,
                    f"{item.message}「{found.group()}」（…{context}…）",
                    unit.line,
                )
