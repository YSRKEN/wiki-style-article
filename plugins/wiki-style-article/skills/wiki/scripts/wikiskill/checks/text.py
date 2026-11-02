"""検査の対象になる文字を、記法を取り除いた「表示される文字」として取り出す。

太字・内部リンク・脚注の印のような記法は、画面に出る文字だけにそろえる
（内部リンクは表示の文字、脚注の印は無し）。作品名や記事名にあたる部分は、
約物や語句の規則で誤検出しやすいので ``protected`` として位置を覚えておく。
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass

from wikiskill.checks.walk import iter_inline_groups, iter_sections
from wikiskill.model import Article, Bold, FixRange, Inline, InternalLink, Original, Text

Span = tuple[int, int]
"""文字列の中の範囲（始まりを含み、終わりを含まない）。"""

_BRACKET_PAIRS = {"『": "』", "「": "」"}


@dataclass(frozen=True)
class TextUnit:
    """検査の対象になる、一行ぶんの表示される文字。

    Attributes
    ----------
    text : str
        記法を取り除いた文字。
    line : int
        原稿ファイル全体での行番号。段落なら段落の先頭の行。
    titles : tuple[Span, ...]
        記事名・作品名にあたる範囲。内部リンクの表示・太字・``『』`` の中。
    quotes : tuple[Span, ...]
        ``「」``・``『』`` の中の範囲。引用やせりふ、作品名を含む。
    foreign : tuple[Span, ...]
        外国語の原文（``[!原文|…]``）の範囲。和文用の検査にはかけない。
    """

    text: str
    line: int
    titles: tuple[Span, ...]
    quotes: tuple[Span, ...]
    foreign: tuple[Span, ...] = ()

    @property
    def searchable(self) -> str:
        """和文用の検査にかける文字。原文の範囲は、長さを保ったまま検査に引っかからない字に替える。"""
        return mask_spans(self.text, self.foreign)

    def in_titles(self, position: int) -> bool:
        """``position`` が記事名・作品名の範囲に入っているか。"""
        return any(start <= position < end for start, end in self.titles)

    def in_quotes(self, position: int) -> bool:
        """``position`` が ``「」``・``『』`` の中に入っているか。"""
        return any(start <= position < end for start, end in self.quotes)


_MASK = "\ue000"
"""原文の範囲を塗りつぶす字（私用領域の字。どの規則にも当たらない）。"""


def mask_spans(text: str, spans: tuple[Span, ...]) -> str:
    """``spans`` の範囲を、同じ長さの検査に当たらない字に置き換える。"""
    for start, end in spans:
        text = text[:start] + _MASK * (end - start) + text[end:]
    return text


def bracket_spans(text: str, opening: str, closing: str) -> tuple[Span, ...]:
    """括弧で囲まれた範囲を、括弧を含めて求める。

    ``opening`` から最初の ``closing`` までを一つの範囲とする。

    閉じていなければ末尾まで。
    """
    spans: list[Span] = []
    position = 0
    while (start := text.find(opening, position)) != -1:
        end = text.find(closing, start + 1)
        stop = len(text) if end == -1 else end + 1
        spans.append((start, stop))
        position = stop
    return tuple(spans)


def make_unit(
    text: str, line: int, titles: tuple[Span, ...] = (), foreign: tuple[Span, ...] = ()
) -> TextUnit:
    """文字列から :class:`TextUnit` を作る。``『』``・``「」`` の範囲は文字から求める。

    括弧の範囲は、外国語の原文の範囲を除いた文字から求める（原文の中の括弧を数えない）。
    """
    shown = mask_spans(text, foreign)
    brackets = tuple(
        span
        for opening, closing in _BRACKET_PAIRS.items()
        for span in bracket_spans(shown, opening, closing)
    )
    work_titles = bracket_spans(shown, "『", "』")
    return TextUnit(
        text=text,
        line=line,
        titles=tuple(sorted({*titles, *work_titles})),
        quotes=tuple(sorted(set(brackets))),
        foreign=foreign,
    )


def _unit_from_parts(parts: tuple[Inline, ...], line: int) -> TextUnit:
    buffer: list[str] = []
    titles: list[Span] = []
    foreign: list[Span] = []
    length = 0

    def add(text: str, *, title: bool) -> None:
        nonlocal length
        if title and text:
            titles.append((length, length + len(text)))
        buffer.append(text)
        length += len(text)

    def visit(items: tuple[Inline, ...]) -> None:
        for part in items:
            if isinstance(part, Text):
                add(part.text, title=False)
            elif isinstance(part, InternalLink):
                add(part.display, title=True)
            elif isinstance(part, Original):
                foreign.append((length, length + len(part.text)))
                add(part.text, title=False)
            elif isinstance(part, FixRange):
                # 範囲の印は記法だけを取り除き、範囲の文はふつうの本文として見る。
                visit(part.children)
            elif isinstance(part, Bold):
                shown = "".join(
                    child.text
                    if isinstance(child, Text)
                    else child.display
                    if isinstance(child, InternalLink)
                    else ""
                    for child in part.children
                )
                add(shown, title=True)

    visit(parts)
    return make_unit("".join(buffer), line, tuple(titles), tuple(foreign))


def iter_units(article: Article) -> Iterator[TextUnit]:
    """本文（導入部・節）・見出し・Infobox の値・注釈の本文を、表示される文字として取り出す。"""
    for parts, line in iter_inline_groups(article):
        yield _unit_from_parts(parts, line)
    for section in iter_sections(article):
        yield make_unit(section.title, section.line)
    for field in article.settings.infobox:
        yield make_unit(field.value, field.line)


_SPACES = re.compile(r"\s+")


def snippet(unit: TextUnit, start: int, end: int, width: int = 10) -> str:
    """指摘の前後の文字を、読める長さだけ切り出す。"""
    left = max(0, start - width)
    right = min(len(unit.text), end + width)
    return _SPACES.sub(" ", unit.text[left:right])
